# Profiles

One file per simulated curator. `slug` matches `scout_profiles.slug` in Supabase; the table holds the live
persona/handle/active flag (editable from the Sort tab), these files hold the learning: the charter, my read of
DP's sorting, and the surprises. Sessions are committed under `sessions/` by the Sort tab's "Copy session" →
Claude, and later by an analysis workflow.

## The one principle under all of them (confirmed by DP after session 1)

The reader doesn't know the act, the chef or the scene. Ask: **would I send a friend there cold?** That is why
an unknown band at an uncomfortable venue fails but passes at a pleasant one (music), why intense niche genres fail
however good the club (nightlife), why a special menu that runs for weeks isn't an event (foodie), and why a long
cold walk along Reforma fails where standing in the Zócalo passes (cultural). Category and author are necessary;
the imagined visit decides.

## Tagging a second profile (DP, session 2)

An event gets a second profile when it is at least *good* for that profile, not merely possible. Very good as a
club night and mediocre as a date → nightlife only. A film festival that is very good as culture and good as a
date → both. Price can decide: a $1,300-a-head dinner is foodie, not a general date suggestion.

## Scoring (from 2026-11-03)

Sorting is a 1–5 score per (event, profile), not a yes/no tag; `SCORING.md` is the scale DP sees in the app.
No row on a profile = not on that calendar. **None** = looked at, fits no calendar; **unclear** = looked at,
the listing didn't say enough. The score settles competition for the slots (3–4 per day, 4–5 ongoing per week); only a 1 excludes; "N more" carries only 3+ events that lost a slot, 2s never overflow. A 1 or 2 is a rank, not a rejection: the 13 events that were None in sessions 1–2
all came back as 1s and 2s once a scale existed, so read pre-scoring Nones as "wouldn't feature", not "doesn't belong".
Calibration: the average event is a 1 or 2 (an okay event); 3 is a high score; 4 rare; 5 exceptional (DP, 2026-11-03).
Duplicates scored inconsistently: the first score to appear (by `updated_at`) is the call (DP, 2026-11-03).
Each charter now describes what makes a 5, 4, 3, 2 and 1 for that calendar; the second-profile rule is "at least a 3
there". Frontmatter `charter_version` bumps on every change; the app stamps it on each new score.
