-- Accuracy flags: written nightly by scout/accuracy.py (GitHub Actions, as scout_pipeline), read by
-- search_events (eventrrr-search) and by reviewers. Safe to re-run.
--
-- check_name   severity  meaning
-- date_mismatch demote   the source page gives a different date than Scout stored → Search moves it to "Show more"
-- time_found    info     Scout stored "all day" but the page gives a start time → Search shows that time
-- time_mismatch info     the page gives a start time more than 30 min off the stored one
-- source_gone   info     the source page answers 404/410
-- not_on_page   info     the page loads but the event isn't on it (listing pages rotate; often harmless)
-- cross_source  info     another source lists a look-alike event within 3 days on a different date
-- odd_time      info     timed event starting 03:00–06:59, or ending before it starts
--
-- status: open (found on the latest check) | resolved (no longer found) | dismissed (a person said it's fine;
-- the nightly check leaves dismissed flags alone).

create table if not exists search_flags (
  id                  uuid primary key default gen_random_uuid(),
  event_id            uuid not null references events(id) on delete cascade,
  check_name          text not null,
  severity            text not null default 'info' check (severity in ('demote', 'info')),
  detail              jsonb not null default '{}'::jsonb,
  suggested_starts_at timestamptz,
  status              text not null default 'open' check (status in ('open', 'resolved', 'dismissed')),
  first_seen          timestamptz not null default now(),
  last_seen           timestamptz not null default now(),
  unique (event_id, check_name)
);
create index if not exists search_flags_open_idx on search_flags (event_id) where status = 'open';

alter table search_flags enable row level security;
grant select, insert, update on search_flags to scout_pipeline;
drop policy if exists pipeline_read   on search_flags;
drop policy if exists pipeline_insert on search_flags;
drop policy if exists pipeline_update on search_flags;
create policy pipeline_read   on search_flags for select to scout_pipeline using (true);
create policy pipeline_insert on search_flags for insert to scout_pipeline with check (true);
create policy pipeline_update on search_flags for update to scout_pipeline using (true) with check (true);

do $$
begin
  if exists (select 1 from pg_proc where proname = 'scout_is_reviewer') then
    execute 'drop policy if exists reviewer_read on search_flags';
    execute 'drop policy if exists reviewer_update on search_flags';
    execute 'create policy reviewer_read on search_flags for select to authenticated using (scout_is_reviewer())';
    execute 'create policy reviewer_update on search_flags for update to authenticated using (scout_is_reviewer()) with check (scout_is_reviewer())';
    execute 'grant select, update (status) on search_flags to authenticated';
  end if;
end $$;

-- The database checks in scout/accuracy.py use trigram similarity and Search's accent folding.
grant usage on schema extensions to scout_pipeline;
grant execute on function public.search_fold(text) to scout_pipeline;
