"""Reporting endpoints for the weekly office performance pipeline.

No ETL logic lives here: everything is imported from data/pipelines/pipeline.py.
"""
import sys
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.security import get_current_user

router = APIRouter(prefix="/reporting", tags=["reporting"])

# Inside a Docker image built from services/api only, this file has fewer than 5 parent
# folders (parents[4] would raise IndexError at import and stop the whole API from starting).
# Fall back to a path that does not exist: _pipeline() then answers 503 instead.
_PARENTS = Path(__file__).resolve().parents
_PIPELINES_DIR = (_PARENTS[4] if len(_PARENTS) > 4 else Path("/nonexistent")) / "data" / "pipelines"


def _pipeline():
    """Import data/pipelines/pipeline.py lazily, so a missing data/ folder (for example
    inside a Docker image built from services/api only) cannot stop the API from starting."""
    try:
        if str(_PIPELINES_DIR) not in sys.path:
            sys.path.insert(0, str(_PIPELINES_DIR))
        import pipeline
        return pipeline
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The reporting pipeline is not available in this environment.",
        ) from exc


class TriggerRequest(BaseModel):
    weeks_back: int = Field(3, ge=1, le=12)


@router.get("/weekly-office-program-performance")
def weekly_office_program_performance(week_start: date | None = Query(default=None)):
    """KPI rows for one ISO week (defaults to the most recent computed week)."""
    if week_start is not None and week_start.weekday() != 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "week_start must be a Monday")
    return _pipeline().get_weekly_office_program_performance(week_start)


@router.get("/pipeline-runs/latest")
def latest_pipeline_run():
    """Status and metadata of the most recent pipeline run."""
    run = _pipeline().get_latest_pipeline_run()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pipeline runs yet")
    return run


@router.post("/pipeline-runs", status_code=status.HTTP_202_ACCEPTED)
def trigger_pipeline_run(
    body: TriggerRequest | None = Body(default=None),
    current_user: dict = Depends(get_current_user),
):
    """Manual trigger. Returns 202 with the run_id, or 409 if a run is already in progress."""
    result = _pipeline().trigger_pipeline_run((body or TriggerRequest()).weeks_back)
    if result["status"] == "conflict":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": "A pipeline run is already in progress",
                    "running_run_id": result["running_run_id"]},
        )
    return {"message": "Pipeline run submitted", "run_id": result["run_id"]}
