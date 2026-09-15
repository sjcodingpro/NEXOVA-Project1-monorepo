"""
Incident endpoints.

Existing (incident-analyzer milestone):
    POST /api/incidents/analyze        -- upload a CSV, get the summary as JSON
    GET  /api/incidents/results/export -- download the most recent analysis as CSV

New (Centralized Incident Manager milestone):
    POST  /api/incidents                     -- register an incident
    GET   /api/incidents                     -- list incidents (filterable)
    GET   /api/incidents/summary             -- aggregated counts
    GET   /api/incidents/{incident_id}       -- incident detail
    PATCH /api/incidents/{incident_id}/status -- move an incident through its lifecycle

All new routes require auth (get_current_user), matching the rest of the
API (users, profiles, suppliers) and this same router's existing /analyze
endpoint.
"""

import csv
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from pydantic import ValidationError

from app.auth.security import get_current_user
from app.incidents import logic, service
from app.incidents.models import (
    Branch,
    Category,
    IncidentCreate,
    IncidentOut,
    IncidentStatusUpdate,
    InvalidTransitionError,
    Origin,
    Status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# H7: caps how much of an upload we ever hold in memory at once.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# In-memory store for "the last analysis" -- sufficient for this milestone's
# scope (no persistence layer required). A future milestone could persist
# this per-upload in a database instead of module-level state.
_last_summary = None


@router.post("/analyze")
async def analyze_incidents(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    global _last_summary

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a .csv file.",
        )

    # H7: file.read() with no argument pulls the entire upload into
    # memory regardless of size. Reading one byte past the cap lets us
    # detect an oversized upload without ever holding more than
    # MAX_UPLOAD_BYTES + 1 bytes in memory at once.
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"CSV file is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be UTF-8 encoded text.",
        )

    # H7: load_rows_from_text was called bare -- a malformed CSV (NUL
    # bytes, a field exceeding csv's field-size limit) raised csv.Error
    # as an unhandled 500 instead of a clean 400.
    try:
        rows = logic.load_rows_from_text(text)
    except csv.Error:
        raise HTTPException(status_code=400, detail="Could not parse the CSV.")
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="CSV file has no data rows.",
        )

    missing_columns = [c for c in logic.REQUIRED_COLUMNS if c not in rows[0].keys()]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {', '.join(missing_columns)}",
        )

    summary = logic.analyze(rows)
    _last_summary = summary
    return summary


@router.get("/results/export")
async def export_results(current_user: dict = Depends(get_current_user)):
    if _last_summary is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis has been run yet. Call POST /api/incidents/analyze first.",
        )

    csv_text = logic.summary_to_csv_text(_last_summary)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )


# --- Centralized Incident Manager -------------------------------------------


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate, current_user: dict = Depends(get_current_user)
):
    created = service.create_incident(payload)
    return IncidentOut(**created)


@router.get("/summary")
async def get_summary(current_user: dict = Depends(get_current_user)):
    # Registered before the /{incident_id} routes below so "summary"
    # is never mistaken for an incident id.
    return service.get_summary()


@router.get("", response_model=list[IncidentOut])
async def list_incidents(
    status: Optional[Status] = None,
    origin: Optional[Origin] = None,
    branch: Optional[Branch] = None,
    category: Optional[Category] = None,
    current_user: dict = Depends(get_current_user),
):
    # Parameter shadows the `status` module imported above (used for
    # status.HTTP_* elsewhere in this file) -- safe, since this function
    # never references that module, only the query param.
    incidents = service.list_incidents(
        status=status, origin=origin, branch=branch, category=category
    )
    # M13: a single malformed row (hand-edited DB, or a record predating
    # a schema change) previously 500'd this entire endpoint via an
    # unhandled pydantic ValidationError from IncidentOut(**i). Validate
    # per-row instead -- one bad record is skipped and logged rather than
    # taking down the whole register.
    result: list[IncidentOut] = []
    for i in incidents:
        try:
            result.append(IncidentOut(**i))
        except ValidationError:
            logger.warning("Skipping malformed incident row id=%s", i.get("id"))
    return result


@router.get("/{incident_id}", response_model=IncidentOut)
async def get_incident(incident_id: int, current_user: dict = Depends(get_current_user)):
    incident = service.get_incident_by_id(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    return IncidentOut(**incident)


@router.patch("/{incident_id}/status", response_model=IncidentOut)
async def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    try:
        updated = service.update_incident_status(incident_id, payload.status)
    except InvalidTransitionError as exc:
        # M16: builds the client message from the exception's own
        # structured current/target fields rather than forwarding
        # str(exc) directly -- see InvalidTransitionError's docstring
        # in models.py for why that distinction matters even though
        # today's message content is safe either way.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move an incident from '{exc.current}' to '{exc.target}'.",
        )

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    return IncidentOut(**updated)
