#!/usr/bin/env python3
"""Nightly telemetry export job (DEV-53).

Independent process: no FastAPI imports. Exports yesterday's telemetry_events
(UTC) to data/raw/ as a backup CSV, then runs the data pipeline as a subprocess.
Every run is recorded in job_runs (pending -> processing -> completed | failed).
The 'processing' status is the lock; completed for (job, target_date) = idempotency.
"""
import csv
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from services import job_runner as jobs  # noqa: E402

JOB_NAME = "nightly_export"
RAW_DIR = ROOT / "data" / "raw"
PIPELINE = ROOT / "data" / "pipelines" / "pipeline.py"
COLUMNS = ["id", "timestamp", "service", "event_type", "level", "value", "message", "tags"]

log = logging.getLogger(JOB_NAME)


def setup_logging() -> None:
    fmt = logging.Formatter(f"%(asctime)s %(levelname)s {JOB_NAME} %(message)s",
                            "%Y-%m-%dT%H:%M:%SZ")
    fmt.converter = time.gmtime   # timestamps in UTC
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def resolve_target_date() -> date:
    """TARGET_DATE (YYYY-MM-DD) if set, else yesterday in UTC."""
    raw = os.environ.get("TARGET_DATE")
    if raw:
        return date.fromisoformat(raw)
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def export_csv(target_date: date) -> None:
    """Backup snapshot of telemetry_events for target_date (UTC). Skipped if file exists."""
    path = RAW_DIR / f"telemetry_{target_date.isoformat()}.csv"
    if path.exists():
        log.info("status=processing step=export_skipped reason=file_exists target_date=%s",
                 target_date)
        return
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")   # written fully, then renamed
    count = 0
    with jobs.get_engine().connect() as conn, tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        rows = conn.execute(
            text("SELECT id, timestamp, service, event_type, level, value, message, tags "
                 "FROM telemetry_events WHERE timestamp >= :s AND timestamp < :e "
                 "ORDER BY timestamp, id"),
            {"s": start, "e": end},
        )
        for r in rows:
            writer.writerow([r.id, r.timestamp.isoformat(), r.service, r.event_type,
                             r.level, r.value, r.message, json.dumps(r.tags)])
            count += 1
    tmp.replace(path)
    log.info("status=processing step=exported rows=%s file=%s target_date=%s",
             count, path.name, target_date)


def run_pipeline() -> None:
    """Run the Milestone 6 pipeline CLI as a subprocess (it reads telemetry_events from the DB)."""
    if os.environ.get("NIGHTLY_FORCE_FAILURE"):   # test hook to demonstrate the failed path
        raise RuntimeError("forced failure (NIGHTLY_FORCE_FAILURE is set)")
    result = subprocess.run(
        [sys.executable, str(PIPELINE), "--trigger", "schedule"],
        cwd=ROOT / "services" / "api", capture_output=True, text=True,
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip()[-300:]
        raise RuntimeError(f"pipeline exit code {result.returncode}: {tail}")


def main() -> int:
    setup_logging()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))   # lets `finally` release the lock
    try:
        target_date = resolve_target_date()
    except ValueError as exc:
        log.error('status=failed error="invalid TARGET_DATE: %s"', exc)
        return 2

    if jobs.has_processing_lock(JOB_NAME):
        log.info("status=cancelled reason=processing_lock target_date=%s", target_date)
        return 0
    if jobs.has_completed_for_date(JOB_NAME, target_date):
        log.info("status=skipped reason=duplicate target_date=%s", target_date)
        return 0

    run_id = jobs.create_run(JOB_NAME, target_date)
    if not jobs.mark_processing(run_id):   # lost a simultaneous start
        jobs.discard_run(run_id)
        log.info("status=cancelled reason=processing_lock target_date=%s", target_date)
        return 0
    log.info("status=started run_id=%s target_date=%s", run_id, target_date)

    outcome = None
    try:
        export_csv(target_date)
        run_pipeline()
        jobs.mark_completed(run_id)
        outcome = "completed"
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        jobs.mark_failed(run_id, message)
        outcome = "failed"
        log.error('status=failed run_id=%s target_date=%s error="%s"',
                  run_id, target_date, message.replace("\n", " ")[:300])
        return 1
    finally:
        if outcome is None:   # Ctrl+C / SIGTERM: never leave a zombie 'processing' row
            jobs.mark_failed(run_id, "interrupted before completion")
    log.info("status=completed run_id=%s target_date=%s", run_id, target_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
