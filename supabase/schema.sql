-- Eventrrr Scout tables. Paste into Supabase → SQL editor → Run. Safe to re-run.
-- Lives in the Eventrrr project; everything is prefixed scout_ and touches nothing else.

create table if not exists scout_reviewers (
  email text primary key,
  added_at timestamptz default now()
);
-- Who may use the scout. Add/remove rows to change access.
insert into scout_reviewers (email) values
  ('accounts@danielstringer.com'),
  ('daniel.stringer@gmail.com')
on conflict do nothing;

create table if not exists scout_runs (
  run text primary key,
  window_from date,
  window_to date,
  umbrella text,
  event_count int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists scout_events (
  run text references scout_runs(run) on delete cascade,
  key text,
  starts_at timestamptz,
  category text,
  highlight boolean default false,
  data jsonb not null,
  updated_at timestamptz default now(),
  primary key (run, key)
);
create index if not exists scout_events_run_starts on scout_events (run, starts_at);

create table if not exists scout_decisions (
  run text,
  key text,
  decision text check (decision in ('keep','skip') or decision is null),
  note text check (char_length(note) <= 140),
  exported_at timestamptz,
  updated_at timestamptz default now(),
  updated_by text,
  primary key (run, key)
);

-- Access: only allow-listed emails, via Google (or any) Supabase Auth login.
create or replace function scout_is_reviewer() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from scout_reviewers where email = lower(auth.jwt() ->> 'email'));
$$;

alter table scout_reviewers enable row level security;
alter table scout_runs      enable row level security;
alter table scout_events    enable row level security;
alter table scout_decisions enable row level security;

drop policy if exists scout_reviewers_read on scout_reviewers;
create policy scout_reviewers_read on scout_reviewers for select to authenticated using (scout_is_reviewer());

drop policy if exists scout_runs_read on scout_runs;
create policy scout_runs_read on scout_runs for select to authenticated using (scout_is_reviewer());

drop policy if exists scout_events_read on scout_events;
create policy scout_events_read on scout_events for select to authenticated using (scout_is_reviewer());

drop policy if exists scout_decisions_all on scout_decisions;
create policy scout_decisions_all on scout_decisions for all to authenticated
  using (scout_is_reviewer()) with check (scout_is_reviewer());

-- Writes to runs/events come only from the publish workflow (service role), never from the browser.
revoke all on scout_runs, scout_events, scout_reviewers from anon;
grant select on scout_runs, scout_events, scout_reviewers to authenticated;
grant select, insert, update, delete on scout_decisions to authenticated;
