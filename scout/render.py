#!/usr/bin/env python3
"""Render the review dashboard for a run.

Usage: python scout/render.py <run> [--window "Oct 28 – Nov 11" --umbrella "Día de Muertos 2026"]
Reads : runs/<run>/events.json, taxonomy.yaml, scout/dashboard_template.html
Writes: runs/<run>/dashboard.html   (then Claude publishes it as an Artifact)
"""
import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--window", default="")
    ap.add_argument("--umbrella", default="")
    a = ap.parse_args()

    run_dir = ROOT / "runs" / a.run
    events = json.loads((run_dir / "events.json").read_text())
    tax = yaml.safe_load((ROOT / "taxonomy.yaml").read_text())
    cats = [c["name"] for c in tax["categories"]]

    meta = {
        "run": a.run,
        "window": a.window,
        "umbrella": a.umbrella,
        "categories": cats,
        "threshold": tax["highlight"]["threshold"],
        "counts": {
            "events": len(events),
            "highlights": sum(1 for e in events if e.get("highlight")),
            "family": sum(1 for e in events if e.get("family_friendly")),
        },
    }
    tpl = (ROOT / "scout" / "dashboard_template.html").read_text()
    html = (
        tpl.replace("__META__", json.dumps(meta, ensure_ascii=False))
        .replace("__EVENTS__", json.dumps(events, ensure_ascii=False).replace("</", "<\\/"))
    )
    out = run_dir / "dashboard.html"
    out.write_text(html)
    print(f"wrote {out} ({len(events)} events, {meta['counts']['highlights']} highlights)")


if __name__ == "__main__":
    main()
