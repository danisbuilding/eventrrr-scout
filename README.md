# eventrrr-scout

Finds public events in a city, scores them, and produces a review dashboard so
curated calendars for [Eventrrr](https://eventrrr.com) can be built fast.

Run by Claude (cloud session + DP's Mac via the desktop bridge). Python does the
deterministic parts; Claude does the gathering, extraction and judgment.

## Pipeline

| Stage | What | Where it runs | Code |
|---|---|---|---|
| 1 Sources | Seed list of sites, IG handles, umbrella events | repo | `sources.yaml` |
| 2 Sweep | Fetch each source → raw items | Claude tools (web search, Firecrawl, Apify IG); LLM scouts on the Mac | `scout/adapters/`, `scouts/` |
| 3 Extract | Raw item → structured event(s) | Claude, using `prompts/extract.md` | `schema/event.json` |
| 4 Normalize + dedupe | Same event from N sources → one record | Python | `scout/normalize.py` |
| 5 Score | Highlight score from the rubric | Python + Claude rationale | `scout/score.py`, `prompts/highlight.md` |
| 6 Dashboard | Tabs per category, Highlights, Family filter, Keep/Skip | Artifact | `scout/render.py` |
| 7 Learn | Keep/Skip decisions feed the next run's rubric | repo | `decisions/` |

## Layout

```
sources.yaml            seed sources (edit freely)
taxonomy.yaml           12 Eventrrr categories + definitions, flags, highlight rubric
schema/raw_item.json    adapter output contract (every source emits this)
schema/event.json       normalized event record
prompts/                extraction + highlight prompts used by Claude
scout/                  python: normalize, score, render
scout/adapters/         one doc per source type: how it's swept, what it emits
scouts/                 OpenAI / Gemini parallel scouts (run on the Mac, keys in .env)
inbox/<run>/<source>.jsonl   raw items from a sweep
runs/<run>/events.json       normalized + scored events
runs/<run>/dashboard.html    review page (also published as an Artifact)
decisions/<run>.json         Keep / Skip / notes from review
```

A run is named `YYYY-MM-DD[-slug]`, e.g. `2026-10-28-dia-de-muertos`.

## Running a sweep (v1, on demand)

1. Edit `sources.yaml` if needed (add handles, set the `window` and `umbrella`).
2. Tell Claude: "run the scout for <window/umbrella>". Claude:
   - sweeps every enabled source into `inbox/<run>/`
   - extracts events with `prompts/extract.md`
   - runs `python scout/normalize.py <run>` then `python scout/score.py <run>`
   - runs `python scout/render.py <run>` and publishes the dashboard
3. Review in the dashboard: Keep / Skip, copy links into Eventrrr's capture.
4. Export decisions to `decisions/<run>.json` (dashboard has an Export button).

## Adding a source type later (e.g. WhatsApp)

Write `scout/adapters/<type>.md` describing how raw items are produced, and make
sure the output matches `schema/raw_item.json`. Nothing downstream changes.
WhatsApp plan: export from Instinct (or a native chat export) → `whatsapp` adapter.
