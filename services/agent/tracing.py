"""Per-run traces: which nodes ran, in what order, what each produced, and the checkpoints.

Traces are appended as JSON lines to data/agent_traces/runs.jsonl (override with
AGENT_TRACE_PATH) so they can be queried after the run: get_trace(trace_id), list_traces(),
or GET /agent/traces/{trace_id} on the API. Nothing here is printed-and-forgotten.
"""
from __future__ import annotations

import functools
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(os.environ.get("RAG_REPO_ROOT", Path(__file__).resolve().parents[2]))
_lock = threading.Lock()


def trace_path() -> Path:
    return Path(os.environ.get("AGENT_TRACE_PATH", REPO_ROOT / "data" / "agent_traces" / "runs.jsonl"))


def traced(node_name: str) -> Callable:
    """Wrap a node so it appends {node, summary, output, duration_ms} to state["trace_steps"].

    The node returns (update, summary, output): `update` is its normal state update,
    `summary` a one-line description, `output` a small JSON-able dict of what it produced.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            started = time.perf_counter()
            update, summary, output = fn(state)
            step = {
                "node": node_name,
                "summary": summary,
                "output": output,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
            return {**update, "trace_steps": [step]}
        wrapper.node_name = node_name
        return wrapper
    return decorator


def save_trace(record: dict) -> None:
    path = trace_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def list_traces(limit: int = 20) -> list[dict]:
    """Most recent traces first."""
    path = trace_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in reversed(lines[-limit:]) if line.strip()]


def get_trace(trace_id: str) -> dict | None:
    path = trace_path()
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            record = json.loads(line)
            if record.get("trace_id") == trace_id:
                return record
    return None
