# Handover: processing Scout sorting sessions

For the chat that turns DP's sorting sessions into profile charters, and later into an automatic sorter.
Everything needed is in this doc plus the repo. No secrets are needed for this work.

## What this is

Eventrrr Scout (https://scout.eventrrr.com, repo `danisbuilding/eventrrr-scout`, GitHub Pages from `site/`)
sweeps Mexico City event sources and shows the results to DP. The **Sort tab** holds every event from every run
in one pool. DP assigns each event to zero or more **profiles**, simulated curators that each map to a separate
Eventrrr account:

| slug | name | gist |
|---|---|---|
| foodie | Food & Drink | who's cooking, real producers; not restaurant promos |
| cultural | Arts & Culture | openings, the small gallery over the blockbuster; not tourist packages |
| nightlife | Nightlife & Bars | lineup and crowd; a bar with no event is not an event |
| music | Live Music | small/mid venues, acts with a sound; not cover bands |
| active | Sports & Movement | runs, rides, pickup games; not wellness retreats |

**None** = DP looked and it fits no profile. Untouched = not reviewed yet. Both matter.

The judgment being learned: *would this profile's account feature it*, not *is it in this category*. A generic
restaurant's taco night is Food & Drink but not foodie. The most informative calls are category-says-yes /
DP-says-None.

Profiles are added, edited and archived by DP in the app (`scout_profiles` table in Supabase). The learning lives
in the repo as `profiles/<slug>.md`, which the app displays per profile.

## Where things live

| Thing | Where |
|---|---|
| Live assignments | Supabase `scout_assignments` (run, key, profile, source manual/suggested/confirmed, note, reason). Not readable from a chat; DP exports with **Copy session**. |
| Profiles (persona, handle, active) | Supabase `scout_profiles`; seeded by `supabase/profiles.sql` |
| Charters (the learning) | `profiles/<slug>.md` in the repo; rendered in the app's profile panel, body only (frontmatter stripped) |
| Session archive | `profiles/sessions/<YYYY-MM-DD>[-n].json` (create the folder on first use) |
| Event data | `runs/<run>/events.json`; `runs/index.json` lists runs |
| Scoring rubric | `taxonomy.yaml` (12 categories, highlight signals) |
| Design system | `design/design-system.md` (Neue Verdant) |
| App | `site/app.js` (Sort tab code under `// ---------- sort tab`), `site/index.html`, `site/styles.css` |

Push access: the Claude GitHub app is installed on the repo. In a new chat, add the repo
(`danisbuilding/eventrrr-scout`, push access), clone, work on `main`, push. Pages redeploys on any push touching
`site/**`; charter changes under `profiles/` need no deploy (the app fetches them from
raw.githubusercontent.com).

## The session JSON DP pastes

Produced by **Copy session** on the Sort tab:

```json
{
 "session": "2026-10-29",
 "profiles": [{"slug": "foodie", "name": "Food & Drink", "persona": "…"}, …],
 "assignments": [
  {"run": "2026-10-28-dia-de-muertos", "key": "ofrenda-monumental-zocalo|2026-10-31", "profile": "cultural",
   "source": "manual", "note": null, "updated_at": "…", "title": "…", "category": "Art & Exhibitions",
   "venue": "…", "neighborhood": "…", "price_text": "…", "starts_at": "…", "highlight": true, "url": "…",
   "source_excerpt": "first 300 chars"}
 ],
 "unsorted_count": 61
}
```

It is cumulative: every session contains all assignments to date, not just new ones. Diff against the last
archived session to find what changed. `profile: "none"` rows are the explicit no-fit calls. One event can appear
under several profiles. Full event records are in `runs/<run>/events.json` keyed by `key`.

## What to do with a session

1. Save it to `profiles/sessions/<session date>.json`. Diff against the previous archive.
2. For each profile (including None as a cross-cutting view), read `profiles/<slug>.md` and update:
   - **Charter**: rules as short declarative lines. Add, sharpen, or strike. Rules must be executable by a cheap
     model later, so prefer concrete tests ("named chef or producer in the listing") over vibes ("feels curated").
   - **Would never feature**: concrete exclusions with one example each.
   - **What I think you're doing**: 3–6 lines in second person, one hypothesis per line, each tied to specific
     events ("You put the MUAC installation on cultural but not the Jumex show; I think the difference is…").
     DP confirms or corrects these; the next session revises them.
   - **Surprises**: events placed where the rules so far wouldn't predict, and events DP skipped that the rules
     would include. These are the questions for DP.
   - Frontmatter: bump `sessions`, keep `status: learning` until step 2 below.
   - Include 3–5 worked examples per profile (title, DP's call, the reason), since cheap models follow examples
     better than abstractions. Keep each file under ~120 lines; condense rather than append forever.
3. Commit (`profiles: session <date>`), push.
4. Reply to DP with a table: profile · what changed in the charter · open questions. Keep it short; the detail is
   in the files. Ask the questions as questions, not as corrections.

Do not restate DP's calls as rules he hasn't made. One instance is an observation; a rule needs a pattern across
events or DP's explicit confirmation. Mark hypotheses as hypotheses.

## Steps already planned (do them when the data supports them)

**Step 2, after ~3 sessions: first-pass sorter in the pipeline.** Add `scout/sort.py` after `score.py` in
`.github/workflows/pipeline.yml`: for each new event, a cheap model (gpt‑5‑mini, same key and call pattern as
`scout/extract.py`) reads the active charters and emits `{key, profile, reason}` proposals. Write them to
`runs/<run>/suggestions.json` in the repo rather than into Supabase; the pipeline has no Supabase credentials and
should not get any. The app reads that file, shows proposals as dashed chips (`.pchip.sugg` already styled) with
the reason on hover, and DP's tap saves `source: confirmed` to `scout_assignments`. Profiles are read from the
repo files (slug list = `profiles/*.md`), so an archived profile needs its file marked `status: archived`.

**Step 3, per profile when agreement is high: Auto.** The app computes agreement per profile from the last N
proposals vs DP's confirmed/changed calls and shows it in the profile panel, with the overrides listed (not just
the average; easy cases inflate it). A per-profile **Auto** toggle (a column on `scout_profiles`) makes proposals
exportable without confirmation; keep a "Review auto picks" filter so DP can spot-check. Overrides in Auto mode
still feed the next charter update.

**Also pending, unrelated to sorting:** the highlight rubric in `taxonomy.yaml` is too generous (55/102
highlighted on the first run); tune it from DP's Keep/Skip decisions once he has made some.

## Constraints to keep

- Never ask for or paste secrets. API keys live only in GitHub Actions secrets; the Supabase anon key in
  `site/config.js` is public by design. If DP pastes a session token or URL with a token, tell him to sign out.
- Don't touch eventrrr.com DNS (apex/www belong to Bolt); only the `scout` CNAME is Scout's.
- Don't cancel or trigger DP's workflow runs without his say-so.
- UI uses his design system (`design/`); English UI, event titles as published.
- He wants concise answers, tables where they help, honest pushback, no one-by-one manual steps.

## Prompt DP can use to start the next chat

> Process this Scout sorting session per docs/handover-sorting.md in danisbuilding/eventrrr-scout. Here's the
> session JSON: [paste]
