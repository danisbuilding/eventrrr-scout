#!/usr/bin/env python3
"""Instagram sweep via the Apify API (apify/instagram-scraper). Writes RawItems.

Usage: python scout/instagram_apify.py <run> [--tier 1|2|all] [--limit N] [--newer-than "21 days"]
Env:   APIFY_TOKEN
Out:   inbox/<run>/instagram.jsonl
Cost:  ~$0.003 per post on Apify's free tier.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTOR = "apify~instagram-scraper"
API = "https://api.apify.com/v2"


def handles(src, tier):
    rows = list(src.get("instagram", []))
    if tier in ("2", "all"):
        rows += src.get("instagram_tier2", [])
    if tier == "2":
        rows = [r for r in rows if r.get("tier") == 2]
    return [r["handle"] for r in rows if r.get("enabled", True)]


def run_actor(token, payload):
    r = requests.post(f"{API}/acts/{ACTOR}/runs", params={"token": token}, json=payload, timeout=60)
    r.raise_for_status()
    run = r.json()["data"]
    rid, ds = run["id"], run["defaultDatasetId"]
    for _ in range(120):  # up to ~20 min
        time.sleep(10)
        st = requests.get(f"{API}/actor-runs/{rid}", params={"token": token}, timeout=30).json()["data"]["status"]
        if st in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
    if st != "SUCCEEDED":
        print(f"apify run {rid} ended {st}", file=sys.stderr)
    items = requests.get(f"{API}/datasets/{ds}/items", params={"token": token, "clean": "true"}, timeout=120).json()
    return items


def to_raw(p, fetched):
    cap = p.get("caption") or ""
    links = re.findall(r"https?://\S+", cap)
    media = [p.get("displayUrl")] + [c.get("displayUrl") for c in p.get("childPosts", []) or []]
    return {
        "id": f"instagram:{p.get('ownerUsername')}:{p.get('shortCode')}",
        "source_type": "instagram",
        "source_name": p.get("ownerUsername"),
        "source_url": p.get("url") or f"https://www.instagram.com/p/{p.get('shortCode')}/",
        "author": p.get("ownerUsername"),
        "posted_at": p.get("timestamp"),
        "fetched_at": fetched,
        "text": cap,
        "links": links,
        "media": [m for m in media if m],
        "meta": {k: p.get(k) for k in ("likesCount", "commentsCount", "hashtags", "type", "locationName")},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--tier", default="all")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--newer-than")
    a = ap.parse_args()
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        sys.exit("APIFY_TOKEN not set")
    src = yaml.safe_load((ROOT / "sources.yaml").read_text())
    d = src.get("defaults", {})
    hs = handles(src, a.tier)
    payload = {
        "resultsType": "posts",
        "directUrls": [f"https://www.instagram.com/{h}/" for h in hs],
        "resultsLimit": a.limit or d.get("ig_posts_per_account", 30),
        "onlyPostsNewerThan": a.newer_than or d.get("ig_newer_than", "21 days"),
        "addParentData": True,
    }
    print(f"sweeping {len(hs)} handles: {', '.join(hs)}")
    items = run_actor(token, payload)
    out = ROOT / "inbox" / a.run / "instagram.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    fetched = dt.datetime.now(dt.timezone.utc).isoformat()
    n = 0
    with out.open("w") as f:
        for p in items:
            if not p.get("shortCode"):
                continue
            f.write(json.dumps(to_raw(p, fetched), ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} posts → {out}")


if __name__ == "__main__":
    main()
