#!/usr/bin/env python3
"""Register a run so scout.eventrrr.com can show it: updates runs/index.json (commit + push after).

Usage: python scout/publish.py <run> [--window "Oct 28 – Nov 11"] [--umbrella NAME] [--hide]
The site reads runs/index.json and runs/<run>/events.json from the public repo; no secrets.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDX = ROOT / "runs" / "index.json"

ap = argparse.ArgumentParser()
ap.add_argument("run"); ap.add_argument("--window", default=""); ap.add_argument("--umbrella", default=""); ap.add_argument("--hide", action="store_true")
a = ap.parse_args()
events = json.loads((ROOT / "runs" / a.run / "events.json").read_text())
idx = json.loads(IDX.read_text()) if IDX.exists() else {"runs": []}
idx["runs"] = [r for r in idx["runs"] if r["run"] != a.run]
idx["runs"].insert(0, {"run": a.run, "window": a.window, "umbrella": a.umbrella or None, "event_count": len(events),
                       "highlights": sum(1 for e in events if e.get("highlight")), "published_at": dt.datetime.now(dt.timezone.utc).isoformat(), "hidden": a.hide})
IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
print(f"runs/index.json: {a.run} ({len(events)} events). Commit and push to publish.")
