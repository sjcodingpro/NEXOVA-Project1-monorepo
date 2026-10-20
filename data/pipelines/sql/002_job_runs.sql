-- Nightly orchestration log (DEV-53). Separate from reporting.pipeline_runs (ETL).
CREATE TABLE IF NOT EXISTS public.job_runs (
  id            SERIAL PRIMARY KEY,
  job_name      VARCHAR(64) NOT NULL,
  target_date   DATE NOT NULL,
  status        VARCHAR(16) NOT NULL
                CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  started_at    TIMESTAMPTZ,
  finished_at   TIMESTAMPTZ,
  error_message TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_runs_name_date
  ON public.job_runs (job_name, target_date);
CREATE INDEX IF NOT EXISTS idx_job_runs_name_status
  ON public.job_runs (job_name, status);

-- The 'processing' status is the lock; this index makes it atomic
-- (only one processing row per job can exist, even for simultaneous starts).
CREATE UNIQUE INDEX IF NOT EXISTS job_runs_single_processing
  ON public.job_runs (job_name) WHERE status = 'processing';
