create schema if not exists reporting;

create table if not exists reporting.weekly_office_program_performance (
  id uuid primary key default gen_random_uuid(),
  office text not null,
  programme_id text not null,
  week_start date not null,
  total_material_cost numeric not null default 0,
  kits_delivered_count integer not null default 0,
  shortage_events_count integer not null default 0,
  cost_variance_events_count integer not null default 0,
  currency text not null,
  computed_at timestamptz not null default now(),
  unique (office, programme_id, week_start)
);

create table if not exists reporting.pipeline_runs (
  run_id uuid primary key,
  trigger text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  window_from timestamptz not null,
  window_to timestamptz not null,
  rows_extracted integer,
  rows_rejected integer,
  rows_loaded integer,
  rows_updated integer,
  events_by_type jsonb,
  reconciliation jsonb,
  status text not null check (status in ('running','success','failed','skipped')),
  checkpoint text not null,
  error_summary text,
  pipeline_version text not null
);

-- Single-run guard: the database refuses a second 'running' row.
create unique index if not exists pipeline_runs_single_running
  on reporting.pipeline_runs ((true)) where status = 'running';
