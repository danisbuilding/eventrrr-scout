-- Scout profiles (simulated curators) + per-event assignments. Paste into Bolt / SQL editor. Safe to re-run.
create table if not exists scout_profiles (
  slug text primary key check (slug ~ '^[a-z0-9-]{2,30}$'),
  name text not null,
  persona text,
  handle text,            -- Eventrrr @handle of the account this profile exports to
  active boolean default true,
  sort_order int default 100,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
insert into scout_profiles (slug, name, persona, sort_order) values
  ('foodie',    'Food & Drink',     'Cares who is cooking and where the mezcal comes from. Supper clubs, pop-ups, tastings, markets with real producers. A generic restaurant promo or a chain''s "taco night" does not make the cut.', 10),
  ('cultural',  'Arts & Culture',   'Openings, not just exhibitions; knows the museum calendar; the small gallery in Roma over the blockbuster. A talk if the speaker is worth it. Skips tourist packages and generic "cultural" listings.', 20),
  ('nightlife', 'Nightlife & Bars', 'Out after 11. Clubs, afters, themed parties, the occasional rooftop; decides by lineup and crowd. A bar with no event is not an event.', 30),
  ('music',     'Live Music',       'Small and mid-size venues, acts with a sound, the Foro Indie Rocks / Casa del Lago circuit; a free concert in a park over an arena show. Skips cover bands and hotel lobby sets.', 40),
  ('active',    'Sports & Movement','Runs, rides, hikes, the Sunday Reforma paseo, pickup games, yoga in a park; a match worth watching with friends. Skips wellness retreats and anything indoors-and-still.', 50)
on conflict (slug) do nothing;

create table if not exists scout_assignments (
  run text not null,
  key text not null,
  profile text not null,     -- a scout_profiles.slug, or 'none' = reviewed, fits no profile
  note text check (char_length(note) <= 140),
  source text default 'manual' check (source in ('manual','suggested','confirmed')),
  reason text,               -- first-pass sorter's one-line reason (suggested rows)
  updated_by text,
  updated_at timestamptz default now(),
  primary key (run, key, profile)
);
create index if not exists scout_assignments_profile on scout_assignments (profile, run);

alter table scout_profiles enable row level security;
alter table scout_assignments enable row level security;
drop policy if exists scout_profiles_all on scout_profiles;
create policy scout_profiles_all on scout_profiles for all to authenticated using (scout_is_reviewer()) with check (scout_is_reviewer());
drop policy if exists scout_assignments_all on scout_assignments;
create policy scout_assignments_all on scout_assignments for all to authenticated using (scout_is_reviewer()) with check (scout_is_reviewer());
grant select, insert, update, delete on scout_profiles, scout_assignments to authenticated;
