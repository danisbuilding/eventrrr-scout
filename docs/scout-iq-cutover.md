# Scout IQ cutover (step 4): moving the review side to DP's own Supabase project

Project: `https://tlwyhxvytmhpcgrismsz.supabase.co` (`eventrrr-scout`, free plan). Step 3 (pipeline tables, scoped
role, dual-write, keepalive) is live. This is the order for the review side. Each step is safe to repeat; nothing
here touches Eventrrr's project or the old `scout_*` tables, which keep working until the flag in step 6 flips.

| # | Who | What | Check |
|---|---|---|---|
| 1 | DP | SQL editor → paste and run `supabase/scout_iq_review.sql` (no placeholders). Reviewer allow-list = daniel.stringer@gmail.com and dib@dib.works; the script deactivates any other row | "Success. No rows returned"; Table Editor shows `profiles`, `assignments`, `reviews`, `reviewers`, `export_ledger` |
| 2 | DP | Authentication → Sign In / Providers → Google: enable, paste a Google OAuth client id + secret (Google Cloud Console → APIs & Services → Credentials → OAuth client, type Web; authorized redirect URI `https://tlwyhxvytmhpcgrismsz.supabase.co/auth/v1/callback`). Authentication → URL Configuration: Site URL `https://scout.eventrrr.com`, add `https://scout.eventrrr.com/**` to Redirect URLs | Provider shows Enabled |
| 3 | DP | Edge Functions → Deploy a new function via the editor, name `scout-trigger`, paste `supabase/functions/scout-trigger/index.ts`; Edge Functions → Secrets → add `GITHUB_SCOUT_TOKEN` (same value as in Eventrrr's project) | Function listed; without it the Runs and Sources tabs return "Sign in first" after the cutover |
| 4 | Claude | Pull the live `scout_*` rows from the signed-in app into `profiles/sessions/2026-11-03-migration.json`, commit | File in the repo |
| 5 | Claude | Run the `iq-backfill-review` workflow (reads that file) | Log: "written: N assignments, M reviews …"; nothing "not in Scout IQ" |
| 6 | DP | GitHub → Settings → Secrets and variables → Actions → **Variables** → New repository variable `SCOUT_IQ_LIVE` = `true`, then Actions → `pages` → Run workflow | `pages` log: "config.js → Scout IQ"; scout.eventrrr.com asks for Google sign-in again (new project) and the Sort tab shows the same scores |
| 7 | DP | Score something; Copy session; check it appears in Table Editor → `assignments` (append-only: a new row, nothing changed in place) | |

Rollback: set `SCOUT_IQ_LIVE` to `false` and re-run `pages`; the site returns to the old tables with nothing lost.

## What changes for the app

- `site/config.js` gets `schema: "iq"` and the new URL + publishable key, written by `pages.yml` from the
  `SCOUT_SUPABASE_URL` / `SCOUT_SUPABASE_ANON_KEY` secrets; the committed file stays on the legacy values.
- `iqProvider` in `site/app.js`: scores are inserted as `assignments` rows (never updated); taking a calendar off an
  event inserts a `withdrawn` row; None / Can't tell / Duplicate and the Events tab's Keep/Skip + note are `reviews`
  rows; `current_assignments` / `current_reviews` decide what counts. Event keys resolve to their `run` occurrence
  through `app_event_keys`; an event the pipeline has not written yet cannot be scored (the message says so).
- supabase-js 2.45.4 → 2.112.0 for the publishable-key format.
- The edge function is unchanged; it just needs to exist in the new project (step 3).

## Step 5 (export v2) — after step 4 is live

| # | Who | What | Check |
|---|---|---|---|
| 1 | DP | SQL editor → run `supabase/scout_iq_export.sql` (creates `calendars`, `exports`; retires `export_ledger`) | Table Editor shows `calendars`, `exports`; no `export_ledger` |
| 2 | — | Site already exports v2: payload carries `scout_export: "v2"`, `export_id`, a `calendar` block and `tier` per event; the Export button says "N new: M main, K overflow"; 2s without a slot wait in the pool | Export once; Table Editor → `exports` has the batch with `tier_by_occurrence` |
| 3 | DP | Bolt: run Prompt A from `docs/eventrrr-import-v2-prompt.md` (calendar match + tiers + reply block), later Prompt B (week bands, overflow) | Prompt's own tests |
| 4 | DP | After an import, paste Eventrrr's reply into the profile panel ("Record Eventrrr's reply") | `calendars.eventrrr_calendar_id`, `exports.eventrrr_event_ids` filled |

Until step 1 runs, exporting from the site fails to record (the copy still works) with "relation exports does not exist".

## Step 6 (raw text to Storage, nightly session dump)

| # | Who | What | Check |
|---|---|---|---|
| 1 | DP | Supabase → Storage → New bucket: name `raw`, **private** | Bucket listed |
| 2 | DP | Storage → Settings (or S3 Connection) → **S3 access keys** → New access key, description "github actions scout" → copy the Access key ID and Secret access key once; note the Region shown there | — |
| 3 | DP | GitHub → Settings → Secrets and variables → Actions: secrets `SCOUT_IQ_S3_ACCESS_KEY`, `SCOUT_IQ_S3_SECRET_KEY`; variable `SCOUT_IQ_S3_REGION` = the region from step 2 (e.g. `us-east-1`) | — |
| 4 | Claude | Run `iq-backfill` once more: uploads every raw inbox item of both runs to `raw/<run>/<item id>.txt` and sets `observations.raw_text_ref` | Log: "storage: N raw items uploaded"; bucket has two folders |
| 5 | — | `session-dump` runs nightly at 00:23 Mexico City and commits `profiles/sessions/<date>.json` only when assignments or reviews changed; run it by hand from the Actions tab to get one now | A new file under `profiles/sessions/` the morning after a sorting session |

Without the S3 keys the pipeline keeps writing everything else and leaves `raw_text_ref` null. The S3 keys reach Storage only (they cannot read tables), which is why they are allowed in Actions while the service key is not.

## Later

- Step 7: drop the old `scout_*` tables from Eventrrr via Bolt once this has run clean for a week.
- Auto-sort (sort.py writing sorter rows) once the charters have worked examples.
