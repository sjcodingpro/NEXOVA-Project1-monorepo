"""Evals for the LangGraph sales agent, asserted against RECORDED traces of real runs.

Fixtures: tests/pipelines/fixtures/agent_traces/*.json, produced by
    uv run python -m services.agent.record_eval_traces
(real Qdrant + 4Geeks models). No model or Qdrant call happens here.

Run all pipeline tests (RAG + agent):  uv run pytest tests/pipelines -q
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "tests" / "pipelines" / "fixtures" / "agent_traces"

from services.agent.nodes import NO_CONTEXT_ANSWER  # noqa: E402


def trace(name: str) -> dict:
    path = FIXTURES / f"{name}.json"
    if not path.exists():
        pytest.fail(f"Missing {path.name}: run `uv run python -m services.agent.record_eval_traces`")
    return json.loads(path.read_text(encoding="utf-8"))


def step(record: dict, node: str) -> dict:
    return next(s for s in record["steps"] if s["node"] == node)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


# ------------------------------------------------------------------ eval 1: node order
def test_eval_retrieve_runs_before_generation():
    record = trace("pricing_8_week_training")
    assert record["node_order"] == ["receive_question", "retrieve", "generate"]
    assert record["error"] is None
    assert [s["order"] for s in record["steps"]] == [1, 2, 3]


# --------------------------------------------- eval 2: grounded in the BRIEFING knowledge base
def test_eval_pricing_answer_is_grounded_in_the_knowledge_base():
    record = trace("pricing_8_week_training")
    chunks = step(record, "retrieve")["output"]["chunks"]
    assert any(c["source_document"] == "pricing-model" and "Corporate training" in c["section"]
               for c in chunks), "the pricing chunk for training programs must be retrieved"
    answer = record["answer"]
    assert "6,200" in answer or "6200" in answer               # nexova-pricing-model.en.md: 8-week = 6,200 USD
    assert "15" in answer                                       # ... for groups of up to 15 people
    # Faithfulness (BRIEFING section 4): every number in the answer comes from the retrieved
    # chunks or the question itself, never from the model's imagination.
    allowed = _numbers(" ".join(c["text"] for c in chunks) + " " + record["question"])
    invented = _numbers(answer) - allowed
    assert not invented, f"numbers not found in the retrieved context: {invented}"


def test_eval_discount_objection_defers_to_approval_and_keeps_22_percent():
    record = trace("objection_discount_15")
    assert record["node_order"] == ["receive_question", "retrieve", "generate"]
    chunks = step(record, "retrieve")["output"]["chunks"]
    assert any(c["source_document"] == "objection-handling" for c in chunks)
    answer = record["answer"].lower()
    assert "22%" in answer
    assert "approv" in answer                                   # BRIEFING section 6: defer to a human
    assert not re.search(r"\b(we can|i can|happy to) (do|offer|give)[^.]*15%", answer)


# ------------------------------------------- eval 3: error path ends without retrieval
def test_eval_empty_question_ends_before_retrieval():
    record = trace("empty_question")
    assert record["node_order"] == ["receive_question"]
    assert record["error"] == "empty_question"
    assert record["answer"] is None


# ----------------------------------- eval 4: no context -> honest answer, model not called
def test_eval_off_topic_question_gets_honest_answer_without_generation():
    record = trace("off_topic_weather")
    assert record["node_order"] == ["receive_question", "retrieve", "no_context"]
    assert step(record, "retrieve")["output"]["chunks"] == []
    assert "generate" not in record["node_order"]
    assert record["answer"] == NO_CONTEXT_ANSWER


# ------------------------------------------------ eval 5: every transition is checkpointed
@pytest.mark.parametrize("name", ["pricing_8_week_training", "off_topic_weather", "empty_question"])
def test_eval_every_transition_is_checkpointed(name):
    record = trace(name)
    after = [c["after_node"] for c in record["checkpoints"] if c["after_node"]]
    assert after == record["node_order"]                        # one checkpoint after each node
    assert record["checkpoints"][-1]["next"] == []              # the run reached END
