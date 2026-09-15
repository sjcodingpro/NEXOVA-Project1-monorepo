"""
Shared TinyDB instance for the Nexova API.

A single JSON-backed database file, shared across all domains. Each
domain gets its own TinyDB "table" (a logical namespace within the
same file) rather than a separate database file.
"""

import threading
from pathlib import Path

from tinydb import TinyDB

DB_PATH = Path(__file__).resolve().parent.parent / "db.json"

try:
    db = TinyDB(DB_PATH)
    db.tables()  # TinyDB reads the file lazily on first access, not at
    # construction -- without this call, a corrupt/unreadable db.json
    # would pass this guard silently and only fail on the app's first
    # real request instead of at startup.
except Exception as exc:
    # Runs at import time -- a missing/unreadable/corrupt db.json would
    # otherwise crash the app with a raw traceback. The original exception
    # is still chained (visible in server logs via `from exc`) for
    # debugging; this message is what actually explains the problem.
    raise RuntimeError(
        f"Could not open the database file at {DB_PATH}. It may be "
        "missing, unreadable, or not valid JSON. Fix or remove the file "
        "and restart the app."
    ) from exc

# TinyDB's JSONStorage does a synchronous read-modify-write of the whole
# file on every write call. FastAPI can run multiple sync (`def`, not
# `async def`) route handlers concurrently in a threadpool, so two writes
# landing at the same moment can interleave and truncate the file. Every
# service-layer function that calls table.insert/update/remove must wrap
# that call in `with db_lock:` -- reads don't need it.
db_lock = threading.Lock()


def get_suppliers_table():
    return db.table("suppliers")


def get_users_table():
    return db.table("users")


def get_profiles_table():
    return db.table("profiles")


def get_incidents_table():
    return db.table("incidents")


def check_db_readable() -> bool:
    """Used by the /health endpoint. A cheap read-only check that the
    database file is actually openable and queryable right now, not just
    that it was openable at import time."""
    try:
        db.tables()
        return True
    except Exception:
        return False
