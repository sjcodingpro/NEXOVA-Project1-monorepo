"""
Shared TinyDB instance for the Nexova API.

A single JSON-backed database file, shared across all domains. Each
domain gets its own TinyDB "table" (a logical namespace within the
same file) rather than a separate database file.
"""

from pathlib import Path
from tinydb import TinyDB

DB_PATH = Path(__file__).resolve().parent.parent / "db.json"

db = TinyDB(DB_PATH)


def get_suppliers_table():
    return db.table("suppliers")
