# Bolt prompt: Eventrrr in English (original title kept)

Status: written 2026-11-12, not yet run. After it runs, add `title_original` to the field list in
`docs/eventrrr-import-prompt.md` (the scout export already sends it).

```
Eventrrr's audience is English speakers, so event text should be in English no matter what language the source was in. Keep the original title so people can match it to the flyer or listing. Make exactly these changes and nothing else.

## 1. Database

Add one nullable column to `events`: `title_original text` (max 200 chars). No other schema changes. RLS: it follows the same rules as `title` (visible wherever title is visible, including share links and public curated calendars).

## 2. AI extractor (screenshots, photos, links, pasted text)

Change the extraction prompt so that:
- `title`, `description` and `price_text` are written in natural English for an English-speaking visitor, whatever the source language.
- Proper names stay exactly as written: artists, bands, people, venues, exhibitions, festivals, works, brands (e.g. "Mini Domingo", "FILIJ", "Bestiario fantástico" stay). Translate only the descriptive words: "Taller de Pan de Muerto" → "Pan de Muerto workshop"; "Garbage se presentará en el Zócalo" → "Garbage live at the Zócalo". Drop ticket-site prefixes like "PRECIOS:" or "SOLD OUT:".
- Price text in English: "Entrada libre" → "Free entry", "Actividad con costo" → "Paid activity", "PRECIOS: ver enlace" → "See the listing for prices"; amounts and currency unchanged. `price_min` 0 only when the source says free.
- `title_original` = the title exactly as published, only when it differs from the English title; otherwise null.
- `venue`, `address` and `neighborhood` stay as published (they're names and addresses).
The Manual tab is unchanged: whatever the user types is saved as typed, `title_original` null.

## 3. JSON import (Paste text tab, src/lib/scoutImport.ts)

Also read `title_original` from each imported event (string, trim, cap 200, else null) and save it. Everything else about the import stays as it is.

## 4. Display

Wherever the event detail sheet shows the title (own calendar, private share link, public curated calendar page), show `title_original` directly under the title when it's present and different: 12px, the muted text color, one line with ellipsis. Not on list rows or cards.

## 5. Copies

"Add to mine" and any other place that copies an event copies `title_original` along with the title.

## 6. One-time backfill of existing events

Create a Supabase edge function `translate-backfill` (service role, callable only by me — check my user id) that processes events where `title_original` is null, 20 per call, oldest first, skipping titles starting with "[Sample]":
- Send title, description and price_text to the same LLM the extractor uses, with the rules in section 2, asking for JSON {already_english: bool, title, description, price_text}.
- If already_english is true, set `title_original` to '' (empty string, meaning "checked, nothing to keep") and change nothing else.
- Otherwise set `title_original` = the old title, and replace title, description and price_text with the English versions. Never touch dates, venue, address, neighborhood, url, category, price_min, notes or anything else.
- Return {processed, translated, remaining}.
Add a temporary button for me in Settings, "Translate existing events", that calls it repeatedly until remaining is 0 and shows progress. Treat '' the same as null when displaying (don't show an empty line).
```
