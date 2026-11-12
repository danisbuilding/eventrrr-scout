# eventrrr-scout

Finds public events in a city, scores them, and produces a review dashboard so
curated calendars for [Eventrrr](https://eventrrr.com) can be built fast.

Run by Claude from a cloud session. Python does the deterministic parts; Claude does the
gathering, extraction and judgment. Review happens at https://scout.eventrrr.com (Google
login, allow-listed), served from `site/` by GitHub Pages; events read from this repo, decisions stored in Eventrrr's Supabase.

## Pipeline

| Stage | What | Where it runs | Code |
|---|---|---|---|
| 1 Sources | Seed list of sites, IG handles, umbrella events | repo | `sources.yaml` |
| 2 Sweep | Fetch each source → raw items | Web: Claude tools (search, Firecrawl). Instagram + LLM scouts: GitHub Actions `sweep` workflow | `scout/adapters/`, `scouts/`, `.github/workflows/` |
| 3 Extract | Raw item → structured event(s) | Claude, using `prompts/extract.md` | `schema/event.json` |
| 4 Normalize + dedupe | Same event from N sources → one record; past events and events already published in an earlier run are dropped (`runs/<run>/dropped.json` says why) | Python | `scout/normalize.py` |
| 4b Venues | Each venue looked up once on Google Maps (Places API (New)); 4.8+ with 50+ reviews sets `signals.venue_rated`; cache in `data/venues.json` | Python | `scout/venues.py` |
| 5 Score | Highlight score from the rubric | Python + Claude rationale | `scout/score.py`, `prompts/highlight.md` |
| 6 Publish | `runs/index.json` + `runs/<run>/events.json` pushed to the repo; review at scout.eventrrr.com | `scout/publish.py` + git push | `site/` |
| 7 Learn | Keep/Skip decisions (Supabase `scout_decisions`) feed the next run's rubric | DP presses "Copy decisions" and pastes to Claude | `decisions/` |
| 8 Write to Scout IQ | Events, occurrences, observations into the Scout IQ database; prices and `is_free` via `normalize.price_fields`; older misreads of the same page get `superseded_by` | GitHub Actions (`pipeline.yml`) | `scout/iq_write.py` |
| 9 Tag | Kid-friendly, outdoor, venue type, activity, in-metro, embeddings, English title / description / price → `event_tags` | GitHub Actions (`accuracy.yml`, after each run and nightly) | `scout/enrich.py` |
| 10 Check | Re-reads source pages; flags in `search_flags`; writes confident start times and prices back into `events`; report in issue #1 | GitHub Actions (`accuracy.yml`) | `scout/accuracy.py` |

## Layout

```
sources.yaml            seed sources (edit freely)
taxonomy.yaml           12 Eventrrr categories + definitions, flags, highlight rubric
schema/raw_item.json    adapter output contract (every source emits this)
schema/event.json       normalized event record
prompts/                extraction + highlight prompts used by Claude
scout/                  python: normalize, score, publish (runs index), render (offline mock)
site/                   the review app (index.html, app.js, styles.css, config.js) → GitHub Pages
supabase/schema.sql     tables + RLS for scout_* (applied via Bolt; only scout_decisions is used by the site)
supabase/profiles.sql   scout_profiles + scout_assignments (the Sort tab; applied via Bolt)
profiles/<slug>.md      one charter per simulated curator: persona, what I think DP is doing, surprises
scout/adapters/         one doc per source type: how it's swept, what it emits
scouts/                 OpenAI / Gemini parallel scouts (GitHub Actions; keys are repo secrets)
.github/workflows/      sweep (Instagram + scouts) and thumbs workflows
inbox/<run>/<source>.jsonl   raw items from a sweep
runs/<run>/events.json       normalized + scored events
runs/<run>/dashboard.html    offline/mock render of the same UI (optional)
decisions/<run>.json         Keep / Skip / notes from review
```

A run is named `YYYY-MM-DD[-slug]`, e.g. `2026-10-28-dia-de-muertos`.

## Data quality and English (2026-11-12)

Scout IQ is the corrected copy every reader uses (scout.eventrrr.com, its export to Eventrrr, and Eventrrr Search):

| Rule | Where |
|---|---|
| The date is when the event happens, never a sign-up or ticket deadline; weekday and day number must agree; any stated start time is recorded | `prompts/extract.md` |
| Free only when the price text says so; a 0 without it is unknown (null) | `prompts/extract.md`, `normalize.price_fields` |
| A start time or price the accuracy check found survives later re-reads | `iq_write.py` upsert |
| A row a later read replaced (same page and title, new date) gets `superseded_by`; readers skip it | `iq_write.py`, `accuracy.py`, Search |
| Text shows in English (`event_tags.title_en`, `description_en`, `price_en`, proper names kept); originals stay in `events` | `enrich.py`; the site overlays them via rpc `scout_english`; exports send `title_original` too |

Scout sweeps Mexico City only for now (`CITY_SLUG` in `iq_write.py`, `cdmx` in `accuracy.py`). `cities.search_status`
(live / soon / hidden) decides Eventrrr Search's city menu; a new city needs sources and a per-city sweep first.
Full table and function list: "Since v1" in [Scout IQ: Database Spec v1](https://claude.ai/artifact/C98BvUrDVz9DVYyvroeGxw).

## Calendars (the Review tab)

Every event from every run lands in one pool on the Review tab. DP taps calendar chips (an event can belong to
several, or to None); assignments live in `scout_assignments`. A calendar (`scout_profiles` row) is ongoing
(trains the sorter) or one-off (has an end date, hides after it); each maps to an Eventrrr account.
"Export to Eventrrr (n new)" copies the calendar's upcoming, not-yet-exported events as one import JSON tagged
with the calendar slug; the ledger is `scout_exports` (`supabase/exports.sql`), with "Undo last export".
"Copy session" copies all assignments as JSON to paste to Claude, who updates `profiles/<slug>.md`. After ~5–6
sessions a first-pass sorter in the pipeline proposes assignments (`source: suggested`, dashed chips).

## Running a sweep

Runs tab on scout.eventrrr.com → **Start sweep**. The edge function `scout-trigger` dispatches
`.github/workflows/pipeline.yml`, which gathers (Apify Instagram, web sweep, optional LLM scouts), extracts
(gpt-5-mini), normalizes, scores, publishes and commits. The run appears in the Events and Sort tabs when done.
Handover docs (Claude docs; pointers in `docs/`): build → `docs/handover-scout.md`, sorting → `docs/handover-sorting.md`.

## Adding a source type later (e.g. WhatsApp)

Write `scout/adapters/<type>.md` describing how raw items are produced, and make
sure the output matches `schema/raw_item.json`. Nothing downstream changes.
WhatsApp plan: export from Instinct (or a native chat export) → `whatsapp` adapter.

## Secrets (GitHub → Settings → Secrets and variables → Actions)

| Secret | Used by |
|---|---|
| `APIFY_TOKEN` | Instagram sweep |
| `OPENAI_API_KEY` | OpenAI scout |
| `GEMINI_API_KEY` | Gemini scout |
| `SCOUT_IQ_DB_URL` | Writing to Scout IQ, tagging, accuracy check (`scout_pipeline` role) |

Nothing else holds keys. `scouts/.env` still works for a local run and is git-ignored.
