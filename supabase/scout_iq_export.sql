-- Scout IQ, step 5: calendars and exports, after scout_iq_review.sql (step 4).
-- A calendar is profile × city × Eventrrr account; an export is one batch sent to one calendar (occurrence ids,
-- tier per occurrence, and the Eventrrr ids pasted back). Replaces the app's export_ledger.
-- Paste into the SQL editor and run once; safe to re-run.

set client_min_messages = warning;

create table if not exists calendars (
  id                    uuid primary key default gen_random_uuid(),
  profile_id            uuid not null references profiles(id),
  city_id               uuid not null references cities(id),
  eventrrr_account      text not null,                 -- the curator account (profiles.handle, else the slug)
  eventrrr_calendar_id  text,                          -- pasted back from Eventrrr after the first import
  handle_slug           text not null,                 -- "<profile>-<city>", e.g. date-night-cdmx
  created_at            timestamptz not null default now(),
  unique (profile_id, city_id, eventrrr_account)
);

create table if not exists exports (
  id                   uuid primary key default gen_random_uuid(),
  calendar_id          uuid not null references calendars(id),
  run_id               uuid references runs(id),       -- null when the batch spans runs (the Sort pool does)
  exported_at          timestamptz not null default now(),
  exported_by          text,
  payload_ref          text,                           -- Supabase Storage path (step 6)
  occurrence_ids       uuid[] not null,
  tier_by_occurrence   jsonb not null default '{}',    -- {occurrence_id: "main" | "overflow"}
  eventrrr_event_ids   jsonb,                          -- pasted back from Eventrrr: [ids] or {occurrence_id: id}
  undone_at            timestamptz,                    -- "Undo last export": the batch no longer counts
  created_at           timestamptz not null default now()
);
create index if not exists exports_calendar_idx on exports (calendar_id, exported_at desc);

-- Carry over anything the step-4 ledger recorded, then retire it.
do $$
begin
  if to_regclass('public.export_ledger') is not null then
    insert into calendars (profile_id, city_id, eventrrr_account, handle_slug)
    select distinct l.profile_id, c.id, coalesce(p.handle, p.slug), p.slug || '-' || c.slug
    from export_ledger l join profiles p on p.id = l.profile_id cross join (select id, slug from cities where slug = 'cdmx') c
    on conflict (profile_id, city_id, eventrrr_account) do nothing;
    insert into exports (calendar_id, exported_at, exported_by, occurrence_ids, tier_by_occurrence)
    select cal.id, min(l.exported_at), min(l.exported_by), array_agg(l.occurrence_id), '{}'::jsonb
    from export_ledger l join profiles p on p.id = l.profile_id
    join calendars cal on cal.profile_id = l.profile_id and cal.eventrrr_account = coalesce(p.handle, p.slug)
    group by cal.id, l.batch;
    drop view if exists app_exports;
    drop table export_ledger;
  end if;
end $$;

-- What the app reads: one row per exported occurrence that still counts.
create or replace view app_exports as
select p.slug as profile, r.slug as run, e.key, x.id::text as batch, x.exported_at,
       x.tier_by_occurrence ->> o.id::text as tier, x.calendar_id
from exports x
join calendars cal on cal.id = x.calendar_id
join profiles p on p.id = cal.profile_id
cross join lateral unnest(x.occurrence_ids) as u(occurrence_id)
join occurrences o on o.id = u.occurrence_id
join events e on e.id = o.event_id
join runs r on r.id = e.first_seen_run_id
where x.undone_at is null;

create or replace view app_calendars as
select cal.id, p.slug as profile, c.slug as city_slug, c.name as city, cal.eventrrr_account, cal.eventrrr_calendar_id, cal.handle_slug
from calendars cal join profiles p on p.id = cal.profile_id join cities c on c.id = cal.city_id;

alter view app_exports   set (security_invoker = on);
alter view app_calendars set (security_invoker = on);

alter table calendars enable row level security;
alter table exports   enable row level security;

grant select on calendars, exports, app_exports, app_calendars to authenticated;
grant insert on calendars, exports to authenticated;
grant update (eventrrr_calendar_id) on calendars to authenticated;             -- paste-back only
grant update (eventrrr_event_ids, undone_at) on exports to authenticated;      -- paste-back and undo only

drop policy if exists reviewer_read on calendars;
create policy reviewer_read on calendars for select to authenticated using (scout_is_reviewer());
drop policy if exists reviewer_insert on calendars;
create policy reviewer_insert on calendars for insert to authenticated with check (scout_is_reviewer());
drop policy if exists reviewer_update on calendars;
create policy reviewer_update on calendars for update to authenticated using (scout_is_reviewer()) with check (scout_is_reviewer());
drop policy if exists reviewer_read on exports;
create policy reviewer_read on exports for select to authenticated using (scout_is_reviewer());
drop policy if exists reviewer_insert on exports;
create policy reviewer_insert on exports for insert to authenticated with check (scout_is_reviewer());
drop policy if exists reviewer_update on exports;
create policy reviewer_update on exports for update to authenticated using (scout_is_reviewer()) with check (scout_is_reviewer());

grant select, insert on calendars, exports to scout_pipeline;
grant select on app_exports, app_calendars to scout_pipeline;
drop policy if exists pipeline_read on calendars;   create policy pipeline_read   on calendars for select to scout_pipeline using (true);
drop policy if exists pipeline_insert on calendars; create policy pipeline_insert on calendars for insert to scout_pipeline with check (true);
drop policy if exists pipeline_read on exports;     create policy pipeline_read   on exports for select to scout_pipeline using (true);
drop policy if exists pipeline_insert on exports;   create policy pipeline_insert on exports for insert to scout_pipeline with check (true);
