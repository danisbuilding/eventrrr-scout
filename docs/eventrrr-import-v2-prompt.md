# Bolt prompt: Scout export v2 on the Paste text tab, and the curated-calendar view

Status: Prompts A and B ran in Bolt on 2026-11-04 and were verified in the live app (see the Scout Build Handover). Follows `eventrrr-import-prompt.md` (v1, ran 2026-10-28). The Scout now sends v2
payloads; until this prompt runs, v1 import still works because every v1 field name is unchanged and unknown keys are
ignored (the Scout-side builder is `exportJson` in `site/app.js`).

Two prompts, pasted into Bolt one after the other, output requested verbatim each time. Prompt A changes the import;
Prompt B changes how a curated calendar is shown. Run A first; B can wait.

## Prompt A — calendar match and tiers on import

```
Extend the JSON import on the + sheet's Paste text tab (src/lib/scoutImport.ts, called from src/sheets/TextTab.tsx) to accept the scout's v2 payload. Everything that works today keeps working: v1 payloads (no `scout_export` key) behave exactly as now, and plain text still goes to the extractor.

## 1. What v2 adds

Detection is unchanged (`"eventrrr_import": 1` plus an `events` array). A v2 payload also has `"scout_export": "v2"`, an `export_id` string, and a `calendar` object:

{
  "eventrrr_import": 1,
  "scout_export": "v2",
  "source": "eventrrr-scout",
  "run": "calendar:date-night",
  "export_id": "3f2b…",
  "calendar": {
    "profile": "date-night",
    "profile_name": "Date Night",
    "city": "Mexico City",
    "city_slug": "cdmx",
    "handle_slug": "date-night-cdmx"
  },
  "events": [
    { ...the v1 fields exactly as today (title, starts_at, ends_at, all_day, timezone, venue, address, neighborhood, price_text, price_min, currency, url, category, description, public_note)..., "tier": "main" }
  ]
}

Per event, `tier` is "main" or "overflow" (default "main" when missing or anything else). No other field is added, renamed or removed. The payload never carries `image_url` or `highlight`; keep ignoring unknown keys.

## 2. Calendar match (replaces the "Also add to" chip for v2 payloads)

When `calendar` is present, find the signed-in user's calendar whose stored scout mapping is (`calendar.profile`, `calendar.city_slug`). Store that mapping on the calendar (two nullable text columns `scout_profile`, `scout_city`, or an equivalent you already have; add the columns if needed, nothing else). Matching is inside the signed-in account only: two accounts can each have a "Date Night · Mexico City" and never collide.

- Match found: import into that calendar. Ignore the "Also add to" chip.
- No match: before inserting, show one confirmation inline in the sheet: "Create calendar "Date Night · Mexico City" for these events?" with Create and Cancel. Create makes the calendar named `calendar.profile_name` + " · " + `calendar.city`, stores the mapping, and imports. Cancel inserts nothing.

For v1 payloads (no `calendar`), keep today's behavior with the "Also add to" chip.

## 3. Tier

Add a nullable text column `scout_tier` on calendar_events (or the join row you use for an event in a calendar), values "main" | "overflow". Set it from the event's `tier` for every imported event. Nothing in the UI changes in this prompt.

## 4. Reply for the scout

On success, show the existing toast ("{N} events added to your Inbox") and, under it in the sheet, a small copyable block the user can paste back into the scout:

{"export_id": "<export_id from the payload>", "calendar_id": "<the calendar's id>", "event_ids": ["<new event id>", …]}

in the order of the payload's `events`. A Copy button next to it. The block disappears when the sheet closes.

## 5. Don't

- Don't call the extractor for an import. Don't change how plain text, links, photos or Manual captures work.
- Don't add a new tab, route or edge function. The only schema changes are the two mapping columns on calendars and `scout_tier` on the calendar-event row.
- Don't let the payload set status, visibility, ownership, or any calendar other than the matched or newly created one.
- Events still land in the Inbox as To review, with the duplicate check as today.

## Test, then tell me

1. Paste a v2 payload with 2 events for a profile this account has never seen: the "Create calendar …" confirmation shows; Create → both events in the Inbox as To review, in the new calendar, `scout_tier` set ("main" and "overflow"); the reply block shows the calendar id and two event ids; Copy works.
2. Paste the same payload again: no confirmation, same calendar; both cards show the duplicate choice.
3. Paste a v2 payload whose `calendar.city_slug` is "gdl" for the same profile: a different calendar is proposed ("Date Night · Guadalajara" if `calendar.city` says so).
4. Paste a v1 payload (no `scout_export`, no `calendar`): behaves exactly as before, including "Also add to".
5. Paste a v2 payload with `"tier": "weird"` on one event: it imports with scout_tier "main".
6. Tell me the files changed and the exact column names added.
```

## Prompt B — curated calendar view: week bands and overflow

```
Change how a calendar that has scout-imported events (any event with `scout_tier` set) is displayed. Calendars without any such event are untouched.

## 1. Week bands

Group the calendar's upcoming events into Monday-start week bands ("Week of Nov 3", "Week of Nov 10", …), in order. Inside a band:
- Ongoing events (ends_at on a later day than starts_at) come first, as a compact strip or list at the top of the band, ordered by closing date ascending (the one closing soonest first). An ongoing event appears in every band it overlaps.
- Dated events come under their day, in the existing day grouping, by start time.

## 2. Overflow

Events with `scout_tier = "overflow"` are collapsed: per day (dated) and per band (ongoing), show the main events, then one line "N more" that expands to the overflow events inline. Expansion state is per day/band and resets on reload.

Add a per-calendar boolean `show_overflow` (default false) in the calendar's settings sheet, labeled "Show overflow events". When true, overflow events are listed inline with the main ones, visually quieter (the existing muted text style), with no "N more" line.

## 3. Don't

- Don't change any calendar that has no scout-imported events.
- Don't change the Inbox, the import, or the event detail view.
- Don't add routes or edge functions; the only schema change is `show_overflow` on calendars.

## Test, then tell me

1. A calendar with 2 ongoing events (one closing Nov 9, one Nov 20) and 5 dated events on Nov 6 (3 main, 2 overflow): the "Week of Nov 3" band shows the ongoing strip with the Nov 9 one first, then Nov 6 with 3 events and a "2 more" line that expands; the "Week of Nov 17" band shows only the Nov 20 ongoing event.
2. Turn on "Show overflow events": the 2 overflow events list inline, muted; the "2 more" line is gone.
3. A calendar with no scout events looks exactly as before.
4. Tell me the files changed.
```

## After Prompt A runs

- Paste Eventrrr's reply block into the Scout's profile panel ("Record Eventrrr's reply") so `calendars.eventrrr_calendar_id`
  and `exports.eventrrr_event_ids` fill in. That closes the loop the Scout IQ spec asks for.
- The v1 `tags` and the `slug` / `name` / `eventrrr_name` keys inside `calendar` were dropped from `exportJson` on
  2026-11-04, after Prompt A went live.
