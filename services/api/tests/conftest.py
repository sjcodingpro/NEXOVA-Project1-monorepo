"""
Shared fixtures for the full test suite -- both the AUTH-088 auth tests
and the inventory (Asset/AssetEntry/AssetExit) tests. Each test gets
fresh, isolated TinyDB and SQLite-standing-in-for-Supabase databases so
tests never see each other's data, and the two suites' fixtures are
named distinctly (client vs inventory_client, etc.) so adding one never
silently breaks the other.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine
from fastapi import FastAPI
from fastapi.testclient import TestClient


# --- TinyDB (auth/users) -- unchanged from AUTH-088 -------------------------

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Points app.database at a fresh TinyDB file for this test only."""
    db_file = tmp_path / "test_db.json"
    import app.database as database_module
    from tinydb import TinyDB

    test_db = TinyDB(db_file)
    monkeypatch.setattr(database_module, "db", test_db)
    yield test_db
    test_db.close()


@pytest.fixture
def client(isolated_db):
    """Auth-only FastAPI app -- used by the AUTH-088 suite."""
    from app.auth.router import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)
    return TestClient(app)


@pytest.fixture
def make_user(isolated_db):
    """Creates a user directly in the DB (bypassing the API) with a
    known plaintext password, and returns (user_id, email, password)."""
    from app.auth.security import hash_password
    from app.database import get_users_table
    from datetime import datetime, timezone

    def _make(email="jane@example.com", password="correcthorse123", is_active=True, role="user"):
        table = get_users_table()
        now = datetime.now(timezone.utc).isoformat()
        user_id = table.insert({
            "email": email,
            "hashed_password": hash_password(password),
            "is_active": is_active,
            "role": role,
            "created_at": now,
            "password_changed_at": now,
        })
        return user_id, email, password

    return _make


@pytest.fixture
def auth_headers():
    """Factory: auth_headers(user_id, role="user") -> Authorization
    header dict. Shared by both suites -- inventory tests create a user
    via make_user, then a token via this same fixture."""
    from app.auth.security import create_access_token

    def _headers(user_id, role="user"):
        token = create_access_token(user_id, role)
        return {"Authorization": f"Bearer {token}"}

    return _headers


# --- SQLite standing in for Supabase -- new, for the inventory suite -------

@pytest.fixture
def inventory_engine(tmp_path):
    """A fresh SQLite database per test, with foreign keys enabled --
    SQLite doesn't enforce FKs by default, so this makes it behave like
    Postgres does out of the box. That's what makes
    test_inventory.py's FK enforcement test meaningful."""
    db_file = tmp_path / "test_inventory.db"
    eng = create_engine(f"sqlite:///{db_file}")

    @event.listens_for(eng, "connect")
    def _enable_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from app.inventory.models import Asset, AssetEntry, AssetExit  # noqa: F401
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(inventory_engine):
    with Session(inventory_engine) as session:
        yield session


@pytest.fixture
def inventory_client(inventory_engine, isolated_db, monkeypatch):
    """FastAPI app with both auth (so get_current_user resolves against
    the isolated TinyDB) and inventory routers. app.database.engine is
    monkeypatched to the isolated SQLite stand-in, so no test here ever
    touches the real Supabase database."""
    import app.database as database_module
    monkeypatch.setattr(database_module, "engine", inventory_engine)

    from app.auth.router import router as auth_router
    from app.inventory.router import router as inventory_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(inventory_router)
    return TestClient(app)
