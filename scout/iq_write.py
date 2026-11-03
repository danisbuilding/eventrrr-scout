#!/usr/bin/env python3
"""Dual-write a published run into Scout IQ (DP's own Supabase project), pipeline side only.

Usage: python scout/iq_write.py <run> [--dry-run]
Reads : runs/<run>/extracted/*.json (observations), runs/<run>/events.json (canonical events, after score +
        venues), runs/<run>/dropped.json (observations that merged into an earlier run's event), runs/index.json,
        inbox/<run>/*.jsonl (observed_at and source URL per raw item), sources.yaml, data/venues.json
Writes: runs, sources, observations, events, event_merges, occurrences, venues, organizers in the project named by
        SCOUT_IQ_DB_URL (a postgresql:// URL for the scoped `scout_pipeline` role, through the session pooler).

Idempotent: observation ids are uuid5 of run|file|index, events upsert on `key`, occurrences on (event, kind,
starts_at), venues on google_place_id or (city, name), sources on (kind, handle); running it twice changes nothing.
Without SCOUT_IQ_DB_URL it prints the counts and exits 0, so the pipeline never fails on it.

Mapping (Scout IQ: Database Spec v1):
  one extracted record            → one observation (+ one live event_merges row)
  one events.json record          → one event (key = normalize.py key) + its `run` occurrence
  dropped.json reason seen_in     → observation merged into the earlier run's event (by key)
  events.json `continues`         → merged into the original event; its occurrence widened; no new event row
  venue_place / data/venues.json  → venues (google_place_id, google_rating, google_reviews) and events.venue_id
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NS = uuid.UUID("6b0a8d3e-5c1e-4b7a-9a1e-7c2d1f0e9a55")  # namespace for deterministic ids
CITY_SLUG = "cdmx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from venues import venue_query, fold  # noqa: E402


def uid(*parts) -> uuid.UUID:
    return uuid.uuid5(NS, "|".join(str(p) for p in parts))


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_run(run: str) -> dict:
    d = ROOT / "runs" / run
    extracted = []
    for f in sorted((d / "extracted").glob("*.json")):
        for i, rec in enumerate(json.loads(f.read_text())):
            extracted.append((f.name, i, rec))
    events = json.loads((d / "events.json").read_text())
    dropped = json.loads((d / "dropped.json").read_text()) if (d / "dropped.json").exists() else []
    inbox = {}
    for f in (ROOT / "inbox" / run).glob("*.jsonl") if (ROOT / "inbox" / run).exists() else []:
        for line in f.read_text(errors="replace").splitlines():
            try:
                it = json.loads(line)
                inbox[it["id"]] = it
            except (ValueError, KeyError, TypeError):
                continue  # a few inbox lines are corrupt (run 2026-11-03 was finished by hand); observed_at then falls back
    meta = next((r for r in json.loads((ROOT / "runs" / "index.json").read_text()).get("runs", []) if r["run"] == run), {})
    return {"extracted": extracted, "events": events, "dropped": dropped, "inbox": inbox, "meta": meta}


def window(meta: dict) -> tuple[str | None, str | None]:
    m = re.findall(r"\d{4}-\d{2}-\d{2}", meta.get("window") or "")
    return (m[0], m[1]) if len(m) >= 2 else (None, None)


def source_of(rec: dict) -> tuple[str, str] | None:
    """('website'|'instagram'|…, handle_or_url) from the first raw-item id 'web:<slug>:<hash>'."""
    for s in rec.get("sources") or []:
        parts = s.split(":", 2)
        if len(parts) == 3:
            kind, name = parts[0], parts[1]
            return ({"web": "website", "ig": "instagram"}.get(kind, kind), name)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    url = os.environ.get("SCOUT_IQ_DB_URL", "").strip()
    data = load_run(a.run)
    ex, events, dropped, inbox, meta = data["extracted"], data["events"], data["dropped"], data["inbox"], data["meta"]
    print(f"{a.run}: {len(ex)} observations, {len(events)} events, {len(dropped)} dropped")
    if a.dry_run or not url:
        if not url:
            print("SCOUT_IQ_DB_URL not set: nothing written", file=sys.stderr)
        return

    import psycopg
    from psycopg.types.json import Jsonb

    srcs = yaml.safe_load((ROOT / "sources.yaml").read_text())
    vcache = json.loads((ROOT / "data" / "venues.json").read_text()) if (ROOT / "data" / "venues.json").exists() else {}
    extractor_model = os.environ.get("OPENAI_EXTRACT_MODEL") or "gpt-5-mini"
    dedupe_version = next((e.get("dedupe_version") for e in events if e.get("dedupe_version")), "2")

    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute("select id from cities where slug = %s", (CITY_SLUG,))
        city_id = cur.fetchone()[0]

        # sources: sources.yaml first, then any handle seen in this run's observations
        source_ids: dict[tuple[str, str], uuid.UUID] = {}
        def upsert_source(kind, handle, name=None, tier=None, enabled=True):
            cur.execute("""insert into sources (city_id, kind, handle_or_url, name, tier, enabled)
                           values (%s, %s, %s, %s, %s, %s)
                           on conflict (kind, handle_or_url) do update set name = coalesce(excluded.name, sources.name),
                             tier = coalesce(excluded.tier, sources.tier), enabled = excluded.enabled
                           returning id""", (city_id, kind, handle, name, tier, enabled))
            source_ids[(kind, handle)] = cur.fetchone()[0]
        for s in (srcs.get("sites") or []) + (srcs.get("sites_tier2") or []):
            upsert_source("website", slug(s["name"]), s["name"], s.get("tier"), s.get("enabled", True))
        for s in (srcs.get("instagram") or []) + (srcs.get("instagram_tier2") or []):
            upsert_source("instagram", s["handle"], s["handle"], s.get("tier"), s.get("enabled", True))
        for _, _, rec in ex:
            so = source_of(rec)
            if so and so not in source_ids:
                upsert_source(so[0], so[1], so[1])

        # run
        wf, wt = window(meta)
        run_id = uid("run", a.run)
        cur.execute("""insert into runs (id, slug, city_id, window_start, window_end, umbrella, source_ids, extractor_model,
                         dedupe_version, status, finished_at)
                       values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'done', %s)
                       on conflict (slug) do update set dedupe_version = excluded.dedupe_version, umbrella = excluded.umbrella,
                         window_start = excluded.window_start, window_end = excluded.window_end, finished_at = excluded.finished_at""",
                    (run_id, a.run, city_id, wf, wt, meta.get("umbrella"), sorted({str(v) for v in source_ids.values()}),
                     extractor_model, dedupe_version, meta.get("published_at")))
        cur.execute("update sources set last_run_at = %s where id = any(%s)", (meta.get("published_at"), list(source_ids.values())))

        # venues: one row per matched Google place, else per cleaned venue string
        venue_ids: dict[str, uuid.UUID] = {}
        def venue_for(venue_text):
            q = venue_query(venue_text)
            if not q:
                return None
            if fold(q) in venue_ids:
                return venue_ids[fold(q)]
            c = vcache.get(fold(q)) or {}
            if c.get("matched") and c.get("place_id"):
                cur.execute("""insert into venues (city_id, name, aliases, address, lat, lng, google_place_id, google_rating,
                                 google_reviews, google_checked_at)
                               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                               on conflict (google_place_id) do update set google_rating = excluded.google_rating,
                                 google_reviews = excluded.google_reviews, google_checked_at = excluded.google_checked_at,
                                 aliases = (select array(select distinct unnest(venues.aliases || excluded.aliases)))
                               returning id""",
                            (city_id, c.get("name") or q, [q], c.get("address"), c.get("lat"), c.get("lng"), c["place_id"],
                             c.get("rating"), c.get("reviews"), c.get("looked_up_at")))
            else:
                cur.execute("""insert into venues (city_id, name, aliases) values (%s, %s, %s)
                               on conflict (city_id, lower(name)) where google_place_id is null do update set aliases = venues.aliases
                               returning id""", (city_id, q, [q]))
            venue_ids[fold(q)] = cur.fetchone()[0]
            return venue_ids[fold(q)]

        def organizer_for(name):
            if not name or not str(name).strip():
                return None
            n = str(name).strip()[:200]
            cur.execute("insert into organizers (name) values (%s) on conflict (lower(name)) do update set name = organizers.name returning id", (n,))
            return cur.fetchone()[0]

        # events (canonical) and their `run` occurrence
        event_ids: dict[str, uuid.UUID] = {}
        def event_id_by_key(key):
            cur.execute("select id from events where key = %s", (key,))
            r = cur.fetchone()
            return r[0] if r else None
        n_new = n_cont = 0
        for e in events:
            cont = e.get("continues")
            if cont:
                orig = event_id_by_key(cont["key"])
                if orig:
                    cur.execute("""update events set ends_at = greatest(ends_at, %s::timestamptz), last_seen_run_id = %s,
                                     updated_at = now() where id = %s""", (e.get("ends_at"), run_id, orig))
                    cur.execute("""update occurrences set ends_at = greatest(ends_at, %s::timestamptz)
                                   where event_id = %s and kind = 'run'""", (e.get("ends_at"), orig))
                    event_ids[e["key"]] = orig
                    n_cont += 1
                    continue
            vid = venue_for(e.get("venue"))
            oid = organizer_for(e.get("organizer"))
            sig = e.get("signals") or {}
            is_free = (e.get("price_min") == 0) if e.get("price_min") is not None else (bool(re.search(r"\b(gratis|libre|free)\b", str(e.get("price_text") or ""), re.I)) or None)
            cur.execute("""insert into events (key, city_id, title, description, starts_at, ends_at, all_day, timezone, venue_id,
                             venue_text, organizer_id, neighborhood, address, price_min, price_currency, price_text, is_free, url,
                             eventrrr_category, is_ongoing, rubric_score, signals, first_seen_run_id, last_seen_run_id)
                           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           on conflict (key) do update set title = excluded.title, description = excluded.description,
                             starts_at = excluded.starts_at, ends_at = excluded.ends_at, all_day = excluded.all_day,
                             venue_id = coalesce(excluded.venue_id, events.venue_id), venue_text = excluded.venue_text,
                             organizer_id = coalesce(excluded.organizer_id, events.organizer_id), neighborhood = excluded.neighborhood,
                             address = excluded.address, price_min = excluded.price_min, price_text = excluded.price_text,
                             is_free = excluded.is_free, url = excluded.url, eventrrr_category = excluded.eventrrr_category,
                             rubric_score = excluded.rubric_score, signals = excluded.signals, last_seen_run_id = excluded.last_seen_run_id,
                             updated_at = now()
                           returning id""",
                        (e["key"], city_id, e["title"], e.get("description"), e["starts_at"], e.get("ends_at") or None, bool(e.get("all_day")),
                         e.get("timezone") or "America/Mexico_City", vid, e.get("venue") if isinstance(e.get("venue"), str) else None, oid,
                         e.get("neighborhood"), e.get("address"), e.get("price_min"), e.get("currency"), e.get("price_text"), is_free,
                         e.get("url"), e.get("category"), bool(e.get("ends_at") and e["ends_at"][:10] > e["starts_at"][:10]),
                         e.get("score"), Jsonb(sig), run_id, run_id))
            eid = cur.fetchone()[0]
            event_ids[e["key"]] = eid
            n_new += 1
            cur.execute("""insert into occurrences (event_id, starts_at, ends_at, kind) values (%s, %s, %s, 'run')
                           on conflict (event_id, kind, starts_at) do update set ends_at = excluded.ends_at""",
                        (eid, e["starts_at"], e.get("ends_at") or None))

        # observations: one per extracted record, merged into the event it ended up in
        by_title_date = {}
        for e in events:
            by_title_date.setdefault((e["title"], (e.get("starts_at") or "")[:10]), e["key"])
        dropped_to = {}
        for d in dropped:
            if d.get("reason") == "seen_in":
                dropped_to[(d.get("title"), (d.get("starts_at") or "")[:10])] = d.get("key")
        n_obs = n_merged = n_orphan = 0
        for fname, i, rec in ex:
            oid_ = uid("obs", a.run, fname, i)
            so = source_of(rec)
            raw = inbox.get((rec.get("sources") or [None])[0]) or {}
            link = next((l.get("url") for l in rec.get("source_links") or [] if l.get("url")), None)
            cur.execute("""insert into observations (id, run_id, source_id, source_url, observed_at, raw_excerpt, extraction, extractor_model)
                           values (%s, %s, %s, %s, %s, %s, %s, %s)
                           on conflict (id) do update set extraction = excluded.extraction, raw_excerpt = excluded.raw_excerpt""",
                        (oid_, run_id, source_ids.get(so) if so else None, raw.get("source_url") or link,
                         raw.get("fetched_at") or meta.get("published_at"), (rec.get("source_excerpt") or "")[:300], Jsonb(rec), extractor_model))
            n_obs += 1
            # which event? the merged record whose sources include this one; else by title+day; else a dropped seen_in
            key = None
            for e in events:
                if any(s in (e.get("sources") or []) for s in rec.get("sources") or []):
                    key = e["key"]; break
            if not key:
                key = by_title_date.get((rec.get("title"), (rec.get("starts_at") or "")[:10])) or dropped_to.get((rec.get("title"), (rec.get("starts_at") or "")[:10]))
            eid = event_ids.get(key) or (event_id_by_key(key) if key else None)
            if not eid:
                n_orphan += 1
                continue
            cur.execute("""insert into event_merges (observation_id, event_id, merged_by, dedupe_version)
                           select %s, %s, 'model', %s where not exists
                             (select 1 from event_merges where observation_id = %s and unmerged_at is null)""",
                        (oid_, eid, dedupe_version, oid_))
            n_merged += 1
        conn.commit()
    print(f"written: {n_new} events ({n_cont} folded into earlier events), {n_obs} observations, {n_merged} merges, {n_orphan} observations without an event (past/dateless)")


if __name__ == "__main__":
    main()
