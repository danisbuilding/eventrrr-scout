#!/usr/bin/env python3
"""Render a self-contained dashboard for a run from the site/ UI (for an Artifact or a mock).

Usage: python scout/render.py <run> [--window "..."] [--umbrella "..."]
Reads : runs/<run>/events.json, taxonomy.yaml, site/styles.css, site/app.js
Writes: runs/<run>/dashboard.html  (inline data, decisions in localStorage)
        site/categories.js         (regenerated from taxonomy.yaml)

The live site at scout.eventrrr.com uses the same site/ files with Supabase; publish a run
there with the `publish` workflow instead.
"""
import argparse
import json
import re
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
    (ROOT / "site" / "categories.js").write_text("// Generated from taxonomy.yaml by scout/render.py; do not edit.\nwindow.SCOUT_CATEGORIES = " + json.dumps(cats, ensure_ascii=False) + ";\n")

    meta = {"run": a.run, "window": a.window, "umbrella": a.umbrella, "categories": cats}
    index = (ROOT / "site" / "index.html").read_text()
    body = re.search(r"<body>([\s\S]*)</body>", index).group(1)
    body = re.sub(r'<script src="app.js"></script>', "", body)
    css = (ROOT / "site" / "styles.css").read_text()
    js = (ROOT / "site" / "app.js").read_text()
    inline = json.dumps({"meta": meta, "events": events}, ensure_ascii=False).replace("</", "<\\/")
    html = (
        "<title>Eventrrr Scout</title>\n"
        '<meta name="claude:viewport-fit-sides" content="cover">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400&display=swap">\n'
        f"<style>\n{css}\n</style>\n{body}\n"
        f"<script>window.SCOUT_CATEGORIES = {json.dumps(cats, ensure_ascii=False)}; window.SCOUT_INLINE = {inline};</script>\n"
        f"<script>\n{js}\n</script>\n"
    )
    out = run_dir / "dashboard.html"
    out.write_text(html)
    print(f"wrote {out} ({len(events)} events, {sum(1 for e in events if e.get('highlight'))} highlights)")


if __name__ == "__main__":
    main()
