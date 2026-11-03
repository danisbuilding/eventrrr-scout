#!/usr/bin/env python3
"""Look each event's venue up on Google Maps (Places API (New) Text Search) and mark well-rated venues.

Usage: python scout/venues.py <run> [--dry-run] [--max N]
Reads : runs/<run>/events.json, data/venues.json (cache, committed with the run)
Writes: runs/<run>/events.json in place — adds `venue_place` {place_id, name, rating, reviews, maps_url, lat, lng}
        and `signals.venue_rated` (rating >= VENUE_RATING_MIN with >= VENUE_REVIEWS_MIN reviews; score.py weighs it
        via taxonomy.yaml → highlight.computed); data/venues.json gains one entry per distinct venue query.

Needs GOOGLE_PLACES_API_KEY (repo secret, restricted to Places API (New)). Without it the step is a no-op that
still prints what it would look up. One Text Search call per new venue string; the field mask includes rating,
so each call bills as Text Search Enterprise (1,000 free per month, then $35 per 1,000). The cache keeps repeat
venues free; --max caps new lookups per run. Run it before score.py.

Scout IQ: the cache is the seed for venues.google_place_id / google_rating / google_reviews.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "venues.json"
ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.googleMapsUri,places.primaryType"
CITY = {"suffix": "Ciudad de México", "lat": 19.4326, "lng": -99.1332, "radius_m": 40000}  # cities table later

VENUE_RATING_MIN = 4.8
VENUE_REVIEWS_MIN = 50
MAX_NEW_LOOKUPS = 150  # per run

# Venue strings that are not a place to look up.
NOT_A_PLACE = re.compile(
    r"^\s*(varias|varios|diversas|diversos|distintas|distintos|m[uú]ltiples|por confirmar|tba|tbd|online|en l[ií]nea|"
    r"virtual|streaming|zoom|televisi[oó]n|tv|radio)\b|\b(sedes|ubicaciones|sucursales|ruta|tramo|fachadas|desfile)\b",
    re.I)
STOP = {"el", "la", "los", "las", "de", "del", "en", "y", "the", "a", "con", "por", "para", "un", "una", "at", "in",
        "of", "and", "cdmx", "mexico", "ciudad", "sala", "salon", "foro", "auditorio", "explanada", "centro", "cultural",
        "museo", "teatro", "casa", "jardin", "plaza", "parque"}


def fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def words(s: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", fold(s)) if len(w) > 2 and w not in STOP}


def venue_query(venue) -> str | None:
    """The searchable part of an extracted venue string: parentheticals out, first clause of 'A — B' / 'A / B'
    (the second is usually a room, an address or an alias), commas kept (Google reads 'Sala X, Centro Y' well)."""
    if isinstance(venue, dict):
        venue = venue.get("name") or ""
    v = str(venue or "").strip()
    if not v or NOT_A_PLACE.search(v):
        return None
    v = re.sub(r"\([^)]*\)", " ", v)
    v = re.split(r"\s+(?:—|–|/+|\|)\s+", v, maxsplit=1)[0]
    v = re.sub(r"\s+", " ", v).strip(" ,.-")
    return v if len(v) >= 3 else None


def plausible(query: str, place: dict) -> bool:
    """Did Google return the venue we asked for, or just something in the city? The name or address must share a
    word with the query; a short acronym (MUAC, CCU, MUNAL) may appear in either."""
    name, addr = place.get("displayName", {}).get("text", ""), place.get("formattedAddress", "")
    qw, nw = words(query), words(name) | words(addr)
    if qw & nw:
        return True
    acronyms = {w.lower() for w in re.findall(r"\b[A-Z]{3,6}\b", query)}
    return bool(acronyms and acronyms & {w.lower() for w in re.findall(r"\b[A-Za-z]{3,6}\b", name + " " + addr)})


def lookup(query: str, key: str, session: requests.Session) -> dict:
    body = {"textQuery": f"{query}, {CITY['suffix']}", "pageSize": 1, "languageCode": "es", "regionCode": "MX",
            "locationBias": {"circle": {"center": {"latitude": CITY["lat"], "longitude": CITY["lng"]}, "radius": CITY["radius_m"]}}}
    r = session.post(ENDPOINT, json=body, timeout=20,
                     headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS, "Content-Type": "application/json"})
    entry = {"query": query, "looked_up_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "status": r.status_code}
    if r.status_code != 200:
        entry["error"] = r.text[:300]
        return entry
    places = r.json().get("places") or []
    if not places:
        entry["matched"] = False
        return entry
    p = places[0]
    entry.update({
        "matched": plausible(query, p),
        "place_id": p.get("id"),
        "name": p.get("displayName", {}).get("text"),
        "address": p.get("formattedAddress"),
        "primary_type": p.get("primaryType"),
        "rating": p.get("rating"),
        "reviews": p.get("userRatingCount", 0),
        "maps_url": p.get("googleMapsUri"),
        "lat": p.get("location", {}).get("latitude"),
        "lng": p.get("location", {}).get("longitude"),
    })
    return entry


def is_rated(entry: dict) -> bool:
    return bool(entry.get("matched")) and (entry.get("rating") or 0) >= VENUE_RATING_MIN and (entry.get("reviews") or 0) >= VENUE_REVIEWS_MIN


def apply(ev: dict, entry: dict | None) -> None:
    sig = ev.setdefault("signals", {})
    if not entry or not entry.get("matched"):
        sig["venue_rated"] = False
        ev.pop("venue_place", None)
        return
    ev["venue_place"] = {k: entry.get(k) for k in ("place_id", "name", "rating", "reviews", "maps_url", "lat", "lng")}
    sig["venue_rated"] = is_rated(entry)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--dry-run", action="store_true", help="print the queries; no API calls, no writes")
    ap.add_argument("--max", type=int, default=MAX_NEW_LOOKUPS, help="new lookups per run")
    a = ap.parse_args()
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    p = ROOT / "runs" / a.run / "events.json"
    events = json.loads(p.read_text())
    cache: dict[str, dict] = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    queries = {}
    for ev in events:
        q = venue_query(ev.get("venue"))
        if q:
            queries.setdefault(fold(q), q)
    new = [q for k, q in queries.items() if k not in cache or cache[k].get("status") not in (200,)]
    print(f"{len(events)} events, {len(queries)} venue queries, {len(cache)} cached, {len(new)} new")
    if a.dry_run or not key:
        if not key:
            print("GOOGLE_PLACES_API_KEY not set: no lookups made", file=sys.stderr)
        for q in new:
            print("  would look up:", q)
        return

    s = requests.Session()
    for q in new[:a.max]:
        cache[fold(q)] = lookup(q, key, s)
        e = cache[fold(q)]
        print(f"  {q[:45]:45} → {e.get('name') or e.get('error') or 'no match'} {e.get('rating', '')} ({e.get('reviews', '')}){'' if e.get('matched') else '  [unmatched]'}")
    if len(new) > a.max:
        print(f"  {len(new) - a.max} venues left for the next run (--max {a.max})")
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1))

    n_rated = 0
    for ev in events:
        q = venue_query(ev.get("venue"))
        entry = cache.get(fold(q)) if q else None
        apply(ev, entry)
        n_rated += ev["signals"]["venue_rated"]
    p.write_text(json.dumps(events, ensure_ascii=False, indent=1))
    print(f"{n_rated} events at a venue rated ≥{VENUE_RATING_MIN} with ≥{VENUE_REVIEWS_MIN} reviews → {p}")


if __name__ == "__main__":
    main()
