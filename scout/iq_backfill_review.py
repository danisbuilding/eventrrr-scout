#!/usr/bin/env python3
"""One-time migration of the review side from Eventrrr's Supabase (scout_* tables) into Scout IQ.

Usage: python scout/iq_backfill_review.py profiles/sessions/<snapshot>.json [--dry-run]
The snapshot is a JSON dump of the old tables, pulled from the signed-in Scout app:
  {"scout_profiles": [...], "scout_assignments": [...], "scout_decisions": [...], "scout_exports": [...],
   "scout_reviewers": [...]}
Writes through SCOUT_IQ_DB_URL (scout_pipeline role), after scout_iq_review.sql has run and iq_write.py has
written every run the rows refer to. Idempotent: a row is skipped when an identical one (same occurrence,
profile, score/withdrawn, created_at) already exists.

Mapping (Scout IQ: Database Spec v1, "Backfill carries no scores" / "Legacy rows carry no score"):
  scout_profiles                       → profiles (charter_version from profiles/<slug>.md frontmatter)
  scout_reviewers                      → reviewers
  scout_assignments, profile = a slug  → assignments (actor human, created_at = old updated_at;
                                          score null → legacy = true; nothing inferred from Keep/Skip or highlight)
  scout_assignments, profile none|unclear → reviews (skip_reason none|unclear)
  scout_decisions                      → reviews (decision keep|skip, note; note 'duplicate' → skip_reason duplicate)
  scout_exports                        → export_ledger
Rows whose (run, key) is not in Scout IQ are reported and skipped.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def charter_version(slug: str) -> str | None:
    f = ROOT / "profiles" / f"{slug}.md"
    if not f.exists():
        return None
    m = re.search(r"^charter_version:\s*(\S+)", f.read_text(), re.M)
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    snap = json.loads(Path(a.snapshot).read_text())
    profiles = snap.get("scout_profiles") or []
    assigns = snap.get("scout_assignments") or []
    decisions = snap.get("scout_decisions") or []
    exports = snap.get("scout_exports") or []
    reviewers = snap.get("scout_reviewers") or []
    print(f"snapshot: {len(profiles)} profiles, {len(assigns)} assignments, {len(decisions)} decisions, {len(exports)} exports, {len(reviewers)} reviewers")
    url = os.environ.get("SCOUT_IQ_DB_URL", "").strip()
    if a.dry_run or not url:
        if not url:
            print("SCOUT_IQ_DB_URL not set: nothing written", file=sys.stderr)
        return

    import psycopg
    default_email = (reviewers[0]["email"] if reviewers else "accounts@danielstringer.com").lower()
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        rev_ids = {}
        for r in reviewers:
            cur.execute("insert into reviewers (email) values (%s) on conflict (email) do update set active = true returning id", (r["email"].lower(),))
            rev_ids[r["email"].lower()] = cur.fetchone()[0]
        def reviewer(email):
            e = (email or default_email).lower()
            if e not in rev_ids:
                cur.execute("select id from reviewers where email = %s", (e,))
                row = cur.fetchone()
                rev_ids[e] = row[0] if row else rev_ids.get(default_email)
            return rev_ids[e]

        prof_ids = {}
        for p in profiles:
            cur.execute("""insert into profiles (slug, display_name, persona, handle, charter_path, charter_version, kind, ends_on, active, sort_order, created_at, updated_at)
                           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()), coalesce(%s, now()))
                           on conflict (slug) do update set display_name = excluded.display_name, persona = excluded.persona, handle = excluded.handle,
                             charter_version = coalesce(excluded.charter_version, profiles.charter_version), kind = excluded.kind, ends_on = excluded.ends_on,
                             active = excluded.active, sort_order = excluded.sort_order, updated_at = now()
                           returning id""",
                        (p["slug"], p["name"], p.get("persona"), p.get("handle"), f"profiles/{p['slug']}.md", charter_version(p["slug"]),
                         p.get("kind") or "ongoing", p.get("ends_on"), p.get("active", True), p.get("sort_order", 100), p.get("created_at"), p.get("updated_at")))
            prof_ids[p["slug"]] = cur.fetchone()[0]

        cur.execute("select key, event_id, occurrence_id from app_event_keys")
        keys = {k: (e, o) for k, e, o in cur.fetchall()}
        missing = set()
        n_assign = n_review = n_export = n_skip = 0

        for x in sorted(assigns, key=lambda r: r.get("updated_at") or ""):
            k = x["key"]
            if k not in keys:
                missing.add((x["run"], k)); continue
            ev_id, occ_id = keys[k]
            rid = reviewer(x.get("updated_by"))
            if x["profile"] in ("none", "unclear"):
                cur.execute("""insert into reviews (event_id, reviewer_id, reviewed_at, skip_reason, note)
                               select %s, %s, %s, %s, %s where not exists
                                 (select 1 from reviews where event_id = %s and reviewed_at = %s and skip_reason = %s)""",
                            (ev_id, rid, x.get("updated_at"), x["profile"], x.get("note"), ev_id, x.get("updated_at"), x["profile"]))
                n_review += cur.rowcount
                continue
            pid = prof_ids.get(x["profile"])
            if not pid:
                n_skip += 1; continue
            score = x.get("score")
            cur.execute("""insert into assignments (occurrence_id, profile_id, score, actor, actor_id, charter_version, legacy, source, note, created_at)
                           select %s, %s, %s, 'human', %s, %s, %s, %s, %s, %s where not exists
                             (select 1 from assignments where occurrence_id = %s and profile_id = %s and created_at = %s and actor = 'human')""",
                        (occ_id, pid, score, rid, x.get("charter_version") if score is not None else None, score is None,
                         x.get("source") or "manual", x.get("note"), x.get("updated_at"), occ_id, pid, x.get("updated_at")))
            n_assign += cur.rowcount

        for d in decisions:
            k = d["key"]
            if k not in keys:
                missing.add((d["run"], k)); continue
            ev_id, _ = keys[k]
            note = d.get("note")
            reason = "duplicate" if (note or "").lower().startswith("duplicate") else ("skip" if d.get("decision") == "skip" else None)
            cur.execute("""insert into reviews (event_id, reviewer_id, reviewed_at, decision, skip_reason, note)
                           select %s, %s, %s, %s, %s, %s where not exists
                             (select 1 from reviews where event_id = %s and reviewed_at = %s)""",
                        (ev_id, reviewer(d.get("updated_by")), d.get("updated_at"), d.get("decision"), reason, note, ev_id, d.get("updated_at")))
            n_review += cur.rowcount

        for x in exports:
            k = x["key"]
            if k not in keys or x["profile"] not in prof_ids:
                missing.add((x["run"], k)); continue
            cur.execute("""insert into export_ledger (profile_id, occurrence_id, batch, exported_by, exported_at)
                           values (%s, %s, %s, %s, coalesce(%s, now())) on conflict (profile_id, occurrence_id) do nothing""",
                        (prof_ids[x["profile"]], keys[k][1], x["batch"], x.get("exported_by"), x.get("exported_at")))
            n_export += cur.rowcount
        conn.commit()
    print(f"written: {n_assign} assignments, {n_review} reviews, {n_export} exports; {n_skip} rows for unknown profiles skipped")
    if missing:
        print(f"{len(missing)} (run, key) not in Scout IQ, skipped:")
        for run, k in sorted(missing):
            print(f"  {run} | {k}")


if __name__ == "__main__":
    main()
