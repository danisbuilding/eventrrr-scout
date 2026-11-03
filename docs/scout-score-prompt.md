# Bolt prompt: scores on scout_assignments (2026-11-03)

Paste the block below into Bolt for the Eventrrr project. Ask for the output verbatim.

---

In the Supabase database, run this SQL exactly as written and show me the full output, including any errors. Do not change anything else in the app; these columns are used only by the external Scout tool at scout.eventrrr.com.

```sql
alter table scout_assignments add column if not exists score smallint check (score between 1 and 5);
alter table scout_assignments add column if not exists score_actor text default 'human' check (score_actor in ('human','sorter'));
alter table scout_assignments add column if not exists charter_version text;
create index if not exists scout_assignments_score on scout_assignments (profile, score);
select column_name, data_type, column_default from information_schema.columns where table_name = 'scout_assignments' order by ordinal_position;
```

---

Expected: the final select lists `run, key, profile, note, source, reason, updated_by, updated_at, score, score_actor, charter_version`. The existing RLS policy (`scout_assignments_all`) already covers the new columns; no policy change is needed.
