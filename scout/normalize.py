#!/usr/bin/env python3
"""Merge extracted events for a run, dedupe, set corroboration.

Usage: python scout/normalize.py <run>
Reads : runs/<run>/extracted/*.json   (arrays of Event objects from extraction)
Writes: runs/<run>/events.json
"""
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


STOP = {"el", "la", "los", "las", "de", "del", "en", "y", "the", "a", "con", "por", "para", "un", "una",
        "at", "in", "of", "and", "cdmx", "mexico", "ciudad"}


def tokens(title: str) -> set[str]:
    return {w for w in slug(title).split("-") if len(w) > 1 and w not in STOP and not re.fullmatch(r"(19|20)\d\d", w)}


def title_key(title: str) -> str:
    return "-".join(sorted(tokens(title))[:6])


def event_key(ev: dict) -> str:
    date = (ev.get("starts_at") or "")[:10]
    return f"{title_key(ev.get('title', ''))}|{date}"


def find_match(ev: dict, by_key: dict[str, dict], threshold: float = 0.6) -> str | None:
    """Exact key, else same-day fuzzy token overlap (Jaccard)."""
    k = event_key(ev)
    if k in by_key:
        return k
    date = k.split("|")[1]
    t = tokens(ev.get("title", ""))
    best, best_j = None, 0.0
    for ok, other in by_key.items():
        if ok.split("|")[1] != date or not t:
            continue
        ot = tokens(other.get("title", ""))
        j = len(t & ot) / len(t | ot) if (t | ot) else 0
        if j > best_j:
            best, best_j = ok, j
    return best if best_j >= threshold else None


def merge(a: dict, b: dict) -> dict:
    """Keep the more complete record; union sources; keep best confidence."""
    out = dict(a)
    for k, v in b.items():
        if k == "sources":
            out["sources"] = sorted(set(a.get("sources", [])) | set(v or []))
        elif k == "signals":
            s = dict(a.get("signals") or {})
            for sk, sv in (v or {}).items():
                s[sk] = s.get(sk, False) or bool(sv)
            out["signals"] = s
        elif out.get(k) in (None, "", [], False) and v not in (None, "", []):
            out[k] = v
    out["confidence"] = max(a.get("confidence", 0) or 0, b.get("confidence", 0) or 0)
    return out


def main(run: str) -> None:
    run_dir = ROOT / "runs" / run
    src = run_dir / "extracted"
    by_key: dict[str, dict] = {}
    n_in = 0
    for f in sorted(src.glob("*.json")):
        for ev in json.loads(f.read_text()):
            n_in += 1
            k = find_match(ev, by_key) or event_key(ev)
            ev["key"] = k
            by_key[k] = merge(by_key[k], ev) if k in by_key else ev

    events = list(by_key.values())
    for ev in events:
        # corroboration = distinct source_name count, derived from RawItem ids "<type>:<name>:<id>"
        names = {s.split(":")[1] for s in ev.get("sources", []) if s.count(":") >= 2}
        ev.setdefault("signals", {})["corroborated"] = len(names) >= 2
        ev["source_count"] = len(names)

    events.sort(key=lambda e: (e.get("starts_at") or "", e.get("title") or ""))
    (run_dir / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=1))
    print(f"{n_in} extracted → {len(events)} unique events → {run_dir/'events.json'}")


if __name__ == "__main__":
    main(sys.argv[1])
