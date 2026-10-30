"""Task status endpoints (DEV-55)."""
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status

from app.celery_app import celery_app, read_dlq_records

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Celery state -> the four statuses the API exposes.
STATUS_BY_STATE = {
    "PENDING": "pending",
    "RECEIVED": "pending",
    "STARTED": "started",
    "RETRY": "started",
    "SUCCESS": "success",
    "FAILURE": "failure",
    "REVOKED": "failure",
}


@router.get("/dlq/records")
def dlq_records(limit: int = 50):
    """Tasks that failed 3 times: task_id, attempt number and error message."""
    try:
        return {"records": read_dlq_records(min(max(limit, 1), 200))}
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Task broker unavailable.")


@router.get("/{task_id}")
def get_task_status(task_id: str):
    """Current status of a task, plus the result (success) or the error (failure)."""
    try:
        result = AsyncResult(task_id, app=celery_app)
        state = result.state
        body = {
            "task_id": task_id,
            "status": STATUS_BY_STATE.get(state, state.lower()),
            "state": state,
        }
        if state == "SUCCESS":
            body["result"] = result.result
        elif state == "FAILURE":
            body["error"] = str(result.result)
        elif state == "RETRY":
            body["error"] = f"Retrying after: {result.result}"
        return body
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Task backend unavailable.")
