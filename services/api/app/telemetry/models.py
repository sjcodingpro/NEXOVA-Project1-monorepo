from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    """Standard envelope from docs/telemetry/telemetry-plan.md (schema 1.0.0).

    Reused as-is by the real persistence endpoint in the next phase.
    userId is nullable: system-emitted events have no human actor.
    """

    eventId: UUID
    timestamp: datetime
    sessionId: str
    userId: Optional[str] = None
    event_type: str = Field(pattern=r"^[a-z]+(_[a-z]+)*_[a-z]+$")
    schemaVersion: str
    requestId: str
    properties: dict[str, Any]


class TelemetryBatch(BaseModel):
    events: list[TelemetryEvent] = Field(max_length=500)
