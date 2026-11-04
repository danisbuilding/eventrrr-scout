#!/usr/bin/env python3
"""Nightly session dump: current_assignments (and None / Can't tell reviews) from Scout IQ → profiles/sessions/<date>.json,
in the shape the Sort tab's "Copy session" produces, so the sorting chat reads the repo instead of a paste.

Usage: python scout/iq_session_dump.py [--date YYYY-MM-DD] [--force]
Writes profiles/sessions/<date>.json only when something changed since the newest dump (assignment and review
counts, newest row); prints "unchanged" otherwise. The workflow commits the file when it exists.
Needs SCOUT_IQ_DB_URL (scout_pipeline role).
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "profiles" / "sessions"
SCALE = {"5": "Singular. Not to be missed.", "4": "Great. Prioritize over other things.", "3": "Good. Worth going if you're free.",
         "2": "Fine. Maybe go or not.", "1": "Mediocre. Lean toward skipping."}
STATE = ROOT / "profiles" / "sessions" / ".dump-state.json"


def charter_version(slug: str) -> str | None:
    f = ROOT / "profiles" / f"{slug}.md"
    if not f.exists():
        return None
    m = re.search(r"^charter_version:\s*(\S+)", f.read_text(), re.M)
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone(dt.timedelta(hours=-6))).date().isoformat())
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    url = os.environ.get("SCOUT_IQ_DB_URL", "").strip()
    if not url:
        sys.exit("SCOUT_IQ_DB_URL not set")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("""select (select count(*) from assignments), (select count(*) from reviews),
                              greatest((select max(created_at) from assignments), (select max(created_at) from reviews))""")
        n_a, n_r, newest = cur.fetchone()
        sig = {"assignments": n_a, "reviews": n_r, "newest": newest.isoformat() if newest else None}
        prev = json.loads(STATE.read_text()) if STATE.exists() else {}
        if not a.force and prev == sig:
            print("unchanged since the last dump")
            return

        cur.execute("select slug, display_name, persona, charter_version from profiles where active order by sort_order")
        profiles = [{"slug": s, "name": n, "persona": p, "charter_version": charter_version(s) or cv} for s, n, p, cv in cur.fetchall()]

        cur.execute("""select aa.run, aa.key, aa.profile, aa.score, aa.score_actor, aa.charter_version, aa.source, aa.note, aa.updated_at,
                              e.title, e.eventrrr_category, e.venue_text, e.neighborhood, e.price_text, e.starts_at, e.ends_at, e.all_day,
                              (e.rubric_score >= 7) as highlight, e.url,
                              (select raw_excerpt from observations o join event_merges m on m.observation_id = o.id
                               where m.event_id = e.id and m.unmerged_at is null order by o.observed_at limit 1) as source_excerpt
                       from app_assignments aa join events e on e.key = aa.key
                       order by aa.updated_at""")
        cols = ["run", "key", "profile", "score", "score_actor", "charter_version", "source", "note", "updated_at", "title", "category",
                "venue", "neighborhood", "price_text", "starts_at", "ends_at", "all_day", "highlight", "url", "source_excerpt"]
        rows = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            for k in ("updated_at", "starts_at", "ends_at"):
                if d[k] is not None:
                    d[k] = d[k].isoformat()
            if d["score"] is None:
                d["score_actor"] = None
            rows.append(d)

        cur.execute("""select ar.run, ar.key, ar.skip_reason, ar.reviewed_at from app_reviews ar
                       where ar.skip_reason in ('none', 'unclear') order by ar.reviewed_at""")
        for run, key, reason, at in cur.fetchall():
            rows.append({"run": run, "key": key, "profile": reason, "score": None, "score_actor": None, "charter_version": None,
                         "source": "manual", "note": None, "updated_at": at.isoformat()})

        cur.execute("""select count(*) from events e
                       where e.id not in (select o.event_id from occurrences o join current_assignments ca on ca.occurrence_id = o.id)
                         and e.id not in (select event_id from current_reviews)
                         and coalesce(e.ends_at, e.starts_at) >= now() - interval '1 day'""")
        unsorted = cur.fetchone()[0]

    out = {"session": a.date, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "source": "scout-iq nightly dump",
           "scale": SCALE, "profiles": profiles, "assignments": rows, "unsorted_count": unsorted}
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{a.date}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    STATE.write_text(json.dumps(sig))
    print(f"{f.relative_to(ROOT)}: {len(rows)} rows ({n_a} assignment rows in IQ, {n_r} reviews), {unsorted} unsorted")


if __name__ == "__main__":
    main()
