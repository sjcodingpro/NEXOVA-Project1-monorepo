"""Record real agent runs as trace fixtures for the evals in tests/pipelines/test_agent_evals.py.

Runs the compiled graph (real Qdrant + 4Geeks models + the real incident manager) once per eval case and saves each
trace to tests/pipelines/fixtures/agent_traces/<case>.json. The evals then assert against
those saved traces, so CI never needs live model calls. Re-record after changing the graph,
the prompt or the knowledge base.

Run from the repo root, with services/api's environment (the ticket tool imports the incident
manager's service layer, which needs its dependencies):

    uv run --project services/api python -m services.agent.record_eval_traces
"""
from __future__ import annotations

import json
from pathlib import Path

from services.agent.graph import run_agent

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "pipelines" / "fixtures" / "agent_traces"

EVAL_CASES = {
    # Part 1: RAG path
    "pricing_8_week_training": "How much does an 8-week training program cost?",
    "objection_discount_15": "22% seems expensive. Can you do 15%?",
    "off_topic_weather": "What's the weather like in Valencia this weekend?",
    "empty_question": "   ",
    # Part 2: routing between the knowledge base and the incident manager
    "rag_shortlist_policy": "What happens if the shortlist doesn't work for me?",
    "ticket_status_96": "What's the status of ticket 96?",
    "ticket_missing_482": "What is the status of ticket 482?",
    "ticket_and_policy": "Ticket 96 came from a client: what happens if the shortlist doesn't work for them?",
}


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, question in EVAL_CASES.items():
        record = run_agent(question)
        (FIXTURES / f"{name}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
        print(f"{name:24} {' -> '.join(record['node_order']):95} sources={record['sources_used']} "
              f"tool={record['tool_outcome']} error={record['error']}")
    print(f"\nSaved {len(EVAL_CASES)} traces to {FIXTURES.relative_to(FIXTURES.parents[3])}")


if __name__ == "__main__":
    main()
