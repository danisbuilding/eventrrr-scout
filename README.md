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
| 4 Normalize + dedupe | Same event from N sources → one record | Python | `scout/normalize.py` |
| 5 Score | Highlight score from the rubric | Python + Claude rationale | `scout/score.py`, `prompts/highlight.md` |
| 6 Publish | `runs/index.json` + `runs/<run>/events.json` pushed to the repo; review at scout.eventrrr.com | `scout/publish.py` + git push | `site/` |
| 7 Learn | Keep/Skip decisions (Supabase `scout_decisions`) feed the next run's rubric | DP presses "Copy decisions" and pastes to Claude | `decisions/` |

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

## Profiles (the Sort tab)

Every event from every run lands in one pool on the Sort tab. DP taps profile chips (an event can belong to
several, or to None); assignments live in `scout_assignments`. Each profile is a separate Eventrrr account, so
"Export to Eventrrr (n)" on a profile copies that profile's upcoming events as one import JSON. "Copy session"
copies all assignments as JSON to paste to Claude, who updates `profiles/<slug>.md`. After ~5–6 sessions a
first-pass sorter in the pipeline proposes assignments (`source: suggested`, dashed chips) for DP to confirm.

## Running a sweep (v1, on demand)

1. Edit `sources.yaml` if needed (add handles, set the `window` and `umbrella`).
2. Tell Claude: "run the scout for <window/umbrella>". Claude:
   - triggers `gh workflow run sweep.yml` (Instagram via Apify + OpenAI/Gemini scouts → `inbox/<run>/`, committed by the bot)
   - sweeps the web sources itself into `inbox/<run>/`
   - extracts events with `prompts/extract.md`
   - runs `python scout/normalize.py <run>` then `python scout/score.py <run>`
   - runs `python scout/publish.py <run>` and pushes → the run appears at scout.eventrrr.com
3. Review there: Keep / Skip, notes, tick rows, **Export to Eventrrr** → paste into Eventrrr → Paste text.
4. Before the next run, press **Copy decisions** and paste to Claude; the rubric gets tuned from them.

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

Nothing else holds keys. `scouts/.env` still works for a local run and is git-ignored.
