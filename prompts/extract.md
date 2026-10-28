# Extraction prompt

Used by Claude (and by the LLM scouts) to turn raw items into events. Output must
validate against `schema/event.json` minus the fields marked "set by".

## Instructions

You are reading posts, captions and pages from Mexico City event sources. For each
distinct, dated, real-world event you find, emit one event object. Rules:

1. **Only dated events.** No "coming soon", no generic venue promos, no past events.
   Run window: {{window_from}} to {{window_to}}. Keep events inside it, plus anything
   that is part of the umbrella "{{umbrella}}" even if a day outside.
2. **Title as published.** Spanish stays Spanish. Strip emoji and ALL CAPS shouting.
3. **Dates.** Resolve relative dates ("este sábado") from `posted_at`. Timezone
   America/Mexico_City. If no time is given, `all_day: true`. If the date cannot be
   resolved, drop the event.
4. **Neighborhood.** Use the printed colonia. Otherwise infer from the venue name or
   address if you are confident; else null.
5. **Price.** `price_text` verbatim; `price_min` 0 for free / "entrada libre".
6. **Link.** Prefer tickets > organizer page > the source post itself. Never null if
   a `source_url` exists.
7. **Category.** Exactly one from the list in `taxonomy.yaml`, using its definitions.
   `category_alt` only when two fit equally.
8. **family_friendly.** True only when stated or obvious (kids' workshop, daytime
   ofrenda in a park). A club night is false.
9. **umbrella.** "{{umbrella}}" when the event is part of it; else null.
10. **recurring.** True for weekly residencies, every-Sunday markets, etc.
11. **signals.** For each signal in `taxonomy.yaml → highlight.signals` and
    `penalties`, set true/false based on what the text supports. Do not guess
    `corroborated`; normalize.py sets it from source counts.
12. **sources.** The RawItem id(s) you read this from.
13. **source_links / source_excerpt / image_url.** `source_links` = one `{name, url}` per
    RawItem it came from (name like "IG @cdmxsecreta" or "Chilango"); `source_excerpt` = the
    most relevant ~600 chars of the original text, verbatim; `image_url` = the flyer/image
    URL from the RawItem's `media`, if any.
14. **confidence.** 0.9+ when date, venue and link are all explicit; 0.6 when one is
    inferred; below 0.5 drop it.

Output: a JSON array. No prose.
