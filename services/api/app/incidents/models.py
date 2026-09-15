"""
Pydantic models for the incident-manager domain (CONTEXT.md — Centralized
Incident Manager). Distinct from the raw CSV categories/statuses in
logic.py (TECHNICAL/BILLING/... and OPEN/CLOSED/DISCARDED) -- those are the
incidents-file-analyzer's *raw export* values; the enums below are this
manager's own model, which the seed script maps the raw CSV values into.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Branch(str, Enum):
    CENTRAL = "central"
    VALENCIA_OPERATIONS = "valencia_operations"
    MIAMI_OFFICE = "miami_office"
    REMOTE = "remote"


class Category(str, Enum):
    TECHNICAL_FAILURE = "technical_failure"
    PROCESS_ERROR = "process_error"
    CLIENT_COMPLAINT = "client_complaint"
    CANDIDATE_ISSUE = "candidate_issue"
    STAFF_ISSUE = "staff_issue"
    SLA_BREACH = "sla_breach"
    DATA_QUALITY = "data_quality"
    OTHER = "other"


class Status(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISCARDED = "discarded"


class Origin(str, Enum):
    CUSTOMER = "customer"
    BRANCH = "branch"
    INTERNAL = "internal"


# Valid forward transitions per CONTEXT.md. resolved/discarded are final.
VALID_STATUS_TRANSITIONS: dict[Status, set[Status]] = {
    Status.OPEN: {Status.IN_PROGRESS, Status.DISCARDED},
    Status.IN_PROGRESS: {Status.RESOLVED, Status.DISCARDED},
    Status.RESOLVED: set(),
    Status.DISCARDED: set(),
}


def is_valid_transition(current: Status, target: Status) -> bool:
    return target in VALID_STATUS_TRANSITIONS.get(current, set())


class IncidentCreate(BaseModel):
    """POST /api/incidents payload. status always starts at 'open' for
    incidents registered through the form -- only the seed script (which
    bypasses this model) can set resolved/discarded directly from
    historical data."""

    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    category: Category
    origin: Origin
    branch: Branch


class IncidentStatusUpdate(BaseModel):
    status: Status


class IncidentOut(BaseModel):
    id: int
    title: str
    description: str
    category: Category
    status: Status
    origin: Origin
    branch: Branch
    created_at: datetime
    updated_at: datetime
