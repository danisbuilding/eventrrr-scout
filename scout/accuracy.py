#!/usr/bin/env python3
"""Nightly accuracy check for upcoming Scout IQ events. Writes search_flags (see supabase/accuracy.sql).

Usage: python scout/accuracy.py [--days 21] [--limit 120] [--dry-run] [--report report.md]
Env  : SCOUT_IQ_DB_URL (scout_pipeline role), OPENAI_API_KEY, ACCURACY_MODEL (default gpt-5-mini)

What it does, per upcoming one-off event in CDMX (not Instagram, not superseded by a later read of the same page):
  1. Re-reads the source page (one fetch per URL) and asks the model for THIS event's date and start time.
  2. Compares with what Scout stored:
       different date (and not one of the page's other dates) → date_mismatch (demote: Search shows it under "Show more")
       stored all-day, page gives a time                      → time_found   (Search shows that time)
       stored time off by more than 30 minutes                 → time_mismatch
       page 404/410                                            → source_gone
       page loads, event not on it                             → not_on_page
  3. Database checks: look-alike events from other sources within 3 days on a different date (cross_source), and
     timed events starting 03:00–06:59 or ending before they start (odd_time).
Flags found again stay open; open flags not found again are resolved; dismissed flags are left alone.
Low-confidence model answers never create a flag. The report lists open flags, newest first.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36 eventrrr-scout/1.0"
TZ = ZoneInfo("America/Mexico_City")
WEEKDAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MAX_TEXT = 14000
STOP = {"el", "la", "los", "las", "de", "del", "en", "y", "the", "a", "of", "in", "at", "cdmx", "se", "con", "por",
        "para", "un", "una", "precios", "presentara", "presenta", "show", "dara", "mexico", "ciudad"}

SCHEMA = {
    "name": "event_on_page", "strict": True,
    "schema": {
        "type": "object", "additionalProperties": False,
        "required": ["found", "date", "start_time", "other_dates", "evidence", "confidence"],
        "properties": {
            "found": {"type": "boolean"},
            "date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
            "start_time": {"type": ["string", "null"], "description": "HH:MM 24h, null if the page gives no time"},
            "other_dates": {"type": "array", "items": {"type": "string"}, "description": "other YYYY-MM-DD dates the page gives for this same event"},
            "evidence": {"type": "string", "description": "the words on the page that give the date/time, max 25 words"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
    },
}


# ------------------------------------------------------------------------------------------------ pure helpers
def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def title_words(title):
    return [w for w in fold(title).split() if len(w) > 2 and w not in STOP]


def fold_same_length(s):
    """Lowercase, accents stripped, one output char per input char (so offsets map back to the original)."""
    out = []
    for ch in s:
        base = unicodedata.normalize("NFKD", ch)[:1]
        out.append(base.lower() if base.isascii() else ch.lower())
    return "".join(out)


def focus_text(text, title, limit=MAX_TEXT):
    """Whole page if it fits; otherwise windows around the title's distinctive words (listing pages are long)."""
    if len(text) <= limit:
        return text
    low = fold_same_length(text)
    words = sorted(set(title_words(title)), key=len, reverse=True)[:3]
    spans = []
    for w in words:
        for m in re.finditer(r"\b" + re.escape(w), low):
            spans.append((max(0, m.start() - 1500), min(len(text), m.end() + 2500)))
    if not spans:
        return text[:limit]
    spans.sort()
    merged = [list(spans[0])]
    for x, y in spans[1:]:
        if x <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], y)
        else:
            merged.append([x, y])
    out, total = [], 0
    for x, y in merged:
        chunk = text[x:y][: limit - total]
        out.append(chunk)
        total += len(chunk)
        if total >= limit:
            break
    return "\n…\n".join(out)


def local(ts):
    return ts.astimezone(TZ) if ts else None


def compare(ev, ans):
    """ev: dict(starts_at aware dt, all_day bool). ans: model answer. Returns list of (check, severity, detail, suggested)."""
    if not ans or not ans.get("found") or ans.get("confidence") == "low" or not ans.get("date"):
        return []
    try:
        page_day = dt.date.fromisoformat(ans["date"])
    except ValueError:
        return []
    start = local(ev["starts_at"])
    stored_day = start.date()
    others = set()
    for d in ans.get("other_dates") or []:
        try:
            others.add(dt.date.fromisoformat(d))
        except ValueError:
            pass
    detail = {"page_date": ans["date"], "page_time": ans.get("start_time"), "evidence": (ans.get("evidence") or "")[:240],
              "stored": start.strftime("%Y-%m-%d %H:%M") if not ev["all_day"] else stored_day.isoformat() + " (all day)",
              "confidence": ans.get("confidence")}
    t = None
    if ans.get("start_time") and re.fullmatch(r"\d{1,2}:\d{2}", ans["start_time"]):
        h, m = map(int, ans["start_time"].split(":"))
        if 0 <= h < 24 and 0 <= m < 60:
            t = dt.time(h, m)
    if page_day != stored_day and stored_day not in others:
        sug = dt.datetime.combine(page_day, t or dt.time(0, 0), TZ) if page_day else None
        return [("date_mismatch", "demote", detail, sug)]
    if t is None:
        return []
    page_start = dt.datetime.combine(stored_day, t, TZ)
    if ev["all_day"]:
        return [("time_found", "info", detail, page_start)]
    if abs((page_start - start).total_seconds()) > 30 * 60:
        return [("time_mismatch", "info", detail, page_start)]
    return []


# ------------------------------------------------------------------------------------------------ io
def fetch(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"}, timeout=20, allow_redirects=True)
    except Exception as e:
        return {"status": 0, "error": str(e)[:200], "text": ""}
    if r.status_code >= 400:
        return {"status": r.status_code, "text": ""}
    import trafilatura
    html = r.text
    txt = trafilatura.extract(html, url=url, include_links=False, include_comments=False, favor_recall=True) or ""
    if len(txt) < 400:  # listing pages often defeat trafilatura; fall back to all visible text
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()
        txt = re.sub(r"\n\s*\n+", "\n", soup.get_text("\n"))
    return {"status": r.status_code, "text": txt}


def ask(client, model, ev, text, today):
    start = local(ev["starts_at"])
    stored = (f"{WEEKDAYS_ES[start.weekday()]} {start:%Y-%m-%d}" + ("" if ev["all_day"] else f" at {start:%H:%M}"))
    system = (
        "You check event listings against their source web page. Find the event named by the user on the page and "
        "report the date and start time THE PAGE gives for it. Never guess: if the page doesn't say, use null. "
        f"Today is {today:%A %Y-%m-%d} in Mexico City. If the page omits the year, use the next such date on or after "
        "today. Dates in Spanish (e.g. 'sábado 14 de noviembre') must be converted carefully; check that the weekday "
        "and the day number agree, and if they don't, trust the day number and say so in evidence. A time like "
        "'20 h' or '8 pm' is 20:00; 'puertas' (doors) is not the start time if a show time is also given. "
        "found=false if this event isn't on the page. confidence=low if you are unsure it's the same event.")
    user = f"Event: {ev['title']}\nScout recorded: {stored}\nVenue: {ev.get('venue') or 'unknown'}\n\nPage text:\n{text}"
    kw = dict(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
              response_format={"type": "json_schema", "json_schema": SCHEMA})
    try:
        r = client.chat.completions.create(**kw, reasoning_effort=os.getenv("ACCURACY_EFFORT", "low"))
    except Exception as e:
        if "reasoning" not in str(e).lower():
            raise
        r = client.chat.completions.create(**kw)
    return json.loads(r.choices[0].message.content)


CANDIDATES = """
select e.id, e.title, e.url, e.all_day, e.timezone, coalesce(v.name, e.venue_text) venue,
       coalesce(o.starts_at, e.starts_at) starts_at, coalesce(o.ends_at, e.ends_at) ends_at
from events e
join cities c on c.id = e.city_id
left join venues v on v.id = e.venue_id
left join lateral (select starts_at, ends_at from occurrences where event_id = e.id order by starts_at limit 1) o on true
where c.slug = 'cdmx' and e.status in ('live', 'moved') and not e.is_ongoing
  and coalesce(o.starts_at, e.starts_at) between now() - interval '6 hours' and now() + make_interval(days => %(days)s)
  and not exists (
    select 1 from events e2 join runs r2 on r2.id = e2.last_seen_run_id join runs r1 on r1.id = e.last_seen_run_id
    where e2.id <> e.id and e2.url = e.url and split_part(e2.key, '|', 1) = split_part(e.key, '|', 1)
      and r2.created_at > r1.created_at)
order by starts_at
limit %(limit)s
"""

DB_CHECKS = """
with u as (
  select e.id, e.title, e.url, e.all_day, (e.starts_at at time zone e.timezone) l, e.starts_at, e.ends_at,
         search_fold(e.title) ft, split_part(e.url, '/', 3) host
  from events e join cities c on c.id = e.city_id
  where c.slug = 'cdmx' and e.status in ('live', 'moved') and not e.is_ongoing
    and e.starts_at between now() - interval '6 hours' and now() + make_interval(days => %(days)s)
    and not exists (
      select 1 from events e2 join runs r2 on r2.id = e2.last_seen_run_id join runs r1 on r1.id = e.last_seen_run_id
      where e2.id <> e.id and e2.url = e.url and split_part(e2.key, '|', 1) = split_part(e.key, '|', 1)
        and r2.created_at > r1.created_at))
select 'cross_source' check_name, a.id, jsonb_build_object('other_title', b.title, 'other_url', b.url,
         'other_date', b.l::date, 'stored', a.l::date) detail
from u a join u b on a.id <> b.id and a.host <> b.host
  and extensions.similarity(a.ft, b.ft) >= 0.35 and a.l::date <> b.l::date and abs(a.l::date - b.l::date) <= 3
union all
select 'odd_time', id, jsonb_build_object('stored', to_char(l, 'YYYY-MM-DD HH24:MI'),
         'why', case when ends_at < starts_at then 'ends before it starts' else 'starts between 03:00 and 06:59' end)
from u where not all_day and (extract(hour from l) between 3 and 6 or ends_at < starts_at)
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    url = os.getenv("SCOUT_IQ_DB_URL")
    if not url:
        sys.exit("SCOUT_IQ_DB_URL not set")
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    from openai import OpenAI

    model = os.getenv("ACCURACY_MODEL") or "gpt-5-mini"
    client = OpenAI()
    today = dt.datetime.now(TZ).date()

    with psycopg.connect(url, row_factory=dict_row) as conn:
        evs = conn.execute(CANDIDATES, {"days": a.days, "limit": a.limit}).fetchall()
        db_flags = conn.execute(DB_CHECKS, {"days": a.days}).fetchall()

    web = [e for e in evs if e["url"] and "instagram.com" not in e["url"]]
    urls = sorted({e["url"] for e in web})
    print(f"{len(evs)} upcoming events; re-reading {len(web)} on {len(urls)} pages with {model}")
    with ThreadPoolExecutor(6) as pool:
        pages = dict(zip(urls, pool.map(fetch, urls)))

    def check(ev):
        p = pages[ev["url"]]
        if p["status"] in (404, 410):
            return ev, [("source_gone", "info", {"http": p["status"]}, None)], False, None
        if not p["text"]:
            return ev, [], False, f"unreadable ({p.get('status')}{' ' + p['error'] if p.get('error') else ''})"
        if len(p["text"]) < 600:
            return ev, [], False, "page has almost no text without JavaScript"
        try:
            ans = ask(client, model, ev, focus_text(p["text"], ev["title"]), today)
        except Exception as e:  # one bad call never stops the run
            return ev, [], False, f"model error: {str(e)[:120]}"
        if not ans.get("found") and ans.get("confidence") != "low":
            return ev, [("not_on_page", "info", {"evidence": ans.get("evidence", "")[:240]}, None)], False, None
        confident = bool(ans.get("found")) and ans.get("confidence") in ("high", "medium") and bool(ans.get("date"))
        return ev, compare(ev, ans), confident, None

    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(check, web))

    found = {}  # (event_id, check) -> (severity, detail, suggested)
    skipped = []
    confirmed = []  # events with a confident answer tonight: their old date/time flags can be resolved
    loaded = []     # events whose page loaded: their old source_gone / not_on_page flags can be resolved
    for ev, flags, confident, err in results:
        if confident:
            confirmed.append(ev["id"])
        if not err and not any(f[0] == "source_gone" for f in flags):
            loaded.append(ev["id"])
        if err:
            skipped.append((ev["id"], ev["title"], err))
        for name, sev, detail, sug in flags:
            found[(ev["id"], name)] = (sev, detail, sug)
    for f in db_flags:
        found[(f["id"], f["check_name"])] = ("info", f["detail"], None)
    db_checked_ids = [e["id"] for e in evs]

    print(f"flags: {len(found)}  skipped: {len(skipped)}")
    for (eid, name), (sev, detail, sug) in found.items():
        title = next((e["title"] for e in evs if e["id"] == eid), str(eid))
        print(f"  [{sev}] {name}: {title} :: {json.dumps(detail, ensure_ascii=False, default=str)[:200]}")
    if a.dry_run:
        return

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for (eid, name), (sev, detail, sug) in found.items():
            cur.execute("""
                insert into search_flags (event_id, check_name, severity, detail, suggested_starts_at)
                values (%s, %s, %s, %s, %s)
                on conflict (event_id, check_name) do update set
                  severity = excluded.severity, detail = excluded.detail, suggested_starts_at = excluded.suggested_starts_at,
                  last_seen = now(),
                  status = case when search_flags.status = 'dismissed' then 'dismissed' else 'open' end,
                  first_seen = case when search_flags.status = 'resolved' then now() else search_flags.first_seen end
            """, (eid, name, sev, Jsonb(detail), sug))
        # resolve: web checks for events re-read tonight, db checks for every candidate
        keep = [f"{eid}|{name}" for (eid, name) in found]
        cur.execute("""
            update search_flags set status = 'resolved'
            where status = 'open' and not ((event_id::text || '|' || check_name) = any (%s))
              and ((check_name in ('date_mismatch', 'time_found', 'time_mismatch', 'not_on_page') and event_id = any (%s))
                   or (check_name = 'source_gone' and event_id = any (%s))
                   or (check_name in ('cross_source', 'odd_time') and event_id = any (%s)))
        """, (keep, confirmed, loaded, db_checked_ids))
        # events no longer checked (superseded by a later read, retired, or past the window) drop their open flags
        cur.execute("""update search_flags set status = 'resolved'
                       where status = 'open' and not (event_id = any (%s))""", (db_checked_ids,))
        # past events drop out of the report
        cur.execute("""update search_flags f set status = 'resolved' from events e
                       where e.id = f.event_id and f.status = 'open' and coalesce(e.ends_at, e.starts_at) < now() - interval '1 day'""")

    if a.report:
        write_report(url, a.report, len(evs), len(web), len(urls), skipped, model)


def write_report(url, path, n_events, n_web, n_pages, skipped, model):
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(url, row_factory=dict_row) as conn:
        rows = conn.execute("""
            select f.check_name, f.severity, f.detail, f.suggested_starts_at, f.first_seen, e.title, e.url,
                   e.starts_at, e.all_day, f.first_seen > now() - interval '20 hours' as new
            from search_flags f join events e on e.id = f.event_id
            where f.status = 'open' order by f.severity, f.first_seen desc""").fetchall()
    new_demotes = sum(1 for r in rows if r["new"] and r["severity"] == "demote")
    lines = [f"Checked {n_events} upcoming events: re-read {n_web} on {n_pages} source pages ({model}), "
             f"plus database checks. Instagram events get database checks only.", ""]
    if not rows:
        lines.append("No open flags. 🎉")
    else:
        lines += ["| | Check | Event | Scout has | Page says | Evidence |", "|---|---|---|---|---|---|"]
        for r in rows:
            d = r["detail"] or {}
            stored = d.get("stored") or local(r["starts_at"]).strftime("%Y-%m-%d %H:%M")
            says = " ".join(x for x in [d.get("page_date") or str(d.get("other_date") or ""), d.get("page_time") or ""] if x) \
                or d.get("why") or (f"HTTP {d['http']}" if d.get("http") else "")
            if r["check_name"] == "cross_source" and d.get("other_url"):
                says = f"[{d.get('other_title', 'other source')[:40]}]({d['other_url']}): {d.get('other_date')}"
            ev = (d.get("evidence") or "").replace("|", "/").replace("\n", " ")[:120]
            mark = ("🆕 " if r["new"] else "") + ("⬇️" if r["severity"] == "demote" else "ℹ️")
            title = " ".join(r["title"].split()).replace("|", "/").replace("[", "(").replace("]", ")")[:60]
            says = says.replace("|", "/").replace("\n", " ")
            lines.append(f"| {mark} | {r['check_name']} | [{title}]({r['url']}) | {stored} | {says} | {ev} |")
    if skipped:
        lines += ["", f"<details><summary>{len(skipped)} couldn't be checked</summary>", ""]
        lines += [f"- {t[:70]}: {why}" for _, t, why in skipped[:40]]
        lines += ["", "</details>"]
    lines += ["", "⬇️ = moved to “Show more” in Search until the page and Scout agree. ℹ️ = for review; Search shows the page's "
              "time for all-day events (time_found). To clear a flag that's wrong: "
              "`update search_flags set status = 'dismissed' where id = '…'` in Scout IQ."]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(path + ".new", "w") as f:
        f.write(str(new_demotes))


if __name__ == "__main__":
    main()
