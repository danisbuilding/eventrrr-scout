#!/usr/bin/env python3
"""Fetch flyer thumbnails as data: URIs so the dashboard can show them (artifacts can't
load external images). Runs on the Mac (needs network). Usage: python scout/thumbs.py <run>
Reads/writes runs/<run>/events.json in place: image_url -> thumb (JPEG, 480px wide).
Deps: pip install pillow requests
"""
import base64, io, json, sys
from pathlib import Path
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "runs" / sys.argv[1] / "events.json"
events = json.loads(p.read_text()); n = 0
for e in events:
    if e.get("thumb") or not e.get("image_url"):
        continue
    try:
        r = requests.get(e["image_url"], timeout=15, headers={"User-Agent": "Mozilla/5.0"}); r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        im.thumbnail((480, 640))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=72)
        e["thumb"] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(); n += 1
    except Exception as ex:
        print(f"skip {e.get('title')}: {ex}", file=sys.stderr)
p.write_text(json.dumps(events, ensure_ascii=False, indent=1)); print(f"{n} thumbnails added")
