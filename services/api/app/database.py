"""
Dual database configuration: TinyDB (existing, auth/users/profiles/
suppliers) and Supabase/PostgreSQL via SQLModel (new, inventory).

Both connections are initialized here per the milestone's instruction
to extend the existing database.py rather than create a parallel one.
The TinyDB half below is byte-for-byte the existing setup -- untouched.
"""

import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine
from tinydb import TinyDB

# Loaded here, not just in main.py -- anything that imports this module
# directly (pytest collecting a test file, the seed script, a future
# script) must not depend on main.py having already run load_dotenv()
# first. python-dotenv is safe to call more than once; it won't
# override a variable that's already set in the real environment.
load_dotenv()

# --- TinyDB (existing, unchanged) -------------------------------------------

DB_PATH = Path(__file__).resolve().parent.parent / "db.json"
db = TinyDB(DB_PATH)
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
    """Used by the /health endpoint. TinyDB reads lazily, so merely
    having constructed TinyDB(DB_PATH) earlier doesn't guarantee the
    file is actually readable -- db.tables() forces the read."""
    try:
        db.tables()
        return True
    except Exception:
        return False


# --- Supabase / PostgreSQL via SQLModel (new) --------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    # Fails loudly at import time -- the inventory router can't function
    # at all without this, so there's no meaningful "degraded" state to
    # fall back to (unlike, say, an optional email provider).
    raise RuntimeError(
        "DATABASE_URL is not set. Add your Supabase connection string "
        "(Transaction pooler, URI type) to .env."
    )

engine = create_engine(DATABASE_URL, echo=False)


def init_inventory_db() -> None:
    """Creates the inventory tables in Supabase if they don't exist yet.
    Called once at app startup -- see main.py."""
    SQLModel.metadata.create_all(engine)


def get_db():
    """Per-request SQLModel session, injected via Depends(). No global
    session variable -- each request gets its own, and it's always
    closed via the `with` block regardless of how the request ends."""
    with Session(engine) as session:
        yield session
