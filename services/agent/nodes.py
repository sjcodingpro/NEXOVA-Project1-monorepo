"""Graph nodes. One responsibility each; RAG logic is imported from data/pipelines/rag.py,
never re-implemented here.

- receive_question  normalise and validate the SDR's question
- retrieve          data.pipelines.rag.retrieve(question)           (search only)
- generate          data.pipelines.rag.generate_answer(question, context)  (generation only)
- no_context        honest fixed answer when nothing cleared min_score (no model call,
                    so it cannot invent Nexova facts)

The monolithic rag.query() (retrieve + generate) is deliberately never called: retrieval
runs exactly once, in its own node, and generation reuses its output.
"""
from __future__ import annotations

import re

from data.pipelines import rag as rag_pipeline
from services.agent.tracing import traced

MAX_QUESTION_CHARS = 1000

NO_CONTEXT_ANSWER = (
    "I don't have information about that in Nexova's sales knowledge base. "
    "Please check with a senior account manager before answering the prospect."
)


@traced("receive_question")
def receive_question(state: dict):
    question = re.sub(r"\s+", " ", state.get("question") or "").strip()
    if not question:
        return ({"question": "", "error": "empty_question"},
                "rejected: the question is empty", {"error": "empty_question"})
    if len(question) > MAX_QUESTION_CHARS:
        return ({"question": question[:MAX_QUESTION_CHARS], "error": "question_too_long"},
                f"rejected: {len(question)} characters (max {MAX_QUESTION_CHARS})",
                {"error": "question_too_long"})
    return ({"question": question, "error": None},
            f"accepted ({len(question)} characters)", {"question": question})


@traced("retrieve")
def retrieve_node(state: dict):
    try:
        context = rag_pipeline.retrieve(state["question"])
    except Exception as exc:  # Qdrant down, embeddings API error...
        return ({"context": None, "error": "retrieval_failed"},
                f"failed: {type(exc).__name__}", {"error": "retrieval_failed"})
    chunks = [{"source_document": c.get("source_document"), "section": c.get("section"),
               "chunk_index": c.get("chunk_index"), "text": c.get("text")} for c in context]
    return ({"context": context},
            f"{len(context)} chunk(s) above min_score {rag_pipeline.DEFAULT_MIN_SCORE}",
            {"chunks": chunks})


@traced("generate")
def generate_node(state: dict):
    try:
        answer = rag_pipeline.generate_answer(state["question"], state["context"])
    except Exception as exc:  # model API error, timeout...
        return ({"answer": None, "error": "generation_failed"},
                f"failed: {type(exc).__name__}", {"error": "generation_failed"})
    if not answer:
        return ({"answer": None, "error": "generation_failed"},
                "failed: empty answer from the model", {"error": "generation_failed"})
    return ({"answer": answer}, f"answered from {len(state['context'])} chunk(s)",
            {"answer": answer})


@traced("no_context")
def no_context_node(state: dict):
    return ({"answer": NO_CONTEXT_ANSWER},
            "no chunk cleared min_score: honest 'not covered' answer, model not called",
            {"answer": NO_CONTEXT_ANSWER})


# --------------------------------------------------------------------------- routing
def route_after_receive(state: dict) -> str:
    return "end" if state.get("error") else "retrieve"


def route_after_retrieve(state: dict) -> str:
    if state.get("error"):
        return "end"
    return "generate" if state.get("context") else "no_context"
