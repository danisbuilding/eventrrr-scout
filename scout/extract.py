#!/usr/bin/env python3
"""LLM extraction: RawItems (inbox/<run>/*.jsonl) → events (runs/<run>/extracted/<source>.json).

Usage: python scout/extract.py <run> --window-from D --window-to D [--umbrella NAME]
Env:   OPENAI_API_KEY (primary; model OPENAI_EXTRACT_MODEL, default gpt-5) or GEMINI_API_KEY (fallback)
Uses prompts/extract.md + taxonomy.yaml. Batches raw items by size so each call stays small.
"""
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BATCH_CHARS = 28000  # ~7k tokens of source text per call


def build_system(args, tax):
    prompt = (ROOT / "prompts" / "extract.md").read_text()
    prompt = prompt.replace("{{window_from}}", args.window_from).replace("{{window_to}}", args.window_to).replace("{{umbrella}}", args.umbrella or "none")
    cats = "\n".join(f"- {c['name']}: {c['def']}" for c in tax["categories"])
    sigs = "\n".join(f"- {k}: {v['def']}" for k, v in {**tax["highlight"]["signals"], **tax["highlight"]["penalties"]}.items())
    today = dt.date.today().isoformat()
    return f"""{prompt}

Today is {today}. Categories (use the name exactly):
{cats}

Signals and penalties (set each true/false in `signals`):
{sigs}

Also set `highlight_why`: one concrete sentence on why this event is or isn't worth featuring.
Return a JSON object: {{"events": [ ...Event objects... ]}}. Nothing else."""


def call_openai(system, user):
    from openai import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model=os.getenv("OPENAI_EXTRACT_MODEL", "gpt-5"),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
    )
    return r.choices[0].message.content


def call_gemini(system, user):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    r = client.models.generate_content(model=os.getenv("GEMINI_EXTRACT_MODEL", "gemini-2.5-pro"), contents=user,
                                       config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json"))
    return r.text


def parse(text):
    try:
        obj = json.loads(text)
    except Exception:
        s, e = text.find("{"), text.rfind("}")
        obj = json.loads(text[s:e + 1])
    return obj.get("events", obj if isinstance(obj, list) else [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run"); ap.add_argument("--window-from", required=True); ap.add_argument("--window-to", required=True); ap.add_argument("--umbrella", default="")
    a = ap.parse_args()
    tax = yaml.safe_load((ROOT / "taxonomy.yaml").read_text())
    system = build_system(a, tax)
    call = call_openai if os.getenv("OPENAI_API_KEY") else (call_gemini if os.getenv("GEMINI_API_KEY") else None)
    if not call:
        sys.exit("no OPENAI_API_KEY or GEMINI_API_KEY")

    inbox = ROOT / "inbox" / a.run
    out_dir = ROOT / "runs" / a.run / "extracted"
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for jl in sorted(inbox.glob("*.jsonl")):
        items = [json.loads(l) for l in jl.read_text().splitlines() if l.strip()]
        batches, cur, size = [], [], 0
        for it in items:
            slim = {k: it.get(k) for k in ("id", "source_name", "source_url", "author", "posted_at", "text", "links", "media")}
            slim["text"] = (slim.get("text") or "")[:9000]
            if size + len(slim["text"]) > BATCH_CHARS and cur:
                batches.append(cur); cur, size = [], 0
            cur.append(slim); size += len(slim["text"])
        if cur:
            batches.append(cur)
        events = []
        for i, b in enumerate(batches):
            user = "Raw items (JSON). Extract every dated event:\n" + json.dumps(b, ensure_ascii=False)
            try:
                evs = parse(call(system, user))
                for e in evs:
                    e.setdefault("sources", [x["id"] for x in b][:1])
                    e.setdefault("source_links", [{"name": b[0].get("source_name"), "url": b[0].get("source_url")}])
                events.extend(evs)
                print(f"{jl.name} batch {i + 1}/{len(batches)}: {len(evs)} events")
            except Exception as e:
                print(f"{jl.name} batch {i + 1}: {e}", file=sys.stderr)
        (out_dir / f"{jl.stem}.json").write_text(json.dumps(events, ensure_ascii=False, indent=1))
        total += len(events)
    print(f"{total} events extracted → {out_dir}")


if __name__ == "__main__":
    main()
