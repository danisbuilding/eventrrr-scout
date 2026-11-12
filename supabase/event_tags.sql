-- Tags and embeddings for Eventrrr Search, written by scout/enrich.py (GitHub Actions, as scout_pipeline).
-- Vocabularies (venue_type, activity) must match scout/enrich.py and eventrrr-search lib/parse.js.
create extension if not exists vector with schema extensions;

create table if not exists event_tags (
  event_id     uuid primary key references events(id) on delete cascade,
  kid_friendly boolean,
  outdoor      boolean,
  venue_type   text,
  activity     text,
  summary_en   text,
  embedding    extensions.vector(512),
  source_hash  text not null,
  model        text,
  updated_at   timestamptz not null default now()
);
alter table event_tags enable row level security;
grant select, insert, update on event_tags to scout_pipeline;
drop policy if exists pipeline_read   on event_tags;
drop policy if exists pipeline_insert on event_tags;
drop policy if exists pipeline_update on event_tags;
create policy pipeline_read   on event_tags for select to scout_pipeline using (true);
create policy pipeline_insert on event_tags for insert to scout_pipeline with check (true);
create policy pipeline_update on event_tags for update to scout_pipeline using (true) with check (true);

-- in_metro: true = in the city or its metro area; false = another city (Search hides it); null = unclear
alter table event_tags add column if not exists in_metro boolean;

-- English versions for Search (proper names kept; originals stay in events)
alter table event_tags add column if not exists title_en text;
alter table event_tags add column if not exists description_en text;
alter table event_tags add column if not exists price_en text;
