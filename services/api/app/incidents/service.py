"""
Service layer for the Centralized Incident Manager -- pure functions
against TinyDB, no FastAPI/HTTP concerns here. Mirrors
app/users/service.py's shape.
"""

from datetime import datetime, timezone
from typing import Optional

from tinydb import Query

from app.database import db_lock, get_incidents_table
from app.incidents.models import (
    Branch,
    Category,
    IncidentCreate,
    InvalidTransitionError,
    Origin,
    Status,
    is_valid_transition,
)


def _row_to_incident(doc) -> dict:
    """dict(doc) may carry extra keys not on IncidentOut (e.g. the seed
    script's seed_ticket_id, used only for dedup) -- IncidentOut ignores
    unknown extra fields by default, so this is safe to pass straight
    into IncidentOut(**data) at the router layer."""
    data = dict(doc)
    data["id"] = doc.doc_id
    return data


def create_incident(payload: IncidentCreate) -> dict:
    table = get_incidents_table()
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "title": payload.title,
        "description": payload.description,
        "category": payload.category.value,
        "status": Status.OPEN.value,
        "origin": payload.origin.value,
        "branch": payload.branch.value,
        "created_at": now,
        "updated_at": now,
    }
    with db_lock:
        doc_id = table.insert(record)
        return _row_to_incident(table.get(doc_id=doc_id))


def get_incident_by_id(incident_id: int) -> Optional[dict]:
    table = get_incidents_table()
    doc = table.get(doc_id=incident_id)
    if doc is None:
        return None
    return _row_to_incident(doc)


def list_incidents(
    status: Optional[Status] = None,
    origin: Optional[Origin] = None,
    branch: Optional[Branch] = None,
    category: Optional[Category] = None,
) -> list[dict]:
    table = get_incidents_table()
    incidents = [_row_to_incident(doc) for doc in table.all()]

    if status is not None:
        incidents = [i for i in incidents if i.get("status") == status.value]
    if origin is not None:
        incidents = [i for i in incidents if i.get("origin") == origin.value]
    if branch is not None:
        incidents = [i for i in incidents if i.get("branch") == branch.value]
    if category is not None:
        incidents = [i for i in incidents if i.get("category") == category.value]

    incidents.sort(key=lambda i: i.get("created_at", ""), reverse=True)
    return incidents


def update_incident_status(incident_id: int, new_status: Status) -> Optional[dict]:
    """Returns the updated incident, or None if it doesn't exist. Raises
    ValueError if the transition isn't allowed -- the router translates
    that into a 400."""
    table = get_incidents_table()
    existing = table.get(doc_id=incident_id)
    if existing is None:
        return None

    current_status = Status(existing["status"])
    if not is_valid_transition(current_status, new_status):
        raise InvalidTransitionError(current_status.value, new_status.value)

    with db_lock:
        table.update(
            {"status": new_status.value, "updated_at": datetime.now(timezone.utc).isoformat()},
            doc_ids=[incident_id],
        )
        return _row_to_incident(table.get(doc_id=incident_id))


def get_summary() -> dict:
    table = get_incidents_table()
    incidents = table.all()

    by_status = {s.value: 0 for s in Status}
    by_category = {c.value: 0 for c in Category}
    by_origin = {o.value: 0 for o in Origin}
    by_branch = {b.value: 0 for b in Branch}

    for doc in incidents:
        if doc.get("status") in by_status:
            by_status[doc["status"]] += 1
        if doc.get("category") in by_category:
            by_category[doc["category"]] += 1
        if doc.get("origin") in by_origin:
            by_origin[doc["origin"]] += 1
        if doc.get("branch") in by_branch:
            by_branch[doc["branch"]] += 1

    return {
        "by_status": by_status,
        "by_category": by_category,
        "by_origin": by_origin,
        "by_branch": by_branch,
    }


# --- Seed-specific helpers --------------------------------------------------
# Used only by scripts/seed_incidents.py. Kept here (rather than duplicated
# in the script) so the TinyDB access pattern -- and the dedup key name --
# has exactly one definition.


def find_by_seed_ticket_id(ticket_id: str) -> Optional[dict]:
    table = get_incidents_table()
    IncidentQuery = Query()
    doc = table.get(IncidentQuery.seed_ticket_id == ticket_id)
    if doc is None:
        return None
    return _row_to_incident(doc)


def insert_seed_incident(record: dict) -> dict:
    """`record` must already be a fully-formed, validated row (see
    scripts/seed_incidents.py's transform step) including the
    `seed_ticket_id` dedup key."""
    table = get_incidents_table()
    with db_lock:
        doc_id = table.insert(record)
        return _row_to_incident(table.get(doc_id=doc_id))
