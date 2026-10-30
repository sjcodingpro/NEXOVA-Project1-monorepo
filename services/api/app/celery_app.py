"""Celery application (DEV-55): Redis is both the broker and the result backend.

The API only *enqueues* tasks (producer). A separate worker process runs them
(consumer):  celery -A app.celery_app worker -Q default,dlq --loglevel=info

Task messages stay small on purpose: ids and ISO date strings only, never data.
"""
import json
import logging
import os
from datetime import datetime, timezone

import redis
from celery import Celery, Task

logger = logging.getLogger("celery.app.tasks")

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

MAX_ATTEMPTS = 3                  # 1 first run + 2 retries, then the task is dead-lettered
DLQ_QUEUE = "dlq"                 # Celery queue: every dead-lettered task shows up in Flower
DLQ_RECORDS_KEY = "dlq:records"   # Redis list: one JSON record per dead-lettered task

celery_app = Celery(
    "nexova",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["app.telemetry.tasks"],
)

celery_app.conf.update(
    task_default_queue="default",
    task_routes={"dlq.record_failure": {"queue": DLQ_QUEUE}},
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,            # exposes the 'started' status
    task_acks_late=True,                # ACK only after the task finishes successfully
    task_reject_on_worker_lost=True,    # worker dies mid-task -> message goes back to the queue
    worker_prefetch_multiplier=1,       # one message at a time per worker process
    task_soft_time_limit=60,            # every task has a timeout: soft limit raises inside the task...
    task_time_limit=90,                 # ...hard limit kills it
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)


class DeadLetterTask(Task):
    """Base class: when a task has failed for good (retries used up), record it in the DLQ."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        record = {
            "task_id": task_id,
            "task_name": self.name,
            "attempt": self.request.retries + 1,
            "max_attempts": MAX_ATTEMPTS,
            "error": f"{type(exc).__name__}: {exc}",
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.error("DLQ: task %s failed on attempt %s: %s", task_id, record["attempt"], record["error"])
        try:
            redis.Redis.from_url(BROKER_URL).rpush(DLQ_RECORDS_KEY, json.dumps(record))
        except Exception:
            logger.exception("DLQ: could not store the record in Redis")
        # Also publish it to the 'dlq' queue so it appears in Flower.
        record_failure.apply_async(args=[record], queue=DLQ_QUEUE)


@celery_app.task(name="dlq.record_failure")
def record_failure(record: dict) -> dict:
    """Consumes the 'dlq' queue. Logs the dead-lettered task and keeps it visible in Flower."""
    logger.error("DLQ record: %s", record)
    return record


def read_dlq_records(limit: int = 50) -> list[dict]:
    """Newest-last list of DLQ records stored in Redis."""
    raw = redis.Redis.from_url(BROKER_URL).lrange(DLQ_RECORDS_KEY, -limit, -1)
    return [json.loads(item) for item in raw]
