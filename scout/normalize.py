#!/usr/bin/env python3
"""Merge extracted events for a run, dedupe (within the run and against earlier runs), drop past events.

Usage: python scout/normalize.py <run> [--window-from YYYY-MM-DD] [--no-cross-run]
Reads : runs/<run>/extracted/*.json   (arrays of Event objects from extraction)
        runs/<other>/events.json      (earlier runs, for cross-run dedupe)
Writes: runs/<run>/events.json, runs/<run>/dropped.json (what was dropped and why)
"""
import argparse
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def slug(s) -> str:
    if isinstance(s, dict):
        s = s.get("name") or s.get("title") or ""
    elif isinstance(s, list):
        s = " ".join(str(x) for x in s)
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


STOP = {"el", "la", "los", "las", "de", "del", "en", "y", "the", "a", "con", "por", "para", "un", "una",
        "at", "in", "of", "and", "cdmx", "mexico", "ciudad", "edicion", "edition"}


def core_title(title: str) -> str:
    """Title without parentheticals and years (clauses after ' — ' stay: cutting them loses real words)."""
    t = re.sub(r"\([^)]*\)", " ", title or "")
    t = re.sub(r"\b(19|20)\d\d\b", " ", t)
    return t


def tokens(title: str) -> set[str]:
    return {w for w in slug(core_title(title)).split("-") if len(w) > 1 and w not in STOP}


def title_key(title: str) -> str:
    return "-".join(sorted(tokens(title))[:6])


def trigrams(title: str) -> set[str]:
    s = slug(core_title(title)).replace("-", "")
    return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}


GENERIC_VENUE = {"museo", "centro", "cultural", "sala", "foro", "teatro", "casa", "explanada", "plancha", "club",
                 "bar", "galeria", "gallery", "espacio", "parque", "jardin", "auditorio", "universidad"}


def venue_tokens(ev: dict) -> set[str]:
    return {w for w in slug(ev.get("venue") or "").split("-") if len(w) > 2 and w not in STOP and w not in GENERIC_VENUE}


def venues_compatible(a: dict, b: dict) -> bool:
    """Unknown venue on either side is compatible; otherwise they must share a distinctive word."""
    va, vb = venue_tokens(a), venue_tokens(b)
    return not va or not vb or bool(va & vb)


def all_venue_words(ev: dict) -> set[str]:
    return {w for w in slug(ev.get("venue") or "").split("-") if len(w) > 1}


def similar(a: dict, b: dict) -> bool:
    """Same event? Identical title tokens; else a fuzzy match on the title with both venues' words removed
    (so 'Ofrenda en el Museo X' and 'Leyendas | Museo X' don't collide): token containment for added
    words, char-trigram Dice for 'Mega Ofrenda' vs 'Megaofrenda'. Fuzzy matches also need compatible venues."""
    ta, tb = tokens(a.get("title", "")), tokens(b.get("title", ""))
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    if not venues_compatible(a, b):
        return False
    vw = all_venue_words(a) | all_venue_words(b)
    ra, rb = ta - vw, tb - vw
    if not ra or not rb:
        ra, rb = ta, tb
    if ra == rb:
        return True
    inter = len(ra & rb)
    if min(len(ra), len(rb)) >= 2 and inter / min(len(ra), len(rb)) >= 0.75:
        return True
    ga, gb = trigrams(" ".join(sorted(ra))), trigrams(" ".join(sorted(rb)))
    dice = 2 * len(ga & gb) / (len(ga) + len(gb)) if (ga or gb) else 0
    return dice >= 0.85


def span(ev: dict) -> tuple[str, str]:
    s = (ev.get("starts_at") or "")[:10]
    e = (ev.get("ends_at") or "")[:10] or s
    return s, max(s, e)


def dates_touch(a: dict, b: dict) -> bool:
    """Same start day, or overlapping multi-day ranges."""
    sa, ea = span(a)
    sb, eb = span(b)
    if sa == sb:
        return True
    multi = ea > sa or eb > sb
    return multi and sa <= eb and sb <= ea


def event_key(ev: dict) -> str:
    return f"{title_key(ev.get('title', ''))}|{span(ev)[0]}"


def find_match(ev: dict, pool: dict[str, dict]) -> str | None:
    k = event_key(ev)
    if k in pool:
        return k
    for ok, other in pool.items():
        if dates_touch(ev, other) and similar(ev, other):
            return ok
    return None


def merge(a: dict, b: dict) -> dict:
    """Keep the more complete record; union sources; keep best confidence; widest date span."""
    out = dict(a)
    for k, v in b.items():
        if k == "sources":
            out["sources"] = sorted(set(a.get("sources", [])) | set(v or []))
        elif k == "source_links":
            seen = {(l.get("name"), l.get("url")) for l in a.get("source_links") or []}
            out["source_links"] = (a.get("source_links") or []) + [l for l in (v or []) if (l.get("name"), l.get("url")) not in seen]
        elif k == "signals":
            s = dict(a.get("signals") or {})
            for sk, sv in (v or {}).items():
                s[sk] = s.get(sk, False) or bool(sv)
            out["signals"] = s
        elif out.get(k) in (None, "", [], False) and v not in (None, "", []):
            out[k] = v
    if b.get("ends_at") and (not a.get("ends_at") or b["ends_at"] > a["ends_at"]):
        out["ends_at"] = b["ends_at"]
    out["confidence"] = max(a.get("confidence", 0) or 0, b.get("confidence", 0) or 0)
    return out


def earlier_runs(run: str) -> dict[str, dict]:
    """Events from every other published run, keyed by run|key, for cross-run dedupe."""
    pool: dict[str, dict] = {}
    idx = ROOT / "runs" / "index.json"
    if not idx.exists():
        return pool
    for r in json.loads(idx.read_text()).get("runs", []):
        name = r.get("run")
        if not name or name == run or name.startswith("sample"):
            continue
        f = ROOT / "runs" / name / "events.json"
        if f.exists():
            for ev in json.loads(f.read_text()):
                pool[f"{name}|{ev['key']}"] = ev
    return pool


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--window-from", default=dt.date.today().isoformat(), help="drop events that end before this date")
    ap.add_argument("--no-cross-run", action="store_true")
    a = ap.parse_args()
    run_dir = ROOT / "runs" / a.run
    src = run_dir / "extracted"
    by_key: dict[str, dict] = {}
    dropped: list[dict] = []
    n_in = 0
    for f in sorted(src.glob("*.json")):
        for ev in json.loads(f.read_text()):
            n_in += 1
            if not ev.get("starts_at") or not ev.get("title"):
                dropped.append({"title": ev.get("title"), "reason": "no_date_or_title"})
                continue
            if span(ev)[1] < a.window_from:
                dropped.append({"title": ev.get("title"), "starts_at": ev.get("starts_at"), "reason": "past"})
                continue
            k = find_match(ev, by_key) or event_key(ev)
            ev["key"] = k
            by_key[k] = merge(by_key[k], ev) if k in by_key else ev

    n_dup = 0
    if not a.no_cross_run:
        prior = earlier_runs(a.run)
        for k in list(by_key):
            m = find_match(by_key[k], prior)
            if m:
                prun, pkey = m.split("|", 1)
                dropped.append({"title": by_key[k]["title"], "starts_at": by_key[k]["starts_at"], "reason": "seen_in", "run": prun, "key": pkey})
                del by_key[k]
                n_dup += 1

    events = list(by_key.values())
    for ev in events:
        names = {s.split(":")[1] for s in ev.get("sources", []) if s.count(":") >= 2}
        ev.setdefault("signals", {})["corroborated"] = len(names) >= 2
        ev["source_count"] = len(names)

    events.sort(key=lambda e: (e.get("starts_at") or "", e.get("title") or ""))
    (run_dir / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=1))
    (run_dir / "dropped.json").write_text(json.dumps(dropped, ensure_ascii=False, indent=1))
    n_past = sum(1 for d in dropped if d["reason"] == "past")
    print(f"{n_in} extracted → {len(events)} unique events ({n_past} past, {n_dup} seen in earlier runs dropped) → {run_dir/'events.json'}")


if __name__ == "__main__":
    main()
