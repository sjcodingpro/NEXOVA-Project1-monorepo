"""Unit tests for the ticket tool contract, its timeout/fallback, and intent routing.

The incident manager is replaced by an in-memory stand-in with the same read-only get/list
methods; the routing and graph logic under test is the real code.

Run: uv run pytest tests/pipelines/test_agent_tools.py -q
"""
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.pipelines import rag  # noqa: E402
from services.agent import graph as agent_graph  # noqa: E402
from services.agent import nodes, tools  # noqa: E402

TICKET_96 = {"id": 96, "title": "Mobile app crashes on iOS 17 after update", "status": "open",
             "category": "technical_failure", "origin": "customer", "branch": "central",
             "created_at": "2024-01-28T00:00:00+00:00", "updated_at": "2024-01-28T00:00:00+00:00"}


class FakeIncidents:
    def __init__(self, rows=(TICKET_96,), delay=0.0):
        self.rows, self.delay, self.calls = list(rows), delay, []

    def get(self, ticket_id):
        self.calls.append(("get", ticket_id))
        time.sleep(self.delay)
        return next((r for r in self.rows if r["id"] == ticket_id), None)

    def list(self, status):
        self.calls.append(("list", status))
        time.sleep(self.delay)
        rows = [r for r in self.rows if r["status"] == status]
        return {"total": len(rows), "incidents": rows[:tools.MAX_LISTED]}   # list_incidents' shape


@pytest.fixture
def incidents(monkeypatch):
    fake = FakeIncidents()
    monkeypatch.setattr(tools, "_client", fake)
    return fake


@pytest.fixture
def stub_rag(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_TRACE_PATH", str(tmp_path / "runs.jsonl"))
    calls = []
    monkeypatch.setattr(rag, "retrieve", lambda q: calls.append("retrieve") or [
        {"source_document": "objection-handling", "section": "S", "chunk_index": 0,
         "text": "Nexova offers one additional round of search at no cost."}])
    monkeypatch.setattr(rag, "generate_answer", lambda q, c: calls.append("generate") or
                        "We offer one additional round of search at no cost.")
    return calls


def run(question):
    from langgraph.checkpoint.memory import MemorySaver
    return agent_graph.run_agent(question, graph=agent_graph.build_graph(MemorySaver()))


# ---------------------------------------------------------------------- typed contract
def test_lookup_by_id_returns_typed_ticket(incidents):
    out = tools.lookup_ticket(tools.TicketLookupInput(ticket_id=96))
    assert isinstance(out, tools.TicketLookupOutput)
    assert out.found and out.outcome == "success"
    assert out.tickets[0].status == "open" and out.tickets[0].category == "technical_failure"


def test_missing_ticket_is_not_found_not_an_exception(incidents):
    out = tools.lookup_ticket(tools.TicketLookupInput(ticket_id=482))
    assert (out.found, out.outcome) == (False, "not_found") and out.tickets == []


def test_list_by_status(incidents):
    out = tools.lookup_ticket(tools.TicketLookupInput(status="open"))
    assert out.found and out.total_matching == 1 and out.tickets[0].ticket_id == 96


def test_input_contract_rejects_invalid_values():
    with pytest.raises(ValueError):
        tools.TicketLookupInput(ticket_id=0)
    with pytest.raises(ValueError):
        tools.TicketLookupInput(status="closed-ish")


# ---------------------------------------------------------------- timeout and fallback
def test_timeout_is_explicit_and_numeric():
    assert isinstance(tools.TICKET_TOOL_TIMEOUT_S, float) and 0 < tools.TICKET_TOOL_TIMEOUT_S <= 5


def test_slow_incident_manager_times_out_and_graph_falls_back(monkeypatch, stub_rag):
    monkeypatch.setattr(tools, "TICKET_TOOL_TIMEOUT_S", 0.2)
    monkeypatch.setattr(tools, "_client", FakeIncidents(delay=1.0))
    started = time.perf_counter()
    record = run("What's the status of ticket 96?")
    assert time.perf_counter() - started < 1.0                       # the graph did not hang
    assert record["tool_outcome"] == "timeout"
    assert record["node_order"] == ["receive_question", "route_intent", "lookup_ticket",
                                    "handle_tool_failure", "synthesize_answer"]
    assert "couldn't confirm that ticket's status right now" in record["answer"]
    assert not re.search(r"\b(Open|Resolved|In progress|Discarded)\b", record["answer"])  # no invented status


def test_broken_incident_manager_falls_back(monkeypatch, stub_rag):
    class Broken:
        def get(self, _): raise RuntimeError("db unreadable")
        def list(self, _): raise RuntimeError("db unreadable")
    monkeypatch.setattr(tools, "_client", Broken())
    record = run("Check incident #96")
    assert record["tool_outcome"] == "error" and "handle_tool_failure" in record["node_order"]
    assert "db unreadable" not in record["answer"]


# ------------------------------------------------------------------------------ routing
@pytest.mark.parametrize("question, route, query", [
    ("What's the status of ticket 482?", "ticket_tool", {"ticket_id": 482}),
    ("Can you check incident #12?", "ticket_tool", {"ticket_id": 12}),
    ("How many open tickets do we have?", "ticket_tool", {"status": "open"}),
    ("Show me in-progress incidents", "ticket_tool", {"status": "in_progress"}),
    ("How much does an 8-week training program cost?", "rag", None),
    ("What happens if the shortlist doesn't work for me?", "rag", None),
    ("22% seems expensive, can you do 15%?", "rag", None),
    ("Ticket 96 is a shortlist complaint: what do we offer if the shortlist doesn't work?", "both", {"ticket_id": 96}),
])
def test_router_picks_source_from_question_content(question, route, query):
    update = nodes.route_intent({"question": question})
    assert update["route"] == route and update["ticket_query"] == query


@pytest.mark.parametrize("question, expected", [
    ("Ticket 96 came from a client: what does our replacement guarantee cover?",
     "what does our replacement guarantee cover?"),
    ("Ticket 96 is a shortlist complaint: what do we offer if the shortlist doesn't work?",
     "what do we offer if the shortlist doesn't work?"),
    ("For incident #12, what is the standard fee?", "what is the standard fee?"),
])
def test_mixed_question_searches_the_knowledge_base_without_the_ticket_part(question, expected):
    update = nodes.route_intent({"question": question})
    assert update["route"] == "both" and update["rag_question"] == expected


def test_ticket_question_uses_tool_only(incidents, stub_rag):
    record = run("What's the status of ticket 96?")
    assert record["sources_used"] == ["ticket_tool"] and stub_rag == []
    assert '"Mobile app crashes on iOS 17 after update" is **Open**' in record["answer"]


def test_policy_question_uses_rag_only(incidents, stub_rag):
    record = run("What happens if the shortlist doesn't work for me?")
    assert record["sources_used"] == ["rag"] and incidents.calls == []


def test_mixed_question_runs_tool_then_rag(incidents, stub_rag):
    record = run("Ticket 96 is a shortlist complaint: what do we offer if the shortlist doesn't work?")
    assert record["sources_used"] == ["ticket_tool", "rag"]
    assert "is **Open**" in record["answer"] and "additional round" in record["answer"]


# --------------------------------------------------------------------------- read-only
def test_ticket_tool_is_read_only():
    source = Path(tools.__file__).read_text(encoding="utf-8")
    for write_fn in ("create_incident", "update_incident_status", "insert_seed_incident",
                     "table.insert", "table.update", "table.remove", ".upsert(", "db_lock"):
        assert write_fn not in source, f"tools.py must not reference {write_fn}"
    assert not re.search(r"\b(post|put|patch|delete)\(", source, re.I)   # no HTTP writes either
    assert {m for m in vars(tools.McpIncidentClient) if not m.startswith("_")} == {"get", "list", "prepare"}
    assert set(tools.READ_TOOLS.values()) == {"get_incident", "list_incidents"}   # only read tools are called


def test_agent_reaches_incidents_only_through_mcp():
    agent_dir = Path(tools.__file__).parent
    for py in agent_dir.glob("*.py"):
        src = py.read_text(encoding="utf-8")
        assert "app.incidents" not in src and "services.api" not in src and "db.json" not in src, py.name
    assert "langchain_mcp_adapters" in Path(tools.__file__).read_text(encoding="utf-8")


def test_mcp_client_maps_server_errors(monkeypatch):
    class StaticToken:
        def get(self): return "test-token"
    client = tools.McpIncidentClient(url="http://unused", token_provider=StaticToken())

    async def not_found(action, args): raise tools.McpToolError("NOT_FOUND", "no ticket")
    monkeypatch.setattr(client, "_invoke", not_found)
    assert client.get(482) is None

    async def denied(action, args): raise tools.McpToolError("AUTH_INSUFFICIENT_SCOPE", "x")
    monkeypatch.setattr(client, "_invoke", denied)
    monkeypatch.setattr(tools, "_client", client)
    out = tools.lookup_ticket(tools.TicketLookupInput(ticket_id=96))
    assert out.found is False and out.outcome == "error" and "AUTH_INSUFFICIENT_SCOPE" in out.error


def test_one_responsibility_per_tool():
    public_tools = [name for name in dir(tools) if name.startswith("lookup_")]
    assert public_tools == ["lookup_ticket"]          # tickets only; inventory would be its own tool
