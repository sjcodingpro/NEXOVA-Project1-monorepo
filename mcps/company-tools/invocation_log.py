"""One structured log entry per tool invocation: when, which client, which tool, a summary of
the input, the result (success / error code) and how long it took.

Written as JSON lines to MCP_INVOCATION_LOG (default logs/invocations.jsonl next to this file)
and echoed to the `company_tools.invocations` logger (stdout), so it is both queryable after
the fact and visible live.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("company_tools.invocations")
_lock = threading.Lock()

# Free-text fields are summarised (length only) so ticket descriptions don't fill the log.
_SUMMARISE = {"title", "description"}


def log_path() -> Path:
    return Path(os.environ.get("MCP_INVOCATION_LOG", Path(__file__).resolve().parent / "logs" / "invocations.jsonl"))


def summarise(arguments: dict) -> dict:
    return {k: (f"<{len(str(v))} chars>" if k in _SUMMARISE else v) for k, v in (arguments or {}).items()}


def record(*, client_id: str, tool: str, arguments: dict, result: str, error_code: str | None,
           duration_ms: float) -> dict:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "client_id": client_id,
        "tool": tool,
        "input_summary": summarise(arguments),
        "result": result,                 # "success" or "error"
        "error_code": error_code,         # None on success
        "duration_ms": round(duration_ms, 1),
    }
    line = json.dumps(entry, ensure_ascii=False, default=str)
    log.info(line)
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        log.exception("could not write invocation log")
    return entry


def read_entries(limit: int = 50) -> list[dict]:
    path = log_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]
