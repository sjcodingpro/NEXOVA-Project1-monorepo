"""DEV-55: async task queue. No Redis needed: Celery runs eagerly and Redis is faked."""
import os
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite://")  # app.database refuses to import without it

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def api(monkeypatch):
    from app.tasks.router import router as tasks_router
    from app.telemetry.router import router as telemetry_router

    app = FastAPI()
    app.include_router(telemetry_router)
    app.include_router(tasks_router)
    return TestClient(app)


def test_report_endpoint_returns_202_and_task_id_without_running_the_task(api, monkeypatch):
    calls = []
    import app.telemetry.router as telemetry_router

    def fake_delay(*args):
        calls.append(args)
        return SimpleNamespace(id="abc-123")

    monkeypatch.setattr(telemetry_router.build_report_task, "delay", fake_delay)
    resp = api.post("/telemetry/report", json={})
    assert resp.status_code == 202
    assert resp.json()["task_id"] == "abc-123"
    assert resp.json()["status"] == "pending"
    assert len(calls) == 1
    assert all(isinstance(a, (str, bool)) for a in calls[0])  # light message: strings only


def test_report_endpoint_rejects_inverted_window(api):
    resp = api.post("/telemetry/report", json={
        "start_date": "2026-10-10T00:00:00Z", "end_date": "2026-10-01T00:00:00Z",
    })
    assert resp.status_code == 400


def test_failure_simulation_is_off_by_default(api, monkeypatch):
    monkeypatch.delenv("ALLOW_TASK_FAILURE_DEMO", raising=False)
    assert api.post("/telemetry/report", json={"simulate_failure": True}).status_code == 403


def test_broker_down_returns_503(api, monkeypatch):
    import app.telemetry.router as telemetry_router

    def boom(*args):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(telemetry_router.build_report_task, "delay", boom)
    assert api.post("/telemetry/report", json={}).status_code == 503


@pytest.mark.parametrize("state,expected", [
    ("PENDING", "pending"), ("STARTED", "started"), ("RETRY", "started"),
    ("SUCCESS", "success"), ("FAILURE", "failure"),
])
def test_task_status_maps_celery_states(api, monkeypatch, state, expected):
    import app.tasks.router as tasks_router

    monkeypatch.setattr(
        tasks_router, "AsyncResult",
        lambda task_id, app=None: SimpleNamespace(state=state, result={"ok": 1} if state == "SUCCESS" else "boom"),
    )
    body = api.get("/tasks/some-id").json()
    assert body["status"] == expected
    if state == "SUCCESS":
        assert body["result"] == {"ok": 1}
    if state == "FAILURE":
        assert body["error"] == "boom"


def test_task_fails_three_times_then_lands_in_the_dlq(monkeypatch):
    import app.celery_app as celery_module
    import app.telemetry.tasks as tasks_module

    attempts = []
    stored = []
    dead_lettered = []

    def always_fails(start, end):
        attempts.append(1)
        raise RuntimeError("db exploded")

    fake_redis = SimpleNamespace(rpush=lambda key, value: stored.append((key, value)))
    monkeypatch.setattr(tasks_module, "build_report", always_fails)
    monkeypatch.setattr(celery_module.redis.Redis, "from_url", staticmethod(lambda url: fake_redis))
    monkeypatch.setattr(celery_module.record_failure, "apply_async",
                        lambda args=None, queue=None, **kw: dead_lettered.append((args, queue)))
    # .apply() runs the task in this process (no worker, no Redis) and still honors retries.
    result = tasks_module.build_report_task.apply(args=["2026-10-01T00:00:00+00:00", "2026-10-08T00:00:00+00:00"])

    assert result.failed()
    assert len(attempts) == 3                       # 1 run + 2 retries
    assert len(dead_lettered) == 1 and dead_lettered[0][1] == "dlq"
    record = dead_lettered[0][0][0]
    assert record["task_id"] == result.id
    assert record["attempt"] == 3
    assert "db exploded" in record["error"]
    assert stored and stored[0][0] == "dlq:records"
