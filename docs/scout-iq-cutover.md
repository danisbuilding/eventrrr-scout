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

## Later (not in this step)

- Step 5: `calendars`, `exports`, export v2; `export_ledger` goes away.
- Step 7: drop the old `scout_*` tables from Eventrrr via Bolt once this has run clean for a week.
