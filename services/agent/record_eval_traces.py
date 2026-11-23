"""Record real agent runs as trace fixtures for the evals in tests/pipelines/test_agent_evals.py.

Runs the compiled graph (real Qdrant + 4Geeks models) once per eval case and saves each
trace to tests/pipelines/fixtures/agent_traces/<case>.json. The evals then assert against
those saved traces, so CI never needs live model calls. Re-record after changing the graph,
the prompt or the knowledge base.

Run from the repo root:  uv run python -m services.agent.record_eval_traces
"""
from __future__ import annotations

import json
from pathlib import Path

from services.agent.graph import run_agent

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "pipelines" / "fixtures" / "agent_traces"

EVAL_CASES = {
    "pricing_8_week_training": "How much does an 8-week training program cost?",
    "objection_discount_15": "22% seems expensive. Can you do 15%?",
    "off_topic_weather": "What's the weather like in Valencia this weekend?",
    "empty_question": "   ",
}


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, question in EVAL_CASES.items():
        record = run_agent(question)
        (FIXTURES / f"{name}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
        print(f"{name:26} {' -> '.join(record['node_order']):45} error={record['error']}  "
              f"trace_id={record['trace_id']}")
    print(f"\nSaved {len(EVAL_CASES)} traces to {FIXTURES.relative_to(FIXTURES.parents[3])}")


if __name__ == "__main__":
    main()
