"""Agent tools that read live operational data (Support Agent Part 2).

lookup_ticket(TicketLookupInput) -> TicketLookupOutput
    Reads Nexova's Centralized Incident Manager. One responsibility: tickets. Read-only.

Transport: in-process, through the incident manager's own service layer
(services/api/app/incidents/service.py: get_incident_by_id / list_incidents), the same
functions behind GET /api/incidents and GET /api/incidents/{id}. The agent runs inside the
same FastAPI app, so this avoids an HTTP hop to itself. Those HTTP routes require a user JWT;
the service layer doesn't, so no credential is needed or stored here.

Read-only by construction: only the two read functions are ever looked up, and
tests/pipelines/test_agent_tools.py fails if this module references a write function.

Every call runs under an explicit timeout (TICKET_TOOL_TIMEOUT_S, default 4 seconds) and
never raises: failures come back as found=False with outcome "timeout" / "not_found" /
"error", which the graph routes to its fallback node.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

TICKET_TOOL_TIMEOUT_S = float(os.environ.get("TICKET_TOOL_TIMEOUT_S", "4"))
MAX_LISTED = 5

Outcome = Literal["success", "not_found", "timeout", "error"]
TicketStatus = Literal["open", "in_progress", "resolved", "discarded"]

# Same labels the incident manager UI shows (never raw enum values in an answer).
STATUS_LABELS = {"open": "Open", "in_progress": "In progress", "resolved": "Resolved", "discarded": "Discarded"}
CATEGORY_LABELS = {
    "technical_failure": "Technical failure", "process_error": "Process error",
    "client_complaint": "Client complaint", "candidate_issue": "Candidate issue",
    "staff_issue": "Staff issue", "sla_breach": "SLA breach", "data_quality": "Data quality",
    "other": "Other",
}
ORIGIN_LABELS = {"customer": "Customer", "branch": "Branch", "internal": "Internal"}
BRANCH_LABELS = {"central": "Central", "valencia_operations": "Valencia operations",
                 "miami_office": "Miami office", "remote": "Remote"}


class TicketLookupInput(BaseModel):
    """Exactly one of: a ticket id (detail lookup) or a status filter (list lookup)."""
    ticket_id: int | None = Field(None, ge=1)
    status: TicketStatus | None = None


class Ticket(BaseModel):
    ticket_id: int
    title: str
    status: TicketStatus
    category: str
    origin: str
    branch: str
    created_at: str
    updated_at: str


class TicketLookupOutput(BaseModel):
    found: bool
    outcome: Outcome
    query: TicketLookupInput
    tickets: list[Ticket] = []
    total_matching: int | None = None    # list lookups: how many tickets match the filter
    error: str | None = None             # short, safe description; never an exception dump
    duration_ms: float | None = None


# ----------------------------------------------------------------- incident manager access
def _incident_service():
    """The incident manager's service layer (services/api/app/incidents/service.py)."""
    api_root = Path(__file__).resolve().parents[1] / "api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))
    from app.incidents import service
    return service


class InProcessIncidentClient:
    """Read-only access to the incident manager. Only these two methods exist."""

    def get(self, ticket_id: int) -> dict | None:
        return _incident_service().get_incident_by_id(ticket_id)

    def list(self, status: str) -> list[dict]:
        from app.incidents.models import Status
        return _incident_service().list_incidents(status=Status(status))


_client = InProcessIncidentClient()
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ticket-tool")


def set_incident_client(client) -> None:
    """Swap the transport (tests use an in-memory stand-in with the same get/list methods)."""
    global _client
    _client = client


def _to_ticket(row: dict) -> Ticket:
    return Ticket(ticket_id=int(row["id"]), title=str(row["title"]), status=row["status"],
                  category=str(row["category"]), origin=str(row["origin"]), branch=str(row["branch"]),
                  created_at=str(row["created_at"]), updated_at=str(row["updated_at"]))


def _with_timeout(fn: Callable, *args):
    return _pool.submit(fn, *args).result(timeout=TICKET_TOOL_TIMEOUT_S)


def lookup_ticket(query: TicketLookupInput) -> TicketLookupOutput:
    """Look up one ticket by id, or the tickets with a given status. Never raises."""
    import time
    started = time.perf_counter()

    def done(**kw) -> TicketLookupOutput:
        return TicketLookupOutput(query=query, duration_ms=round((time.perf_counter() - started) * 1000, 1), **kw)

    try:
        if query.ticket_id is not None:
            row = _with_timeout(_client.get, query.ticket_id)
            if row is None:
                return done(found=False, outcome="not_found", error=f"ticket {query.ticket_id} does not exist")
            return done(found=True, outcome="success", tickets=[_to_ticket(row)])
        if query.status is not None:
            rows = _with_timeout(_client.list, query.status)
            if not rows:
                return done(found=False, outcome="not_found", total_matching=0,
                            error=f"no tickets with status {query.status}")
            return done(found=True, outcome="success", total_matching=len(rows),
                        tickets=[_to_ticket(r) for r in rows[:MAX_LISTED]])
        return done(found=False, outcome="error", error="no ticket id or status to look up")
    except FutureTimeout:
        return done(found=False, outcome="timeout",
                    error=f"incident manager did not answer within {TICKET_TOOL_TIMEOUT_S:g}s")
    except Exception as exc:  # DB unreadable, malformed row...
        return done(found=False, outcome="error", error=f"incident manager error ({type(exc).__name__})")
