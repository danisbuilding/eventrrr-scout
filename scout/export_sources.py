#!/usr/bin/env python3
"""Write site/sources.json from sources.yaml so the Sources tab can show it."""
import json
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
src = yaml.safe_load((ROOT / "sources.yaml").read_text())
out = {
    "sites": src.get("sites", []) + src.get("sites_tier2", []),
    "instagram": src.get("instagram", []) + src.get("instagram_tier2", []),
    "umbrellas": [{"name": u["name"], "window": u.get("window"), "known_pages": len(u.get("known_pages", []))} for u in src.get("umbrellas", [])],
    "defaults": src.get("defaults", {}),
}
(ROOT / "site" / "sources.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(f"site/sources.json: {len(out['sites'])} sites, {len(out['instagram'])} IG handles")
