"""Database helpers for weekly_office_performance_flow.

Reads telemetry_events (read-only). Writes only to the reporting schema.
"""
import json
import subprocess
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (
    Column, Date, DateTime, Integer, MetaData, Numeric, Table, Text,
    create_engine, func, literal_column, or_, text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "services" / "api" / ".env")
load_dotenv(ROOT / ".env")

STALE_RUN_MINUTES = 30
EVENT_TYPES = (
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "kit_cost_variance_detected",
)

_meta = MetaData(schema="reporting")
weekly = Table(
    "weekly_office_program_performance", _meta,
    Column("office", Text), Column("programme_id", Text), Column("week_start", Date),
    Column("total_material_cost", Numeric), Column("kits_delivered_count", Integer),
    Column("shortage_events_count", Integer), Column("cost_variance_events_count", Integer),
    Column("currency", Text), Column("computed_at", DateTime(timezone=True)),
)


@lru_cache(maxsize=1)
def get_engine():
    import os
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (expected in services/api/.env)")
    return create_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def pipeline_version() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


_INSERT_RUN = text(
    "insert into reporting.pipeline_runs (run_id, trigger, window_from, window_to, status,"
    " checkpoint, error_summary, pipeline_version, finished_at)"
    " values (cast(:run_id as uuid), :trigger, :window_from, :window_to, :status,"
    " 'started', :error_summary, :version, :finished_at)"
)


def get_running_run_id():
    with get_engine().connect() as conn:
        rid = conn.execute(text(
            "select run_id from reporting.pipeline_runs where status = 'running' limit 1"
        )).scalar()
    return str(rid) if rid else None


def begin_run(run_id, trigger, window_from, window_to):
    """Insert a 'running' row. The unique index allows only one running row, so an
    overlapping run is recorded as 'skipped' instead (single-run guard)."""
    eng = get_engine()
    with eng.begin() as conn:  # stale-run cleanup: a crashed run must not block forever
        conn.execute(text(
            "update reporting.pipeline_runs set status = 'failed', finished_at = now(),"
            " error_summary = 'stale run: exceeded timeout'"
            " where status = 'running' and started_at < now() - (:m * interval '1 minute')"
        ), {"m": STALE_RUN_MINUTES})
    base = {"run_id": run_id, "trigger": trigger, "window_from": window_from,
            "window_to": window_to, "version": pipeline_version()}
    try:
        with eng.begin() as conn:
            conn.execute(_INSERT_RUN, {**base, "status": "running",
                                       "error_summary": None, "finished_at": None})
        return {"run_id": run_id, "status": "running"}
    except IntegrityError:
        other = get_running_run_id()
        with eng.begin() as conn:
            conn.execute(_INSERT_RUN, {**base, "status": "skipped",
                                       "error_summary": f"overlapping run: {other}",
                                       "finished_at": func.now()})
        return {"run_id": run_id, "status": "skipped", "running_run_id": other}


def set_checkpoint(run_id, checkpoint):
    with get_engine().begin() as conn:
        conn.execute(text(
            "update reporting.pipeline_runs set checkpoint = :c where run_id = cast(:r as uuid)"
        ), {"c": checkpoint, "r": run_id})


def finish_run(run_id, status, checkpoint, stats, error_summary=None):
    events = stats.get("events_by_type")
    with get_engine().begin() as conn:
        conn.execute(text(
            "update reporting.pipeline_runs set finished_at = now(), status = :status,"
            " checkpoint = :checkpoint, rows_extracted = :rows_extracted,"
            " rows_rejected = :rows_rejected, rows_loaded = :rows_loaded,"
            " rows_updated = :rows_updated, events_by_type = cast(:events as jsonb),"
            " error_summary = :error_summary where run_id = cast(:run_id as uuid)"
        ), {"status": status, "checkpoint": checkpoint, "run_id": run_id,
            "rows_extracted": stats.get("rows_extracted"),
            "rows_rejected": stats.get("rows_rejected"),
            "rows_loaded": stats.get("rows_loaded"),
            "rows_updated": stats.get("rows_updated"),
            "events": json.dumps(events) if events is not None else None,
            "error_summary": error_summary})


def read_telemetry_events(window_from, window_to):
    """Extract: read-only query over the four mandatory event types."""
    query = text(
        'select "timestamp", event_type, tags from public.telemetry_events'
        ' where "timestamp" >= :a and "timestamp" < :b'
        " and event_type in ('inbound_order_created', 'outbound_order_created',"
        " 'stock_threshold_triggered', 'kit_cost_variance_detected')"
    )
    with get_engine().connect() as conn:
        rows = conn.execute(query, {"a": window_from, "b": window_to}).all()
    return pd.DataFrame([tuple(r) for r in rows], columns=["timestamp", "event_type", "tags"])


def upsert_weekly(records):
    """Idempotent load: upsert on the unique key (office, programme_id, week_start).
    Rows whose values are unchanged are not touched, so re-running over the same
    data leaves the table identical. Returns (inserted, updated)."""
    if not records:
        return 0, 0
    stmt = pg_insert(weekly)
    changed = or_(*[
        getattr(weekly.c, col).is_distinct_from(getattr(stmt.excluded, col))
        for col in ("total_material_cost", "kits_delivered_count", "shortage_events_count",
                    "cost_variance_events_count", "currency")
    ])
    stmt = stmt.on_conflict_do_update(
        index_elements=["office", "programme_id", "week_start"],
        set_={
            "total_material_cost": stmt.excluded.total_material_cost,
            "kits_delivered_count": stmt.excluded.kits_delivered_count,
            "shortage_events_count": stmt.excluded.shortage_events_count,
            "cost_variance_events_count": stmt.excluded.cost_variance_events_count,
            "currency": stmt.excluded.currency,
            "computed_at": func.now(),
        },
        where=changed,
    ).returning(literal_column("(xmax = 0)").label("inserted"))
    with get_engine().begin() as conn:  # one transaction: all rows or none
        flags = [r[0] for r in conn.execute(stmt, records)]
    return flags.count(True), flags.count(False)


def _iso(value):
    return value.isoformat() if value is not None else None


def get_latest_pipeline_run():
    """Status and metadata of the most recent run (None if there are no runs yet)."""
    with get_engine().connect() as conn:
        row = conn.execute(text(
            "select * from reporting.pipeline_runs order by started_at desc limit 1"
        )).mappings().first()
    if row is None:
        return None
    return {
        "run_id": str(row["run_id"]), "trigger": row["trigger"], "status": row["status"],
        "checkpoint": row["checkpoint"], "started_at": _iso(row["started_at"]),
        "finished_at": _iso(row["finished_at"]), "records_processed": row["rows_loaded"],
        "rows_extracted": row["rows_extracted"], "rows_rejected": row["rows_rejected"],
        "rows_updated": row["rows_updated"], "window_from": _iso(row["window_from"]),
        "window_to": _iso(row["window_to"]), "error_summary": row["error_summary"],
        "pipeline_version": row["pipeline_version"],
    }


def get_weekly_office_program_performance(week_start=None):
    """KPI rows for one week (defaults to the most recent computed week)."""
    if isinstance(week_start, str):
        week_start = date.fromisoformat(week_start)
    with get_engine().connect() as conn:
        if week_start is None:
            week_start = conn.execute(text(
                "select max(week_start) from reporting.weekly_office_program_performance"
            )).scalar()
        if week_start is None:
            return {"week_start": None, "entries": []}
        rows = conn.execute(text(
            "select office, programme_id, total_material_cost, kits_delivered_count,"
            " shortage_events_count, cost_variance_events_count, currency"
            " from reporting.weekly_office_program_performance"
            " where week_start = :w order by office, programme_id"
        ), {"w": week_start}).mappings().all()
    entries = [{**dict(r), "total_material_cost": float(r["total_material_cost"])} for r in rows]
    return {"week_start": week_start.isoformat(), "entries": entries}
