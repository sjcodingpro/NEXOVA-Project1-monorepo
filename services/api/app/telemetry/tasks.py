"""Async version of the telemetry report (DEV-55).

build_report() runs five pandas pipelines over the same events table, which makes
it the slowest read in the API. The endpoint now enqueues this task and returns a
task_id; the worker does the heavy work.
"""
import logging
from datetime import datetime

from celery.exceptions import SoftTimeLimitExceeded
from fastapi.encoders import jsonable_encoder

from app.celery_app import MAX_ATTEMPTS, DeadLetterTask, celery_app
from app.telemetry.analysis import build_report

logger = logging.getLogger("celery.app.tasks")


@celery_app.task(
    bind=True,
    base=DeadLetterTask,
    name="telemetry.build_report",
    max_retries=MAX_ATTEMPTS - 1,
)
def build_report_task(self, start_iso: str, end_iso: str, simulate_failure: bool = False) -> dict:
    """Message carries only two ISO date strings; the worker loads the data itself."""
    attempt = self.request.retries + 1
    logger.info("telemetry report: task_id=%s attempt %d/%d", self.request.id, attempt, MAX_ATTEMPTS)
    try:
        if simulate_failure:
            raise RuntimeError("simulated failure (demo)")
        report = build_report(datetime.fromisoformat(start_iso), datetime.fromisoformat(end_iso))
        return jsonable_encoder(report)
    except SoftTimeLimitExceeded:
        raise  # a timeout is not retried: it goes straight to the DLQ
    except Exception as exc:
        logger.warning(
            "telemetry report: task_id=%s attempt %d/%d failed: %s",
            self.request.id, attempt, MAX_ATTEMPTS, exc,
        )
        # Waits 2s, then 4s. After the last attempt, retry() re-raises exc and on_failure runs.
        raise self.retry(exc=exc, countdown=2 ** attempt)
