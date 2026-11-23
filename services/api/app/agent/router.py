"""Sales support agent endpoints (LangGraph, Support Agent Part 1).

POST /agent/query          run the compiled graph, return {answer, trace_id}
GET  /agent/traces         most recent run traces
GET  /agent/traces/{id}    one run's trace: node order, each node's output, checkpoints

No RAG or agent logic lives here: the router only invokes services/agent/graph.py and maps
its error codes to HTTP responses. The graph is imported (and so compiled) when this module
loads, so a broken graph stops the API at startup, not on the first request.
"""
import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

# services/agent and data/ live at the repo root (4 levels up locally; RAG_REPO_ROOT in Docker).
_PARENTS = Path(__file__).resolve().parents
_REPO_ROOT = Path(os.environ.get("RAG_REPO_ROOT") or (_PARENTS[4] if len(_PARENTS) > 4 else "/nonexistent"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.agent.graph import run_agent  # noqa: E402  (compiles the graph)
from services.agent.tracing import get_trace, list_traces  # noqa: E402

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger("nexova_api.agent")

# Graph error code -> (HTTP status, message). Messages never include exception details.
_ERRORS = {
    "empty_question": (status.HTTP_422_UNPROCESSABLE_ENTITY, "The question is empty."),
    "question_too_long": (status.HTTP_422_UNPROCESSABLE_ENTITY, "The question is too long (max 1000 characters)."),
    "retrieval_failed": (status.HTTP_503_SERVICE_UNAVAILABLE, "Agent failed during retrieval."),
    "generation_failed": (status.HTTP_503_SERVICE_UNAVAILABLE, "Agent failed while generating the answer."),
}


class AgentQueryRequest(BaseModel):
    # No min_length: an empty question is routed by the graph itself (receive_question -> END).
    question: str = Field("", max_length=2000)


class AgentQueryResponse(BaseModel):
    answer: str
    trace_id: str


@router.post("/query", response_model=AgentQueryResponse)
def agent_query(body: AgentQueryRequest) -> AgentQueryResponse:
    record = run_agent(body.question)
    error = record.get("error")
    if error or not record.get("answer"):
        code, message = _ERRORS.get(error, (status.HTTP_500_INTERNAL_SERVER_ERROR, "The agent failed."))
        logger.warning("agent run %s failed: %s", record["trace_id"], error)
        raise HTTPException(code, f"{message} Check trace {record['trace_id']}.")
    return AgentQueryResponse(answer=record["answer"], trace_id=record["trace_id"])


@router.get("/traces")
def agent_traces(limit: int = Query(20, ge=1, le=200)):
    return list_traces(limit)


@router.get("/traces/{trace_id}")
def agent_trace(trace_id: str):
    record = get_trace(trace_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not found.")
    return record
