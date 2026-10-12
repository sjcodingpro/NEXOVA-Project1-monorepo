"""weekly_office_performance_flow -- Nexova business performance pipeline.

Run command (from the repo root):
    cd services/api && uv run python ../../data/pipelines/pipeline.py
Schedule: every Monday 05:00 UTC (cron "0 5 * * 1"), see PIPELINE_DESIGN.md.
"""
import os
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))                      # pipeline_db
sys.path.insert(0, str(ROOT / "data" / "process"))  # weekly_office_performance

import pipeline_db as db  # noqa: E402
from prefect import flow, get_run_logger, task  # noqa: E402
from weekly_office_performance import transform_weekly_kpis as _transform  # noqa: E402

# Programmes are derived from the data (the design's config block is not used in v1).
KNOWN_PROGRAMMES: tuple = ()


# --- Tasks -------------------------------------------------------------------

# Touches the database: 2 retries x 5 s absorbs a dropped connection, and
# anything longer than that is a real outage worth failing on.
@task(name="start_pipeline_run", retries=2, retry_delay_seconds=5)
def start_pipeline_run(run_id, trigger, window_from, window_to):
    """Insert the 'running' row and apply the single-run guard."""
    return db.begin_run(run_id, trigger, window_from, window_to)


# Reads Supabase: 3 retries x 30 s covers a pooler restart or brief network
# blip (~90 s) without paging anyone; the read is safe to repeat.
@task(name="extract_telemetry_events", retries=3, retry_delay_seconds=30)
def extract_telemetry_events(window_from, window_to):
    return db.read_telemetry_events(window_from, window_to)


def _transform_cache_key(context, parameters):
    # Cache key = the processed window plus the number of extracted rows, so a
    # re-run over the same data reuses the result, while a late event (a new
    # row count) produces a new key and is recomputed.
    return f"{parameters['window_from']}|{parameters['window_to']}|{len(parameters['raw'])}"


# Caching: the result is valid for 1 hour (ticket: skip repeats within the hour).
@task(name="transform_weekly_kpis", cache_key_fn=_transform_cache_key,
      cache_expiration=timedelta(hours=1))
def transform_weekly_kpis(raw, window_from, window_to):
    return _transform(raw, window_from, window_to, KNOWN_PROGRAMMES)


# Writes Supabase: 2 retries x 10 s. Safe because the load is an idempotent
# single-transaction upsert, so a retry cannot create duplicates.
@task(name="load_weekly_office_program_performance", retries=2, retry_delay_seconds=10)
def load_weekly_office_program_performance(result):
    records = result.to_dict("records")
    inserted, updated = db.upsert_weekly(records)
    return {"rows_loaded": len(records), "rows_inserted": inserted, "rows_updated": updated}


@task(name="export_eval_snapshot_optional")
def export_eval_snapshot_optional(result, run_id):
    """Optional step: save the aggregated rows to data/eval/. Never blocks the run."""
    if os.environ.get("FORCE_OPTIONAL_TASK_FAILURE"):
        raise RuntimeError("simulated failure of the optional snapshot task")
    out = ROOT / "data" / "eval" / "weekly_office_performance_last_run.csv"
    result.to_csv(out, index=False)
    return str(out)


@task(name="finish_pipeline_run", retries=2, retry_delay_seconds=5)
def finish_pipeline_run(run_id, status, checkpoint, stats, error_summary=None):
    db.finish_run(run_id, status, checkpoint, stats, error_summary)


# --- Subflows ----------------------------------------------------------------
# One independent flow per phase, with explicit inputs and outputs (no globals).

@flow(name="extract_telemetry_events_subflow")
def extract_telemetry_events_subflow(window_from, window_to):
    """Extraction phase: the four mandatory telemetry events in the window."""
    return extract_telemetry_events(window_from, window_to)


@flow(name="transform_weekly_kpis_subflow")
def transform_weekly_kpis_subflow(raw, window_from, window_to):
    """Transformation phase: Material Cost per Office/Programme, Kits Delivered,
    Shortage Frequency and Cost Variance Frequency per office, programme and week."""
    return transform_weekly_kpis(raw, window_from, window_to)


@flow(name="load_weekly_office_program_performance_subflow")
def load_weekly_office_program_performance_subflow(result):
    """Load phase: idempotent upsert into reporting.weekly_office_program_performance."""
    return load_weekly_office_program_performance(result)


@flow(name="export_eval_snapshot_subflow")
def export_eval_snapshot_subflow(result, run_id):
    """Optional phase: snapshot of the aggregated rows for data/eval/."""
    return export_eval_snapshot_optional(result, run_id)


# --- Main flow -----------------------------------------------------------------

@flow(name="weekly_office_performance_flow")
def weekly_office_performance_flow(weeks_back: int = 3, trigger: str = "schedule",
                                   run_id: str | None = None):
    """Coordinates the subflows; the ETL logic lives in the tasks and subflows above."""
    logger = get_run_logger()
    weeks_back = max(1, min(int(weeks_back), 12))
    run_id = run_id or str(uuid.uuid4())
    this_monday = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    this_monday -= timedelta(days=this_monday.weekday())
    window_from = this_monday - timedelta(weeks=weeks_back - 1)
    window_to = this_monday + timedelta(weeks=1)

    run = start_pipeline_run(run_id, trigger, window_from, window_to)
    if run["status"] == "skipped":
        logger.warning("Skipped: another run is already in progress (%s)", run.get("running_run_id"))
        return run

    checkpoint, stats = "started", {}
    try:
        raw = extract_telemetry_events_subflow(window_from, window_to)
        checkpoint = "extracted"
        db.set_checkpoint(run_id, checkpoint)

        result, transform_stats = transform_weekly_kpis_subflow(raw, window_from, window_to)
        stats.update(transform_stats)
        checkpoint = "transformed"
        db.set_checkpoint(run_id, checkpoint)

        stats.update(load_weekly_office_program_performance_subflow(result))
        checkpoint = "loaded"

        # Optional subflow: return_state=True, so its failure is handled here
        # instead of propagating and stopping the run.
        snapshot = export_eval_snapshot_subflow(result, run_id, return_state=True)
        if snapshot.is_failed():
            logger.warning("Eval snapshot skipped (non-critical): the main run continues")

        finish_pipeline_run(run_id, "success", checkpoint, stats)
    except Exception as exc:
        finish_pipeline_run(run_id, "failed", checkpoint, stats, f"{type(exc).__name__}: {exc}"[:500])
        raise
    logger.info("Run %s finished: %s", run_id, stats)
    return {"run_id": run_id, "status": "success", **stats}


# --- Manual trigger (imported by services/api/app/reporting) -----------------

def _run_in_background(weeks_back, run_id):
    try:
        weekly_office_performance_flow(weeks_back=weeks_back, trigger="manual", run_id=run_id)
    except Exception:
        pass  # already recorded as 'failed' in reporting.pipeline_runs


def trigger_pipeline_run(weeks_back: int = 3):
    """Start a manual run without blocking the caller (no ETL logic lives in services/)."""
    running = db.get_running_run_id()
    if running:
        return {"status": "conflict", "running_run_id": running}
    run_id = str(uuid.uuid4())
    threading.Thread(target=_run_in_background, args=(weeks_back, run_id), daemon=True).start()
    return {"status": "accepted", "run_id": run_id}


get_latest_pipeline_run = db.get_latest_pipeline_run
get_weekly_office_program_performance = db.get_weekly_office_program_performance


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run weekly_office_performance_flow")
    parser.add_argument("--weeks-back", type=int, default=3)
    parser.add_argument("--trigger", choices=["schedule", "manual"], default="schedule")
    args = parser.parse_args()
    weekly_office_performance_flow(weeks_back=args.weeks_back, trigger=args.trigger)
