"""Build, compile and run the Nexova support agent graph.

    receive_question ──(empty/too long)─────────────────────────────────► END
           ▼
      route_intent ──(rag)──────────────────────────┐
           │ (ticket_tool / both)                   ▼
      lookup_ticket ──(failed)──► handle_tool_failure   retrieve ──(error, rag)──► END
           │ (found)                  │                 │ rag: chunks ─► generate ─► END
           │ ticket_tool ─────────────┴─► synthesize_answer ◄── both    │ rag: none ─► no_context ─► END
           │ both ───────────────────────────────► retrieve             │
                                                  synthesize_answer ─► END

GRAPH is compiled at import time, so a structural error (an edge to a missing node, a node
with no path to END...) stops the API from starting instead of failing on a live request.
A MemorySaver checkpointer stores the state after every node (thread_id = trace_id), and
each run's trace records those checkpoints, the route taken and the sources used.
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

GRAPH_VERSION = "agent-mcp-v1"
logger = logging.getLogger("nexova.agent")
SOURCES = {"lookup_ticket": "ticket_tool", "retrieve": "rag"}


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)
    builder.add_node("receive_question", nodes.receive_question)
    builder.add_node("route_intent", nodes.route_intent)
    builder.add_node("lookup_ticket", nodes.lookup_ticket_node)
    builder.add_node("handle_tool_failure", nodes.handle_tool_failure)
    builder.add_node("retrieve", nodes.retrieve_node)
    builder.add_node("generate", nodes.generate_node)
    builder.add_node("no_context", nodes.no_context_node)
    builder.add_node("synthesize_answer", nodes.synthesize_answer)

    builder.add_edge(START, "receive_question")
    builder.add_conditional_edges("receive_question", nodes.route_after_receive,
                                  {"route_intent": "route_intent", "end": END})
    builder.add_conditional_edges("route_intent", nodes.route_after_intent,
                                  {"retrieve": "retrieve", "lookup_ticket": "lookup_ticket"})
    builder.add_conditional_edges("lookup_ticket", nodes.route_after_lookup,
                                  {"handle_tool_failure": "handle_tool_failure", "retrieve": "retrieve",
                                   "synthesize_answer": "synthesize_answer"})
    builder.add_conditional_edges("handle_tool_failure", nodes.route_after_tool_failure,
                                  {"retrieve": "retrieve", "synthesize_answer": "synthesize_answer"})
    builder.add_conditional_edges("retrieve", nodes.route_after_retrieve,
                                  {"generate": "generate", "no_context": "no_context",
                                   "synthesize_answer": "synthesize_answer", "end": END})
    builder.add_edge("generate", END)
    builder.add_edge("no_context", END)
    builder.add_edge("synthesize_answer", END)
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
        "route": final.get("route"),
        "route_rationale": final.get("route_rationale"),
        # Which data sources ran, in order: "ticket_tool" (incident manager) and/or "rag".
        "sources_used": [SOURCES[s["node"]] for s in steps if s["node"] in SOURCES],
        "tool_outcome": (final.get("tool_result") or {}).get("outcome"),
        # Transport evidence: which MCP server tool answered (None when no ticket lookup ran).
        "tool_via": (final.get("tool_result") or {}).get("via"),
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
