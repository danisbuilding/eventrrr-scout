-- Scout v4 (2026-11-03): 1–5 score per (event, profile). Safe to re-run.
-- score: 5 singular / 4 great / 3 good / 2 fine / 1 mediocre. NULL = tagged before scoring existed (legacy) or the 'none' row.
-- score_actor: who set the score. charter_version: the profile charter's frontmatter version in force when it was set.
alter table scout_assignments add column if not exists score smallint check (score between 1 and 5);
alter table scout_assignments add column if not exists score_actor text default 'human' check (score_actor in ('human','sorter'));
alter table scout_assignments add column if not exists charter_version text;
create index if not exists scout_assignments_score on scout_assignments (profile, score);
