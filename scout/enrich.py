#!/usr/bin/env python3
"""Tag and embed upcoming Scout IQ events for Eventrrr Search (writes event_tags; see supabase/event_tags.sql).

Usage: python scout/enrich.py [--days 60] [--all] [--dry-run]
Env  : SCOUT_IQ_DB_URL (scout_pipeline role), OPENAI_API_KEY,
       ENRICH_MODEL (default gpt-5-mini), EMBED_MODEL (default text-embedding-3-small, 512 dimensions)

For each live event that's on now or starts within --days, and whose text changed since it was last tagged
(source_hash), one model call reads it and returns:
  kid_friendly  true/false/null   suitable for children or families (null when the listing gives no hint)
  outdoor       true/false/null   happens mostly outdoors
  venue_type    one of VENUE_TYPES
  activity      one of ACTIVITIES
  summary_en    one plain English sentence (helps English questions find Spanish listings)
Then one embedding per event (title, venue, category, tags, summary, description) for meaning-based search.
Search filters on the tags and ranks by embedding similarity; the vocabularies must match lib/parse.js there.
"""
import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

VENUE_TYPES = ["museum", "gallery", "park", "music_venue", "club_bar", "theater", "cinema", "restaurant_market",
               "cultural_center", "arena", "public_space", "other"]
ACTIVITIES = ["exhibition", "workshop", "tour", "concert", "dj_party", "performance", "film", "talk", "market",
              "festival", "sport_wellness", "food_drink", "other"]
DIMS = 512

SCHEMA = {
    "name": "event_tags", "strict": True,
    "schema": {
        "type": "object", "additionalProperties": False,
        "required": ["kid_friendly", "outdoor", "venue_type", "activity", "summary_en"],
        "properties": {
            "kid_friendly": {"type": ["boolean", "null"]},
            "outdoor": {"type": ["boolean", "null"]},
            "venue_type": {"type": "string", "enum": VENUE_TYPES},
            "activity": {"type": "string", "enum": ACTIVITIES},
            "summary_en": {"type": "string"},
        },
    },
}

SYSTEM = (
    "You tag event listings from Mexico City (mostly in Spanish) for a search engine. Judge from the listing only.\n"
    "kid_friendly: true ONLY if it's made for children or families: kids' or family workshops, children's theater or "
    "puppets, family days, 'para niños', 'infantil', 'en familia', 'todo público' activities, kids' book fairs, festivals "
    "billed as family-friendly. A general museum exhibition, talk, concert or tasting that a child could technically "
    "attend is NOT kid_friendly (use null). false for adults-only, bars, clubs, late-night shows. null when unclear.\n"
    "outdoor: true if it mostly happens outside (park, street, plaza, open-air stage, rooftop, walking tour, outdoor "
    "market); false if indoors; null if you can't tell.\n"
    "venue_type: the kind of place. museum = museums (Museo …), gallery = art galleries, park = parks/gardens/forests, "
    "music_venue = concert halls, foros, arenas for music under ~5k, club_bar = clubs, bars, cantinas, theater = "
    "theaters and dance venues, cinema, restaurant_market = restaurants, cafés, markets, cultural_center = cultural "
    "centers, libraries, universities, arena = stadiums and big arenas, public_space = plazas, streets, Zócalo.\n"
    "activity: what you do there. exhibition = see an exhibition; workshop = hands-on class/taller; tour = guided "
    "visit/walk; concert = live music; dj_party = DJ, club night, party; performance = theater, dance, comedy, opera; "
    "film = screenings; talk = talks, readings, panels; market = fairs, bazaars, markets; festival = multi-act "
    "festivals; sport_wellness = runs, yoga, sports; food_drink = tastings, dinners, pop-ups.\n"
    "summary_en: one short plain English sentence saying what it is, where, and who it's for. No dates."
)


def source_text(e):
    return "\n".join(str(x) for x in [e["title"], e.get("venue") or "", e.get("category") or "", e.get("address") or "",
                                       e.get("price_text") or "", (e.get("description") or "")[:1500]])


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def tag(client, model, e):
    user = (f"Title: {e['title']}\nVenue: {e.get('venue') or 'unknown'}\nCategory: {e.get('category') or ''}\n"
            f"Starts: {e['starts_local']}{' (ongoing run)' if e['is_ongoing'] else ''}\nPrice: {e.get('price_text') or ''}\n"
            f"Description: {(e.get('description') or '')[:1500]}")
    kw = dict(model=model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
              response_format={"type": "json_schema", "json_schema": SCHEMA})
    try:
        r = client.chat.completions.create(**kw, reasoning_effort=os.getenv("ENRICH_EFFORT", "low"))
    except Exception as ex:
        if "reasoning" not in str(ex).lower():
            raise
        r = client.chat.completions.create(**kw)
    return json.loads(r.choices[0].message.content)


def embed_text(e, t):
    bits = [e["title"], e.get("venue") or "", e.get("category") or "", t["activity"], t["venue_type"],
            "kid-friendly family" if t["kid_friendly"] else "", "outdoors" if t["outdoor"] else "",
            t["summary_en"], (e.get("description") or "")[:800]]
    return " | ".join(b for b in bits if b)


QUERY = """
select e.id, e.title, e.description, e.price_text, e.address, e.is_ongoing, e.eventrrr_category category,
       coalesce(v.name, e.venue_text) venue, to_char(e.starts_at at time zone e.timezone, 'Dy YYYY-MM-DD HH24:MI') starts_local,
       t.source_hash
from events e
join cities c on c.id = e.city_id
left join venues v on v.id = e.venue_id
left join event_tags t on t.event_id = e.id
where e.status in ('live', 'moved')
  and coalesce(e.ends_at, e.starts_at + interval '1 day') >= now() - interval '1 day'
  and e.starts_at <= now() + make_interval(days => %(days)s)
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--all", action="store_true", help="re-tag even unchanged events")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    url = os.getenv("SCOUT_IQ_DB_URL")
    if not url:
        sys.exit("SCOUT_IQ_DB_URL not set")
    import psycopg
    from psycopg.rows import dict_row
    from openai import OpenAI
    client = OpenAI()
    model = os.getenv("ENRICH_MODEL") or "gpt-5-mini"
    emodel = os.getenv("EMBED_MODEL") or "text-embedding-3-small"

    with psycopg.connect(url, row_factory=dict_row) as conn:
        rows = conn.execute(QUERY, {"days": a.days}).fetchall()
    todo = []
    for e in rows:
        sh = h(source_text(e) + "|" + model + "|v2")
        if a.all or e["source_hash"] != sh:
            e["new_hash"] = sh
            todo.append(e)
    print(f"{len(rows)} events in range, {len(todo)} to tag with {model}")
    if not todo:
        return

    def work(e):
        try:
            return e, tag(client, model, e), None
        except Exception as ex:
            return e, None, str(ex)[:160]
    with ThreadPoolExecutor(6) as pool:
        tagged = list(pool.map(work, todo))
    ok = [(e, t) for e, t, err in tagged if t]
    for e, _, err in tagged:
        if err:
            print(f"  ! {e['title'][:60]}: {err}")

    vecs = []
    texts = [embed_text(e, t) for e, t in ok]
    for i in range(0, len(texts), 100):
        r = client.embeddings.create(model=emodel, input=texts[i:i + 100], dimensions=DIMS)
        vecs += [d.embedding for d in r.data]

    kids = sum(1 for _, t in ok if t["kid_friendly"]); outs = sum(1 for _, t in ok if t["outdoor"])
    print(f"tagged {len(ok)}: {kids} kid-friendly, {outs} outdoor")
    for e, t in ok[:12]:
        print(f"  {e['title'][:55]:55} kid={t['kid_friendly']} out={t['outdoor']} {t['venue_type']}/{t['activity']}")
    if a.dry_run:
        return
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for (e, t), v in zip(ok, vecs):
            cur.execute("""
                insert into event_tags (event_id, kid_friendly, outdoor, venue_type, activity, summary_en, embedding, source_hash, model, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s::extensions.vector, %s, %s, now())
                on conflict (event_id) do update set kid_friendly = excluded.kid_friendly, outdoor = excluded.outdoor,
                  venue_type = excluded.venue_type, activity = excluded.activity, summary_en = excluded.summary_en,
                  embedding = excluded.embedding, source_hash = excluded.source_hash, model = excluded.model, updated_at = now()
            """, (e["id"], t["kid_friendly"], t["outdoor"], t["venue_type"], t["activity"], t["summary_en"][:300],
                  "[" + ",".join(f"{x:.6f}" for x in v) + "]", e["new_hash"], model))
    print("written")


if __name__ == "__main__":
    main()
