import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.telemetry.analysis import build_report
from app.telemetry.models import TelemetryEvent
from app.telemetry.repository import bulk_insert_telemetry
from app.telemetry.tasks import build_report_task

# "uvicorn.error" so these lines show in the dev server console.
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

MAX_BATCH = 500
SERVICE = "backoffice"  # every event is emitted by the backoffice frontend

LEVEL_BY_EVENT = {
    "frontend_error_raised": "error",
    "api_request_failed": "error",
    "validation_error_raised": "warn",
    "login_failed": "warn",
    "direct_stock_edit_rejected": "warn",
    "stock_threshold_triggered": "warn",
    "kit_cost_variance_detected": "warn",
}

# One numeric property promoted to the `value` column, where there is an obvious one.
VALUE_FIELD_BY_EVENT = {
    "api_latency_recorded": "duration_ms",
    "kit_cost_variance_detected": "variance_pct",
    "stock_threshold_triggered": "current_stock",
    "inbound_order_created": "quantity",
    "outbound_order_created": "quantity",
}


def _numeric(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def map_event_to_row(event: TelemetryEvent) -> dict[str, Any]:
    value_field = VALUE_FIELD_BY_EVENT.get(event.event_type)
    return {
        "timestamp": event.timestamp,
        "service": SERVICE,
        "event_type": event.event_type,
        "level": LEVEL_BY_EVENT.get(event.event_type, "info"),
        "value": _numeric(event.properties.get(value_field)) if value_field else None,
        "message": None,
        "tags": event.properties,  # allowlisted properties, as sent
    }


@router.post("/events")
def receive_events(payload: dict[str, Any] = Body(...)):
    """Validate each event on its own, then store all valid ones in one bulk insert.

    The body is parsed loosely on purpose: typing it as list[TelemetryEvent]
    would return 422 for the whole batch if a single event were invalid.
    """
    events = payload.get("events")
    if not isinstance(events, list) or len(events) > MAX_BATCH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Body must be {{"events": [...]}} with at most {MAX_BATCH} events.',
        )

    rows: list[dict[str, Any]] = []
    rejected = 0
    for raw in events:
        try:
            rows.append(map_event_to_row(TelemetryEvent.model_validate(raw)))
        except ValidationError:
            rejected += 1

    try:
        stored = bulk_insert_telemetry(rows)
    except SQLAlchemyError:
        logger.exception("telemetry: bulk insert failed")
        # 503 lets the frontend's retry-with-backoff try again.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry storage unavailable.",
        )

    logger.info("telemetry: received %d, stored %d, rejected %d", len(events), stored, rejected)
    return {"received": len(events), "stored": stored, "rejected": rejected}


CACHE_TTL_SECONDS = 60
_REPORT_CACHE: dict[tuple, tuple[float, dict[str, Any]]] = {}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/report")
def get_report(start_date: datetime | None = None, end_date: datetime | None = None):
    """Technical report: operational metrics computed from stored events.

    The default period (last 7 days, UTC) is resolved here, once, and passed
    to every metric function. The pipeline does not run on every request:
    results are cached for 60 seconds per requested (start_date, end_date).
    """
    start_requested = _as_utc(start_date) if start_date else None
    end_requested = _as_utc(end_date) if end_date else None
    # Keyed on what was REQUESTED (None = default), so default requests can hit the cache.
    cache_key = (start_requested, end_requested)

    cached = _REPORT_CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        logger.info("telemetry report: cache hit")
        return cached[1]

    end = end_requested or datetime.now(timezone.utc)
    start = start_requested or end - timedelta(days=7)
    if start >= end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date.",
        )

    try:
        report = build_report(start, end)
    except SQLAlchemyError:
        logger.exception("telemetry report: query failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry storage unavailable.",
        )

    if len(_REPORT_CACHE) >= 100:
        _REPORT_CACHE.clear()
    _REPORT_CACHE[cache_key] = (time.monotonic(), report)
    logger.info("telemetry report: computed (cache miss)")
    return report


class ReportTaskRequest(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    # Demo only: forces the task to fail so the retries and the DLQ can be shown in Flower.
    # Ignored unless ALLOW_TASK_FAILURE_DEMO=1 is set on the API.
    simulate_failure: bool = False


@router.post("/report", status_code=status.HTTP_202_ACCEPTED)
def enqueue_report(body: ReportTaskRequest | None = Body(default=None)):
    """Async version of GET /telemetry/report (DEV-55).

    Returns 202 and a task_id right away; a Celery worker builds the report.
    Poll GET /tasks/{task_id} for the status and the result.
    """
    body = body or ReportTaskRequest()
    end = _as_utc(body.end_date) if body.end_date else datetime.now(timezone.utc)
    start = _as_utc(body.start_date) if body.start_date else end - timedelta(days=7)
    if start >= end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date.",
        )
    if body.simulate_failure and os.environ.get("ALLOW_TASK_FAILURE_DEMO") != "1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Failure simulation is disabled. Set ALLOW_TASK_FAILURE_DEMO=1 to use it.",
        )

    try:
        task = build_report_task.delay(start.isoformat(), end.isoformat(), body.simulate_failure)
    except Exception:
        logger.exception("telemetry report: could not enqueue task")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task broker unavailable.",
        )
    logger.info("telemetry report: enqueued task_id=%s", task.id)
    return {"task_id": task.id, "status": "pending", "status_url": f"/tasks/{task.id}"}
