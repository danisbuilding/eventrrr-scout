#!/usr/bin/env python3
"""Push a run's events to Supabase so scout.eventrrr.com can show them.

Usage: python scout/publish.py <run> [--window-from D --window-to D --umbrella NAME]
Env:   SUPABASE_URL, SUPABASE_SERVICE_KEY   (the publish workflow supplies both)
Also: python scout/publish.py <run> --pull-decisions   → decisions/<run>.json (for the learning loop)
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--window-from")
    ap.add_argument("--window-to")
    ap.add_argument("--umbrella", default=None)
    ap.add_argument("--pull-decisions", action="store_true")
    a = ap.parse_args()
    url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}

    if a.pull_decisions:
        r = requests.get(f"{url}/rest/v1/scout_decisions", params={"run": f"eq.{a.run}", "select": "*"}, headers=h, timeout=60)
        r.raise_for_status()
        rows = r.json()
        out = ROOT / "decisions" / f"{a.run}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps({"run": a.run, "decisions": {d["key"]: d for d in rows}}, ensure_ascii=False, indent=1))
        print(f"{len(rows)} decisions → {out}")
        return

    events = json.loads((ROOT / "runs" / a.run / "events.json").read_text())
    run_row = {"run": a.run, "window_from": a.window_from, "window_to": a.window_to, "umbrella": a.umbrella, "event_count": len(events), "updated_at": "now()"}
    r = requests.post(f"{url}/rest/v1/scout_runs", headers=h, json=run_row, timeout=60); r.raise_for_status()
    rows = [{"run": a.run, "key": e["key"], "starts_at": e.get("starts_at"), "category": e.get("category"), "highlight": bool(e.get("highlight")), "data": e, "updated_at": "now()"} for e in events]
    for i in range(0, len(rows), 200):
        r = requests.post(f"{url}/rest/v1/scout_events", headers=h, json=rows[i:i + 200], timeout=120); r.raise_for_status()
    # drop events no longer in this run (re-publish after a re-score)
    keys = ",".join(f'"{e["key"]}"' for e in events)
    requests.delete(f"{url}/rest/v1/scout_events", params={"run": f"eq.{a.run}", "key": f"not.in.({keys})"}, headers=h, timeout=60)
    print(f"published {len(events)} events for run {a.run}")


if __name__ == "__main__":
    main()
