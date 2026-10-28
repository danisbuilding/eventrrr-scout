#!/usr/bin/env python3
"""Score events against taxonomy.yaml highlight rubric.

Usage: python scout/score.py <run>
Reads/writes runs/<run>/events.json in place. Also reads decisions/*.json for a
disagreement report (score said yes, DP said Skip, and vice versa).
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main(run: str) -> None:
    tax = yaml.safe_load((ROOT / "taxonomy.yaml").read_text())
    rub = tax["highlight"]
    weights = {k: v["weight"] for k, v in rub["signals"].items()}
    weights.update({k: v["weight"] for k, v in rub["penalties"].items()})
    thr = rub["threshold"]

    p = ROOT / "runs" / run / "events.json"
    events = json.loads(p.read_text())
    for ev in events:
        sig = ev.get("signals") or {}
        if ev.get("recurring"):
            sig["recurring_weekly"] = True
        if not ev.get("url") or not ev.get("venue"):
            sig["vague"] = True
        score = sum(w for k, w in weights.items() if sig.get(k))
        ev["signals"] = sig
        ev["score"] = score
        ev["highlight"] = score >= thr
    p.write_text(json.dumps(events, ensure_ascii=False, indent=1))

    n_hi = sum(e["highlight"] for e in events)
    print(f"{len(events)} events scored, {n_hi} highlighted (threshold {thr})")

    # Disagreement report against past decisions, if any
    past = {}
    for f in sorted((ROOT / "decisions").glob("*.json")):
        for k, d in json.loads(f.read_text()).get("decisions", {}).items():
            past[k] = d
    if past:
        fp = [e for e in events if e["highlight"] and past.get(e["key"], {}).get("decision") == "skip"]
        fn = [e for e in events if not e["highlight"] and past.get(e["key"], {}).get("decision") == "keep"]
        print(f"vs past decisions: {len(fp)} highlighted-but-skipped, {len(fn)} kept-but-not-highlighted")


if __name__ == "__main__":
    main(sys.argv[1])
