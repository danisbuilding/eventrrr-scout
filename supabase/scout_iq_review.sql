-- Scout IQ, step 4: review-side tables in DP's own Supabase project, after scout_iq.sql (step 3).
-- profiles, assignments (append-only 1–5 rows), reviews (event looked at / doesn't fit / duplicate / Keep-Skip
-- note), reviewers (Google allow-list), export_ledger (the app's per-profile export bookkeeping until step 5's
-- exports), the views, and RLS for the app (anon key + Google sign-in, same model as before).
--
-- Paste into the SQL editor and run once; safe to re-run. No placeholders. Then: Authentication → Providers →
-- Google (see docs/scout-iq-cutover.md), and add your sign-in emails to `reviewers` if they differ from the two
-- seeded below.

set client_min_messages = warning;

-- ---------------------------------------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------------------------------------

create table if not exists reviewers (
  id          uuid primary key default gen_random_uuid(),
  email       text not null unique,
  google_sub  text,
  active      boolean not null default true,
  created_at  timestamptz not null default now()
);
insert into reviewers (email) values ('accounts@danielstringer.com'), ('daniel.stringer@gmail.com')
on conflict (email) do nothing;

create table if not exists profiles (
  id               uuid primary key default gen_random_uuid(),
  slug             text not null unique check (slug ~ '^[a-z0-9-]{2,30}$'),
  display_name     text not null,
  persona          text,
  handle           text,                              -- Eventrrr calendar name / account handle
  charter_path     text,                              -- profiles/<slug>.md in the repo
  charter_version  text,                              -- cache of the charter file's frontmatter
  kind             text not null default 'ongoing' check (kind in ('ongoing', 'oneoff')),
  ends_on          date,
  active           boolean not null default true,
  sort_order       integer not null default 100,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

-- Append-only. One row per scoring act; current_assignments picks the row that counts.
create table if not exists assignments (
  id               uuid primary key default gen_random_uuid(),
  occurrence_id    uuid not null references occurrences(id),
  profile_id       uuid not null references profiles(id),
  score            smallint check (score between 1 and 5),  -- null = legacy fit-only row (or withdrawn)
  actor            text not null check (actor in ('human', 'sorter')),
  actor_id         uuid references reviewers(id),           -- human rows
  charter_version  text,                                    -- (v) required for scored rows
  sorter_model     text,                                    -- (v) sorter rows
  legacy           boolean not null default false,          -- pre-strip human row, no score
  withdrawn        boolean not null default false,          -- the human took the profile off this occurrence
  source           text not null default 'manual' check (source in ('manual', 'suggested', 'confirmed')),
  note             text check (char_length(note) <= 140),
  created_at       timestamptz not null default now(),
  check (actor = 'sorter' or withdrawn or legacy or (score is not null and charter_version is not null))
);
create index if not exists assignments_current_idx on assignments (occurrence_id, profile_id, created_at desc);
create index if not exists assignments_profile_idx on assignments (profile_id, created_at desc);

-- Append-only. A row = a reviewer looked at the event. skip_reason: none | unclear | duplicate | skip | null.
-- decision/note carry the Events tab's Keep/Skip and 140-char public note. current_reviews = latest per event.
create table if not exists reviews (
  id           uuid primary key default gen_random_uuid(),
  event_id     uuid not null references events(id),
  reviewer_id  uuid references reviewers(id),
  reviewed_at  timestamptz not null default now(),
  decision     text check (decision in ('keep', 'skip')),
  skip_reason  text check (skip_reason in ('none', 'unclear', 'duplicate', 'skip')),
  note         text check (char_length(note) <= 140),
  created_at   timestamptz not null default now()
);
create index if not exists reviews_current_idx on reviews (event_id, reviewed_at desc);

-- The app's export bookkeeping (profile × occurrence × batch); "Undo last export" deletes a batch. Replaced by
-- `exports` + `calendars` in step 5.
create table if not exists export_ledger (
  id             uuid primary key default gen_random_uuid(),
  profile_id     uuid not null references profiles(id),
  occurrence_id  uuid not null references occurrences(id),
  batch          text not null,
  exported_by    text,
  exported_at    timestamptz not null default now(),
  unique (profile_id, occurrence_id)
);
create index if not exists export_ledger_batch_idx on export_ledger (profile_id, batch);

-- ---------------------------------------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------------------------------------

-- Latest human row per occurrence × profile (a withdrawn one counts as no human row), else the latest sorter row.
create or replace view current_assignments as
with human as (
  select distinct on (occurrence_id, profile_id) *
  from assignments where actor = 'human'
  order by occurrence_id, profile_id, created_at desc
), sorter as (
  select distinct on (occurrence_id, profile_id) *
  from assignments where actor = 'sorter'
  order by occurrence_id, profile_id, created_at desc
)
select coalesce(h.occurrence_id, s.occurrence_id) as occurrence_id,
       coalesce(h.profile_id, s.profile_id)       as profile_id,
       case when h.id is not null and not h.withdrawn then h.id else s.id end as assignment_id,
       case when h.id is not null and not h.withdrawn then h.score else s.score end as score,
       case when h.id is not null and not h.withdrawn then 'human' when s.id is not null then 'sorter' end as actor,
       case when h.id is not null and not h.withdrawn then h.actor_id end as actor_id,
       case when h.id is not null and not h.withdrawn then h.charter_version else s.charter_version end as charter_version,
       s.sorter_model,
       case when h.id is not null and not h.withdrawn then h.legacy else false end as legacy,
       case when h.id is not null and not h.withdrawn then h.source else s.source end as source,
       case when h.id is not null and not h.withdrawn then h.note else s.note end as note,
       case when h.id is not null and not h.withdrawn then h.created_at else s.created_at end as updated_at,
       s.score as sorter_score
from human h full outer join sorter s on h.occurrence_id = s.occurrence_id and h.profile_id = s.profile_id
where (h.id is not null and not h.withdrawn) or s.id is not null;

-- Latest review per event.
create or replace view current_reviews as
select distinct on (event_id) *
from reviews order by event_id, reviewed_at desc;

-- Max current score per event × profile (analysis only; export never rolls up).
create or replace view event_scores as
select o.event_id, ca.profile_id, max(ca.score) as score
from current_assignments ca join occurrences o on o.id = ca.occurrence_id
where ca.score is not null
group by 1, 2;

-- Human minus sorter per occurrence × profile, by charter and sorter version. A reviewed event with a sorter row
-- ≥ 3 on a profile and no human row on it after the review is an implicit reject on that profile.
create or replace view score_distance as
with human as (
  select distinct on (occurrence_id, profile_id) occurrence_id, profile_id, score, charter_version, created_at
  from assignments where actor = 'human' and not withdrawn and score is not null
  order by occurrence_id, profile_id, created_at desc
), sorter as (
  select distinct on (occurrence_id, profile_id) occurrence_id, profile_id, score, charter_version, sorter_model, created_at
  from assignments where actor = 'sorter'
  order by occurrence_id, profile_id, created_at desc
)
select s.occurrence_id, s.profile_id, o.event_id,
       h.score as human_score, s.score as sorter_score,
       h.score - s.score as distance,
       h.charter_version as human_charter_version, s.charter_version as sorter_charter_version, s.sorter_model,
       (h.score is null and s.score >= 3 and r.reviewed_at is not null and r.reviewed_at > s.created_at) as implicit_reject
from sorter s
join occurrences o on o.id = s.occurrence_id
left join human h on h.occurrence_id = s.occurrence_id and h.profile_id = s.profile_id
left join current_reviews r on r.event_id = o.event_id;

-- What the app reads: one row per event key × profile slug, shaped like the old scout_assignments.
create or replace view app_assignments as
select r.slug as run, e.key, p.slug as profile, ca.score, ca.actor as score_actor, ca.charter_version, ca.source,
       ca.note, ca.updated_at, ca.legacy, ca.sorter_score, ca.occurrence_id
from current_assignments ca
join occurrences o on o.id = ca.occurrence_id
join events e on e.id = o.event_id
join runs r on r.id = e.first_seen_run_id
join profiles p on p.id = ca.profile_id;

-- Event keys the app can score: the `run` occurrence of every event, with the run it was first seen in.
create or replace view app_event_keys as
select e.key, e.id as event_id, o.id as occurrence_id, r.slug as run
from events e join occurrences o on o.event_id = e.id and o.kind = 'run'
join runs r on r.id = e.first_seen_run_id;

create or replace view app_reviews as
select r.slug as run, e.key, cr.decision, cr.skip_reason, cr.note, cr.reviewed_at
from current_reviews cr join events e on e.id = cr.event_id join runs r on r.id = e.first_seen_run_id;

create or replace view app_exports as
select p.slug as profile, r.slug as run, e.key, x.batch, x.exported_at
from export_ledger x join profiles p on p.id = x.profile_id join occurrences o on o.id = x.occurrence_id
join events e on e.id = o.event_id join runs r on r.id = e.first_seen_run_id;

-- Views run as the caller, so the base tables' RLS applies to whoever reads them.
alter view current_assignments set (security_invoker = on);
alter view current_reviews     set (security_invoker = on);
alter view event_scores        set (security_invoker = on);
alter view score_distance      set (security_invoker = on);
alter view app_assignments     set (security_invoker = on);
alter view app_event_keys      set (security_invoker = on);
alter view app_reviews         set (security_invoker = on);
alter view app_exports         set (security_invoker = on);
alter view neighborhood_density set (security_invoker = on);

-- ---------------------------------------------------------------------------------------------------------
-- App access: anon key + Google sign-in; a reviewer is an active email on the list signed in through Google.
-- ---------------------------------------------------------------------------------------------------------

create or replace function scout_is_reviewer() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from reviewers
    where active and email = lower(auth.jwt() ->> 'email')
      and coalesce(auth.jwt() -> 'app_metadata' ->> 'provider', '') = 'google'
  );
$$;

create or replace function scout_reviewer_id() returns uuid
language sql stable security definer set search_path = public as $$
  select id from reviewers where active and email = lower(auth.jwt() ->> 'email') limit 1;
$$;

alter table reviewers      enable row level security;
alter table profiles       enable row level security;
alter table assignments    enable row level security;
alter table reviews        enable row level security;
alter table export_ledger  enable row level security;

revoke all on all tables in schema public from anon;
grant usage on schema public to authenticated;
grant select on cities, runs, events, occurrences, venues, organizers, profiles, assignments, reviews, reviewers,
  export_ledger, current_assignments, current_reviews, event_scores, score_distance, app_assignments,
  app_event_keys, app_reviews, app_exports to authenticated;
grant insert on assignments, reviews to authenticated;            -- append-only: no update, no delete
grant insert, update on profiles to authenticated;
grant insert, delete on export_ledger to authenticated;           -- "Undo last export"

do $$
declare t text;
begin
  foreach t in array array['cities','runs','events','occurrences','venues','organizers','profiles','assignments','reviews','reviewers','export_ledger'] loop
    execute format('drop policy if exists reviewer_read on %I', t);
    execute format('create policy reviewer_read on %I for select to authenticated using (scout_is_reviewer())', t);
  end loop;
end $$;
drop policy if exists reviewer_insert on assignments;
create policy reviewer_insert on assignments for insert to authenticated
  with check (scout_is_reviewer() and actor = 'human' and actor_id = scout_reviewer_id());
drop policy if exists reviewer_insert on reviews;
create policy reviewer_insert on reviews for insert to authenticated
  with check (scout_is_reviewer() and reviewer_id = scout_reviewer_id());
drop policy if exists reviewer_insert on profiles;
create policy reviewer_insert on profiles for insert to authenticated with check (scout_is_reviewer());
drop policy if exists reviewer_update on profiles;
create policy reviewer_update on profiles for update to authenticated using (scout_is_reviewer()) with check (scout_is_reviewer());
drop policy if exists reviewer_insert on export_ledger;
create policy reviewer_insert on export_ledger for insert to authenticated with check (scout_is_reviewer());
drop policy if exists reviewer_delete on export_ledger;
create policy reviewer_delete on export_ledger for delete to authenticated using (scout_is_reviewer());

-- Pipeline role: reads profiles/reviews, writes sorter assignment rows (sort.py) and the one-time backfill.
grant select, insert, update on profiles, reviewers to scout_pipeline;
grant select, insert on assignments, reviews, export_ledger to scout_pipeline;
grant select on current_assignments, current_reviews, event_scores, score_distance, app_assignments, app_event_keys,
  app_reviews, app_exports, neighborhood_density to scout_pipeline;
do $$
declare t text;
begin
  foreach t in array array['profiles','reviewers','assignments','reviews','export_ledger'] loop
    execute format('drop policy if exists pipeline_read on %I', t);
    execute format('drop policy if exists pipeline_insert on %I', t);
    execute format('create policy pipeline_read   on %I for select to scout_pipeline using (true)', t);
    execute format('create policy pipeline_insert on %I for insert to scout_pipeline with check (true)', t);
  end loop;
  foreach t in array array['profiles','reviewers'] loop
    execute format('drop policy if exists pipeline_update on %I', t);
    execute format('create policy pipeline_update on %I for update to scout_pipeline using (true) with check (true)', t);
  end loop;
end $$;
