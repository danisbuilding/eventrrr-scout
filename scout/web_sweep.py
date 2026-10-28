#!/usr/bin/env python3
"""Web sweep: fetch enabled sites and umbrella known_pages, follow a few event-looking links,
emit RawItems. Runs in GitHub Actions (plain requests + trafilatura; no browser).

Usage: python scout/web_sweep.py <run> [--umbrella "Día de Muertos 2026"] [--max-links 8]
Out:   inbox/<run>/web.jsonl
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36 eventrrr-scout/1.0"
LINK_RX = re.compile(r"(evento|events?|agenda|cartelera|que-hacer|quehacer|actividad|programa|calendario|fiesta|festival|noviembre|octubre|muertos|ofrenda|taller|concierto|exposici|mercado|bazar|cata)", re.I)
MAX_TEXT = 12000


def fetch(url, timeout=25):
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"}, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.text


def page_text(html, url):
    txt = trafilatura.extract(html, url=url, include_links=False, include_comments=False, favor_recall=True) or ""
    if len(txt) < 300:  # fall back to visible text
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()
        txt = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
    return txt[:MAX_TEXT]


def links_from(html, base):
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base).netloc
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"].split("#")[0])
        if urlparse(href).netloc != host or href in seen or href.rstrip("/") == base.rstrip("/"):
            continue
        label = f"{href} {a.get_text(' ', strip=True)}"
        if LINK_RX.search(label):
            seen.add(href)
            out.append(href)
    return out


def item(source_name, url, text, fetched, links=None, kind="web"):
    return {
        "id": f"{kind}:{re.sub(r'[^a-z0-9]+', '-', source_name.lower()).strip('-')}:{hashlib.sha1(url.encode()).hexdigest()[:12]}",
        "source_type": kind, "source_name": source_name, "source_url": url,
        "fetched_at": fetched, "text": text, "links": links or [], "media": [], "meta": {},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--umbrella", default="")
    ap.add_argument("--max-links", type=int, default=8)
    a = ap.parse_args()
    src = yaml.safe_load((ROOT / "sources.yaml").read_text())
    fetched = dt.datetime.now(dt.timezone.utc).isoformat()
    out = ROOT / "inbox" / a.run / "web.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    targets = []  # (source_name, url, follow_links)
    for s in src.get("sites", []) + src.get("sites_tier2", []):
        if s.get("enabled", True):
            targets.append((s["name"], s["url"], True))
    for u in src.get("umbrellas", []):
        if not a.umbrella or u["name"].lower() == a.umbrella.lower():
            for p in u.get("known_pages", []):
                targets.append((f"{u['name']} page", p, False))

    n = 0
    with out.open("w") as f:
        for name, url, follow in targets:
            try:
                html = fetch(url)
            except Exception as e:
                print(f"skip {name}: {e}", file=sys.stderr)
                continue
            f.write(json.dumps(item(name, url, page_text(html, url), fetched, links_from(html, url)[:40]), ensure_ascii=False) + "\n"); n += 1
            if follow:
                for link in links_from(html, url)[: a.max_links]:
                    try:
                        time.sleep(0.6)
                        h2 = fetch(link)
                        f.write(json.dumps(item(name, link, page_text(h2, link), fetched), ensure_ascii=False) + "\n"); n += 1
                    except Exception as e:
                        print(f"  skip {link}: {e}", file=sys.stderr)
            print(f"{name}: ok")
    print(f"{n} pages → {out}")


if __name__ == "__main__":
    main()
