import logging

from fastapi import APIRouter

from app.telemetry.config import TELEMETRY_ENDPOINT
from app.telemetry.models import TelemetryBatch

# "uvicorn.error" so these lines show in the dev server console.
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/events")
async def receive_events(batch: TelemetryBatch):
    """STUB: validates the envelope, logs, returns 200. No persistence yet."""
    logger.info(
        "telemetry: received %d events (configured endpoint: %s)",
        len(batch.events),
        TELEMETRY_ENDPOINT,
    )
    for event in batch.events:
        logger.info("telemetry:   event_type=%s", event.event_type)
    return {"received": len(batch.events)}
