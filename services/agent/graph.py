"""Build, compile and run the Nexova sales agent graph.

    receive_question ──(error)──────────────────────────► END
           │ (ok)
           ▼
        retrieve ──(error)──────────────────────────────► END
           │ (chunks)                 │ (no chunks)
           ▼                          ▼
        generate ──► END          no_context ──► END

GRAPH is compiled at import time, so a structural error (an edge to a missing node, a node
with no path to END...) stops the API from starting instead of failing on a live request.
A MemorySaver checkpointer stores the state after every node (thread_id = trace_id), and
each run's trace records those checkpoints.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from services.agent import nodes
from services.agent.state import AgentState
from services.agent.tracing import save_trace

GRAPH_VERSION = "agent-base-v1"
logger = logging.getLogger("nexova.agent")


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)
    builder.add_node("receive_question", nodes.receive_question)
    builder.add_node("retrieve", nodes.retrieve_node)
    builder.add_node("generate", nodes.generate_node)
    builder.add_node("no_context", nodes.no_context_node)

    builder.add_edge(START, "receive_question")
    builder.add_conditional_edges("receive_question", nodes.route_after_receive,
                                  {"retrieve": "retrieve", "end": END})
    builder.add_conditional_edges("retrieve", nodes.route_after_retrieve,
                                  {"generate": "generate", "no_context": "no_context", "end": END})
    builder.add_edge("generate", END)
    builder.add_edge("no_context", END)
    return builder.compile(checkpointer=checkpointer)


# Compiled once, before anything is served.
CHECKPOINTER = MemorySaver()
GRAPH = build_graph(CHECKPOINTER)


def _checkpoints(graph, config) -> list[dict]:
    """Every saved checkpoint for this run, oldest first: which step, which node wrote it,
    and which node runs next. Proves (and lets you inspect) each state transition."""
    history = list(graph.get_state_history(config))
    out = []
    for snap in reversed(history):
        meta = snap.metadata or {}
        steps_so_far = snap.values.get("trace_steps") or []
        out.append({
            "step": meta.get("step"),
            "after_node": steps_so_far[-1]["node"] if steps_so_far else None,
            "next": list(snap.next),
            "state_keys": sorted(snap.values.keys()),
            "checkpoint_id": snap.config["configurable"].get("checkpoint_id"),
        })
    return out


def run_agent(question: str, *, graph=None, persist: bool = True) -> dict:
    """Run the graph for one question and return (and persist) its trace record."""
    graph = graph or GRAPH
    trace_id = f"run-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": trace_id}}
    started = datetime.now(timezone.utc)
    try:
        final = graph.invoke({"question": question, "trace_steps": []}, config)
    except Exception as exc:  # anything a node didn't handle itself
        final = {"question": question, "error": "agent_failed", "answer": None,
                 "trace_steps": [{"node": "graph", "summary": f"failed: {type(exc).__name__}",
                                  "output": {"error": "agent_failed"}, "duration_ms": None}]}
    steps = [{"order": i + 1, **s} for i, s in enumerate(final.get("trace_steps", []))]
    record = {
        "trace_id": trace_id,
        "graph_version": GRAPH_VERSION,
        "started_at": started.isoformat(timespec="seconds"),
        "question": question,
        "node_order": [s["node"] for s in steps],
        "steps": steps,
        "answer": final.get("answer"),
        "error": final.get("error"),
        "checkpoints": _checkpoints(graph, config) if getattr(graph, "checkpointer", None) else [],
    }
    if persist:
        try:
            save_trace(record)
        except OSError:  # a full or read-only disk must not cost the SDR their answer
            logger.exception("could not persist trace %s", trace_id)
    return record
