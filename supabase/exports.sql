-- Scout v3: calendars (profiles) with a kind + end date, and an export ledger. Safe to re-run.
alter table scout_profiles add column if not exists kind text default 'ongoing' check (kind in ('ongoing','oneoff'));
alter table scout_profiles add column if not exists ends_on date;

create table if not exists scout_exports (
  profile text not null,        -- scout_profiles.slug (the calendar)
  run text not null,
  key text not null,
  batch text not null,          -- ISO timestamp of the export click; "Undo last export" deletes a batch
  exported_by text,
  exported_at timestamptz default now(),
  primary key (profile, run, key)
);
create index if not exists scout_exports_batch on scout_exports (profile, batch);

alter table scout_exports enable row level security;
drop policy if exists scout_exports_all on scout_exports;
create policy scout_exports_all on scout_exports for all to authenticated using (scout_is_reviewer()) with check (scout_is_reviewer());
grant select, insert, update, delete on scout_exports to authenticated;
