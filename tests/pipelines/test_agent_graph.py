"""Unit tests for the agent graph's structure and node contracts (RAG functions stubbed).

Run: uv run pytest tests/pipelines/test_agent_graph.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph  # noqa: E402

from data.pipelines import rag  # noqa: E402
from services.agent import graph as agent_graph  # noqa: E402
from services.agent import nodes  # noqa: E402
from services.agent.state import AgentState  # noqa: E402

CHUNK = {"source_document": "pricing-model", "section": "Pricing Model › Corporate training",
         "chunk_index": 0, "text": "8-week program: starting at 6,200 USD for groups of up to 15 people."}


@pytest.fixture
def stub_rag(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_TRACE_PATH", str(tmp_path / "runs.jsonl"))
    calls = []

    def fake_retrieve(question):
        calls.append(("retrieve", question))
        return [CHUNK] if "cost" in question else []

    def fake_generate(question, context):
        calls.append(("generate", question, context))
        return "It starts at 6,200 USD for up to 15 people."

    def forbidden_query(*_a, **_k):
        raise AssertionError("query() (retrieve + generate) must never be called by the agent")

    monkeypatch.setattr(rag, "retrieve", fake_retrieve)
    monkeypatch.setattr(rag, "generate_answer", fake_generate)
    monkeypatch.setattr(rag, "query", forbidden_query)
    return calls


def fresh_graph():
    from langgraph.checkpoint.memory import MemorySaver
    return agent_graph.build_graph(MemorySaver())


def test_generation_reuses_retrieved_context_and_retrieval_runs_once(stub_rag):
    record = agent_graph.run_agent("How much does the 8-week program cost?", graph=fresh_graph())
    assert record["sources_used"] == ["rag"] and record["route"] == "rag"
    assert record["node_order"] == ["receive_question", "route_intent", "retrieve", "generate"]
    assert [c[0] for c in stub_rag] == ["retrieve", "generate"]
    assert stub_rag[1][2] == [CHUNK]                     # generate got retrieve's own output
    assert "6,200" in record["answer"]


def test_no_context_routes_to_honest_node_without_calling_the_model(stub_rag):
    record = agent_graph.run_agent("weather?", graph=fresh_graph())
    assert record["node_order"] == ["receive_question", "route_intent", "retrieve", "no_context"]
    assert [c[0] for c in stub_rag] == ["retrieve"]
    assert record["answer"] == nodes.NO_CONTEXT_ANSWER


def test_retrieval_failure_ends_with_error_code_not_exception(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_TRACE_PATH", str(tmp_path / "runs.jsonl"))
    monkeypatch.setattr(rag, "retrieve", lambda q: (_ for _ in ()).throw(ConnectionError("qdrant down")))
    record = agent_graph.run_agent("How much?", graph=fresh_graph())
    assert record["node_order"] == ["receive_question", "route_intent", "retrieve"]
    assert record["error"] == "retrieval_failed" and record["answer"] is None
    assert "qdrant down" not in str(record)              # internal details stay out of the trace output


def test_trace_is_persisted_and_queryable(stub_rag):
    from services.agent.tracing import get_trace, list_traces
    record = agent_graph.run_agent("How much does it cost?", graph=fresh_graph())
    assert get_trace(record["trace_id"])["node_order"] == record["node_order"]
    assert list_traces(1)[0]["trace_id"] == record["trace_id"]


def test_checkpointer_stores_every_transition(stub_rag):
    g = fresh_graph()
    record = agent_graph.run_agent("How much does it cost?", graph=g)
    history = list(g.get_state_history({"configurable": {"thread_id": record["trace_id"]}}))
    assert len(history) == len(record["node_order"]) + 2   # input + one per node + final
    assert history[0].values["answer"] == record["answer"]  # latest checkpoint = final state


def test_module_level_graph_is_compiled():
    assert hasattr(agent_graph.GRAPH, "invoke") and agent_graph.GRAPH.checkpointer is not None
    assert set(agent_graph.GRAPH.get_graph().nodes) >= {
        "receive_question", "route_intent", "lookup_ticket", "handle_tool_failure",
        "retrieve", "generate", "no_context", "synthesize_answer"}


def test_structural_error_fails_at_compile_time():
    builder = StateGraph(AgentState)
    builder.add_node("receive_question", nodes.receive_question)
    builder.add_edge(START, "receive_question")
    builder.add_edge("receive_question", "retrive")      # typo: node doesn't exist
    with pytest.raises(ValueError):
        builder.compile()


def test_router_functions_follow_output_conditions():
    assert nodes.route_after_receive({"error": "empty_question"}) == "end"
    assert nodes.route_after_receive({"error": None}) == "route_intent"
    assert nodes.route_after_intent({"route": "rag"}) == "retrieve"
    assert nodes.route_after_intent({"route": "ticket_tool"}) == "lookup_ticket"
    assert nodes.route_after_lookup({"route": "ticket_tool", "tool_result": {"found": False}}) == "handle_tool_failure"
    assert nodes.route_after_lookup({"route": "both", "tool_result": {"found": True}}) == "retrieve"
    assert nodes.route_after_lookup({"route": "ticket_tool", "tool_result": {"found": True}}) == "synthesize_answer"
    assert nodes.route_after_retrieve({"route": "both", "context": []}) == "synthesize_answer"
    assert nodes.route_after_retrieve({"error": "retrieval_failed"}) == "end"
    assert nodes.route_after_retrieve({"context": []}) == "no_context"
    assert nodes.route_after_retrieve({"context": [CHUNK]}) == "generate"
