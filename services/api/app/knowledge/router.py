"""Sales knowledge base endpoint (Milestone 7 — RAG).

No retrieval or generation logic lives here: the router only calls query() from
data/pipelines/rag.py and returns the generated answer. Chunks, scores and Qdrant ids are
never part of the response.
"""
import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
logger = logging.getLogger("nexova_api.knowledge")

# The repo root holds data/. Locally it's 4 folders up from this file; in Docker it's
# mounted and named by RAG_REPO_ROOT (see docker-compose.yml).
_PARENTS = Path(__file__).resolve().parents
_REPO_ROOT = Path(os.environ.get("RAG_REPO_ROOT") or (_PARENTS[4] if len(_PARENTS) > 4 else "/nonexistent"))


def _rag():
    """Import data/pipelines/rag.py lazily so a missing data/ folder or RAG dependency
    answers 503 instead of stopping the whole API from starting."""
    try:
        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from data.pipelines import rag
        return rag
    except Exception as exc:
        logger.exception("RAG pipeline import failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The sales knowledge base is not available in this environment.") from exc


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


class QueryResponse(BaseModel):
    answer: str


@router.post("/query", response_model=QueryResponse)
def knowledge_query(body: QueryRequest) -> QueryResponse:
    """Answer an SDR's question as a Nexova salesperson, from the indexed source documents."""
    rag = _rag()
    try:
        answer = rag.query(body.question)
    except Exception as exc:  # Qdrant down, model API error, missing config...
        logger.exception("Knowledge query failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The sales assistant couldn't answer right now. Please try again.") from exc
    if not answer:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The model returned an empty answer.")
    return QueryResponse(answer=answer)
