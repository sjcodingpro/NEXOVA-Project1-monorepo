"""
Shared fixtures for the auth test suite.

Each test gets a fresh, isolated TinyDB file so tests never see each
other's data -- no shared state, no ordering dependencies.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


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
    from app.auth.security import create_access_token

    def _headers(user_id, role="user"):
        token = create_access_token(user_id, role)
        return {"Authorization": f"Bearer {token}"}

    return _headers
