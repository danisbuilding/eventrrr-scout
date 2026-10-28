# Bolt prompt: JSON import on the Paste text tab

This is the import contract the scout exports to. Keep `scout/dashboard_template.html`
(`exportJson`) and this prompt in sync.

```
Let the + sheet's Paste text tab accept a JSON block from my scouting tool and insert the events directly, skipping the AI extractor. Don't change anything else. Plain text pasted into the same tab must behave exactly as it does today.

## 1. Detection

When the user taps Review on the Paste text tab, trim the text. If it parses as JSON AND the top-level object has `"eventrrr_import": 1` and an `events` array, treat it as an import (section 2). Otherwise, send it to the extractor exactly as today. Never try the extractor on something that failed import validation; show the error instead.

Import payload shape:
{
  "eventrrr_import": 1,
  "source": "eventrrr-scout",
  "run": "2026-10-28-dia-de-muertos",
  "events": [
    {
      "title": "Ofrenda Monumental en el Zócalo",
      "starts_at": "2026-10-31T10:00:00-06:00",
      "ends_at": null,
      "all_day": true,
      "timezone": "America/Mexico_City",
      "venue": "Zócalo",
      "address": "Plaza de la Constitución s/n",
      "neighborhood": "Centro",
      "price_text": "Entrada libre",
      "price_min": 0,
      "currency": "MXN",
      "url": "https://example.org/ofrenda",
      "category": "Art & Exhibitions",
      "description": "The city's flagship Día de Muertos ofrenda.",
      "public_note": null
    }
  ]
}

## 2. Validation (client-side, before any insert)

Reject the whole paste with one error line under the field (13px #b91c1c) if any of these fail; don't insert a partial batch:
- `events` has 1 to 100 items; otherwise "Import must have 1–100 events."
- Each event has a non-empty `title` (string, ≤ 200 chars) and a `starts_at` that parses as an ISO 8601 date-time; otherwise "Event {n}: missing title or date."

Per event, read ONLY these fields and ignore every other key in the object: title, starts_at, ends_at, all_day, timezone, venue, address, neighborhood, price_text, price_min, currency, url, category, description, public_note. Coerce:
- `all_day`: boolean, default false. `timezone`: default "America/Mexico_City".
- `url`: keep only if it starts with `http://` or `https://`; otherwise null.
- `category`: must be one of the values in the `CATEGORIES` constant (src/lib/constants.ts); otherwise "Other".
- `price_min`: number or null. `currency`: 3-letter string, default "MXN".
- Strings: trim; cap venue/address/neighborhood/price_text at 200 chars, description and public_note at 1000.

Never take `user_id`, `status`, `is_private`, `copied_from_event_id`, `capture_id`, `image_path`, calendar ids, or any other column from the payload.

## 3. Insert

Insert each event the same way the Manual tab inserts one, in one batch:
- `user_id` = the signed-in user; `status` = the inbox "To review" value
- `source_type` = 'import'; `source_label` = payload `source` (default "Import") plus " · " plus payload `run` when present; `source_url` = null
- `title_original` = title; `flagged_fields` empty; `confidence` = 1; `neighborhood_inferred` = false; `image_path` null; `capture_id` null; `tags` empty; `notes` null
- `public_note` from the payload (nullable)

The "Also add to: {calendar}" chip applies: after the insert, add a `calendar_events` row for every new event, exactly as Prompt 5 does for other captures. The "Times in" chip is ignored for imports (each event carries its own timezone).

Run the existing likely-duplicate check per imported event against the user's other events, exactly as the Inbox does today, so duplicates show the Merge / Keep both choice on their Inbox cards. Don't add new duplicate logic.

On success, close the sheet and show the existing toast style: "{N} events added to your Inbox."

## 4. Don't

- Don't call the extractor edge functions for an import.
- Don't add a new tab, route, edge function, table, column, or RLS policy.
- Don't change how plain text, links, photos or Manual captures work.
- Don't let the import set status, visibility, ownership or calendars from the payload.

## Test, then tell me

1. Paste the sample payload above with 2 events, "Also add to" set to a calendar, tap Review: both appear in the Inbox as To review, category chips correct, calendar chip showing, source label "eventrrr-scout · 2026-10-28-dia-de-muertos". Open one: venue, address, neighborhood, price and link are exact; the Times in chip had no effect.
2. Paste the same payload again: both cards show the Merge / Keep both duplicate choice.
3. Paste a payload where one event has `"url": "javascript:alert(1)"` and `"category": "Nope"`: it imports with no link and category Other.
4. Paste a payload with an extra key `"user_id": "00000000-0000-0000-0000-000000000000"` and `"status": "going"`: the event is created for the signed-in user as To review; the extra keys are ignored.
5. Paste a payload with 101 events: rejected with the error, nothing inserted. Paste one with an event missing `starts_at`: rejected, nothing inserted.
6. Paste ordinary text ("Ceramics class Sunday 4pm, Roma"): goes through the extractor as before.
7. Paste malformed JSON that starts with `{`: goes through the extractor as before (it isn't a valid import).
8. Tell me the file where the detection and validation live.
```
