#!/usr/bin/env python3
"""Parallel LLM scouts: ask OpenAI and Gemini (with web search on) the same event
questions and write their answers as RawItems. Runs on DP's Mac (needs network + keys).

Usage:
  python scouts/run_scouts.py <run> --window-from 2026-10-28 --window-to 2026-11-11 \
      [--umbrella "Día de Muertos 2026"] [--only openai|gemini]

Keys: scouts/.env with OPENAI_API_KEY and/or GEMINI_API_KEY (never committed).
Output: inbox/<run>/llm_scout_openai.jsonl, inbox/<run>/llm_scout_gemini.jsonl
Deps: pip install openai google-genai python-dotenv pyyaml
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "scouts" / ".env")
except ImportError:
    pass

PROMPT = """You are an event scout for Mexico City. Today is {today}.
List real, dated, public events in Mexico City between {wfrom} and {wto}{umb}.
Cover these categories: {cats}.
Search the web; prefer organizer pages, venue agendas, ticket pages and reputable listings.
For each event give: title (as published), date, start time if known, venue, neighborhood (colonia),
price, a URL, and the category. Aim for 40+ distinct events. Skip anything you cannot date.
Return ONLY a JSON array of objects with keys:
title, date (YYYY-MM-DD), time (HH:MM or null), venue, neighborhood, price_text, url, category, note."""


def questions(args, cats):
    umb = f", with special attention to {args.umbrella}" if args.umbrella else ""
    base = PROMPT.format(today=dt.date.today().isoformat(), wfrom=args.window_from, wto=args.window_to, umb=umb, cats="; ".join(cats))
    # One broad pass plus one pass per category keeps each answer focused and under output limits.
    qs = [("broad", base)]
    for c in cats:
        if c == "Other":
            continue
        qs.append((c, base + f"\n\nFor this pass, list ONLY events in the category: {c}. Aim for 15+."))
    return qs


def to_items(model, label, text, fetched):
    try:
        start, end = text.find("["), text.rfind("]")
        rows = json.loads(text[start:end + 1])
    except Exception:
        rows = [{"raw": text}]
    items = []
    for r in rows:
        body = json.dumps(r, ensure_ascii=False)
        h = hashlib.sha1(body.encode()).hexdigest()[:12]
        items.append({
            "id": f"llm_scout:{model}:{h}",
            "source_type": "llm_scout",
            "source_name": model,
            "source_url": r.get("url") if isinstance(r, dict) else None,
            "fetched_at": fetched,
            "text": body,
            "links": [r["url"]] if isinstance(r, dict) and r.get("url") else [],
            "meta": {"pass": label},
        })
    return items


def ask_openai(q):
    from openai import OpenAI
    client = OpenAI()
    r = client.responses.create(model=os.getenv("OPENAI_SCOUT_MODEL", "gpt-5"), tools=[{"type": "web_search"}], input=q)
    return r.output_text


def ask_gemini(q):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    r = client.models.generate_content(
        model=os.getenv("GEMINI_SCOUT_MODEL", "gemini-2.5-pro"),
        contents=q,
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
    )
    return r.text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--window-from", required=True)
    ap.add_argument("--window-to", required=True)
    ap.add_argument("--umbrella", default="")
    ap.add_argument("--only", choices=["openai", "gemini"])
    args = ap.parse_args()

    cats = [c["name"] for c in yaml.safe_load((ROOT / "taxonomy.yaml").read_text())["categories"]]
    out_dir = ROOT / "inbox" / args.run
    out_dir.mkdir(parents=True, exist_ok=True)
    scouts = {"openai": ask_openai, "gemini": ask_gemini}
    if args.only:
        scouts = {args.only: scouts[args.only]}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    jobs = []
    for name, fn in scouts.items():
        key = "OPENAI_API_KEY" if name == "openai" else "GEMINI_API_KEY"
        if not os.getenv(key):
            print(f"skip {name}: {key} not set", file=sys.stderr)
            continue
        for label, q in questions(args, cats):
            jobs.append((name, fn, label, q))
    results = {}
    with ThreadPoolExecutor(max_workers=int(os.getenv("SCOUT_WORKERS", "8"))) as ex:
        futs = {ex.submit(fn, q): (name, label) for name, fn, label, q in jobs}
        for fut in as_completed(futs):
            name, label = futs[fut]
            try:
                results.setdefault(name, []).append((label, fut.result()))
                print(f"{name}/{label}: ok")
            except Exception as e:
                print(f"{name}/{label}: {e}", file=sys.stderr)
    fetched = dt.datetime.now(dt.timezone.utc).isoformat()
    for name, outs in results.items():
        out = out_dir / f"llm_scout_{name}.jsonl"
        n = 0
        with out.open("w") as f:
            for label, text in outs:
                for it in to_items(name, label, text, fetched):
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
                    n += 1
        print(f"{name}: {n} items → {out}")


if __name__ == "__main__":
    main()
