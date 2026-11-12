-- Scout IQ, step 3: pipeline-side tables in DP's own Supabase project (tlwyhxvytmhpcgrismsz), the scoped
-- pipeline role, and the keepalive table. Review-side tables (profiles, assignments, reviews, reviewers, views)
-- come in step 4; calendars/exports in step 5.
--
-- Paste the whole file into the new project's SQL editor and run it once. Replace <PIPELINE_PASSWORD> first
-- (a long random string; it goes only into the SCOUT_IQ_DB_URL repo secret, never into the repo). Re-running
-- is safe: everything is IF NOT EXISTS / OR REPLACE, and the role line is skipped if the role exists.
--
-- Spec: Scout IQ: Database Spec v1 (claude.ai/artifact/C98BvUrDVz9DVYyvroeGxw).

set client_min_messages = warning;
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------------------------------------
-- Tables (all ids UUID; every table has created_at; (v) = version stamp required on each row)
-- ---------------------------------------------------------------------------------------------------------

create table if not exists cities (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  slug        text not null unique,
  country     text not null,
  timezone    text not null,
  currency    text not null,
  created_at  timestamptz not null default now()
);

create table if not exists sources (
  id             uuid primary key default gen_random_uuid(),
  city_id        uuid not null references cities(id),
  kind           text not null check (kind in ('website', 'instagram', 'newsletter', 'whatsapp', 'llm_scout', 'search')),
  handle_or_url  text not null,
  name           text,
  tier           smallint,
  enabled        boolean not null default true,
  added_by       text,
  last_run_at    timestamptz,
  yield_events   integer not null default 0,
  yield_dupes    integer not null default 0,
  created_at     timestamptz not null default now(),
  unique (kind, handle_or_url)
);

create table if not exists runs (
  id               uuid primary key default gen_random_uuid(),
  slug             text not null unique,            -- the repo's run name: runs/<slug>/
  city_id          uuid not null references cities(id),
  window_start     date,
  window_end       date,
  umbrella         text,
  source_ids       uuid[] not null default '{}',
  extractor_model  text not null,                   -- (v)
  dedupe_version   text not null,                   -- (v)
  sorter_model     text,                            -- (v) once sort.py writes
  cost_usd         numeric(8,3),
  status           text not null default 'done' check (status in ('running', 'done', 'failed')),
  started_at       timestamptz,
  finished_at      timestamptz,
  created_at       timestamptz not null default now()
);

create table if not exists venues (
  id               uuid primary key default gen_random_uuid(),
  city_id          uuid not null references cities(id),
  name             text not null,
  aliases          text[] not null default '{}',    -- venue strings as extracted that resolved here
  address          text,
  neighborhood     text,
  lat              double precision,
  lng              double precision,
  capacity_band    text,
  instagram        text,
  website          text,
  google_place_id  text unique,
  google_rating    numeric(2,1),
  google_reviews   integer,
  google_checked_at timestamptz,
  created_at       timestamptz not null default now()
);
create unique index if not exists venues_city_name_key on venues (city_id, lower(name)) where google_place_id is null;

create table if not exists organizers (
  id               uuid primary key default gen_random_uuid(),
  name             text not null,
  kind             text check (kind in ('venue', 'collective', 'individual', 'brand', 'institution')),
  instagram        text,
  website          text,
  credibility_note text,
  created_at       timestamptz not null default now()
);
create unique index if not exists organizers_name_key on organizers (lower(name));

create table if not exists events (
  id                uuid primary key default gen_random_uuid(),
  key               text not null unique,            -- stable slug from normalize.py; never changed by merges
  city_id           uuid not null references cities(id),
  title             text not null,
  description       text,
  starts_at         timestamptz not null,
  ends_at           timestamptz,
  all_day           boolean not null default false,
  timezone          text not null,
  venue_id          uuid references venues(id),
  venue_text        text,                            -- as extracted, until venue_id is resolved
  organizer_id      uuid references organizers(id),
  neighborhood      text,
  address           text,
  price_min         numeric(10,2),
  price_max         numeric(10,2),
  price_currency    text,
  price_text        text,
  is_free           boolean,
  signup_mechanism  text check (signup_mechanism in ('ticket_link', 'dm', 'transfer', 'walk_in', 'rsvp_link', 'unknown')),
  url               text,
  eventrrr_category text,
  is_ongoing        boolean not null default false,
  rubric_score      integer,                         -- score.py highlight rubric (not the 1–5)
  signals           jsonb not null default '{}',
  first_seen_run_id uuid not null references runs(id),
  last_seen_run_id  uuid not null references runs(id),
  status            text not null default 'live' check (status in ('live', 'cancelled', 'moved', 'past')),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create table if not exists observations (
  id               uuid primary key,                 -- deterministic (uuid5 of run|file|index), so re-writes upsert
  run_id           uuid not null references runs(id),
  source_id        uuid references sources(id),
  source_url       text,
  observed_at      timestamptz,
  raw_text_ref     text,                             -- Supabase Storage path (step 6); null until then
  raw_excerpt      text,                             -- 300 chars
  extraction       jsonb not null,                   -- the extractor's record, verbatim
  extractor_model  text not null,                    -- (v)
  created_at       timestamptz not null default now()
);

create table if not exists event_merges (
  id               uuid primary key default gen_random_uuid(),
  observation_id   uuid not null references observations(id),
  event_id         uuid not null references events(id),
  merged_by        text not null check (merged_by in ('model', 'human')),
  dedupe_version   text not null,                    -- (v)
  unmerged_at      timestamptz,
  created_at       timestamptz not null default now()
);
create unique index if not exists event_merges_live_key on event_merges (observation_id) where unmerged_at is null;

create table if not exists occurrences (
  id               uuid primary key default gen_random_uuid(),
  event_id         uuid not null references events(id),
  starts_at        timestamptz not null,
  ends_at          timestamptz,
  kind             text not null check (kind in ('opening', 'closing', 'run')),
  created_at       timestamptz not null default now(),
  unique (event_id, kind, starts_at)
);

create table if not exists outcomes (
  id          uuid primary key default gen_random_uuid(),
  event_id    uuid not null references events(id),
  observed_at timestamptz not null default now(),
  kind        text not null check (kind in ('sold_out', 'cancelled', 'moved', 'attendance', 'price_change')),
  value       text,
  source      text not null check (source in ('resweep', 'rsvp_layer', 'manual')),
  created_at  timestamptz not null default now()
);

-- Keepalive: the weekly Action inserts a row when nothing else has written in 5 days (free plan pauses at 7).
create table if not exists heartbeats (
  id          uuid primary key default gen_random_uuid(),
  note        text,
  created_at  timestamptz not null default now()
);

-- Indexes from the spec
create index if not exists events_city_starts_idx      on events (city_id, starts_at);
create index if not exists observations_run_idx       on observations (run_id);
create index if not exists event_merges_observation_idx on event_merges (observation_id);
create index if not exists venues_city_neighborhood_idx on venues (city_id, neighborhood);
create index if not exists occurrences_event_idx      on occurrences (event_id);

-- Seed: the one city until a second row exists
insert into cities (name, slug, country, timezone, currency)
values ('Mexico City', 'cdmx', 'MX', 'America/Mexico_City', 'MXN')
on conflict (slug) do nothing;

-- ---------------------------------------------------------------------------------------------------------
-- Pipeline role: GitHub Actions connects as scout_pipeline over the session pooler. Insert/update/select on
-- the tables above, no delete, no truncate, nothing in auth/storage. RLS stays on; the policies below are the
-- only ones until step 4 adds the app's reviewer policies.
-- ---------------------------------------------------------------------------------------------------------

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'scout_pipeline') then
    create role scout_pipeline login password '<PIPELINE_PASSWORD>' nosuperuser nocreatedb nocreaterole noinherit;
  end if;
end $$;

grant usage on schema public to scout_pipeline;
grant select, insert, update on cities, sources, runs, venues, organizers, events, observations, event_merges,
  occurrences, outcomes, heartbeats to scout_pipeline;
revoke delete, truncate on all tables in schema public from scout_pipeline;

alter table cities        enable row level security;
alter table sources       enable row level security;
alter table runs          enable row level security;
alter table venues        enable row level security;
alter table organizers    enable row level security;
alter table events        enable row level security;
alter table observations  enable row level security;
alter table event_merges  enable row level security;
alter table occurrences   enable row level security;
alter table outcomes      enable row level security;
alter table heartbeats    enable row level security;

do $$
declare t text;
begin
  foreach t in array array['cities','sources','runs','venues','organizers','events','observations','event_merges','occurrences','outcomes','heartbeats'] loop
    execute format('drop policy if exists pipeline_read on %I', t);
    execute format('drop policy if exists pipeline_insert on %I', t);
    execute format('drop policy if exists pipeline_update on %I', t);
    execute format('create policy pipeline_read   on %I for select to scout_pipeline using (true)', t);
    execute format('create policy pipeline_insert on %I for insert to scout_pipeline with check (true)', t);
    execute format('create policy pipeline_update on %I for update to scout_pipeline using (true) with check (true)', t);
  end loop;
end $$;

-- Analysis views (read by the app in step 4; harmless now)
create or replace view neighborhood_density as
select e.city_id, e.neighborhood, date_trunc('week', e.starts_at)::date as week, e.eventrrr_category, count(*) as events
from events e
group by 1, 2, 3, 4;

-- A misread superseded by a later read of the same page and title under a new date (set by iq_write.py). Readers skip it.
alter table events add column if not exists superseded_by uuid references events(id);
create index if not exists events_superseded_idx on events (superseded_by) where superseded_by is not null;
