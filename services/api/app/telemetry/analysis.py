"""Technical report metrics computed from telemetry_events.

Every metric function follows the same formula, in this order:
load (SQL) -> refine (Pandas) -> convert types -> group -> aggregate

Rules: no loops (Pandas operations only); every function is side-effect
free (same parameters and same data give the same result); the date window
is received from the caller and applied once, in SQL.
"""

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import bindparam, text

from app.database import engine


def _load(start_date: datetime, end_date: datetime, event_types: list[str] | None = None) -> pd.DataFrame:
    """Load only the rows a metric needs. Window: inclusive start, exclusive end (UTC)."""
    sql = (
        'select "timestamp", event_type, level, tags from telemetry_events '
        'where "timestamp" >= :start and "timestamp" < :end'
    )
    params: dict[str, Any] = {"start": start_date, "end": end_date}
    if event_types:
        statement = text(sql + " and event_type in :types").bindparams(bindparam("types", expanding=True))
        params["types"] = event_types
    else:
        statement = text(sql)
    return pd.read_sql(statement, engine, params=params)


def _convert_types(df: pd.DataFrame) -> pd.DataFrame:
    """Timestamps become real datetimes (UTC) BEFORE any grouping."""
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["date"] = df["timestamp"].dt.date.astype(str)
    return df


def events_per_day(start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
    """How much telemetry is the system producing per day?"""
    df = _convert_types(_load(start_date, end_date))
    return df.groupby("date").agg(events=("event_type", "count")).reset_index().to_dict(orient="records")


def error_rate_by_day(start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
    """What share of each day's events are errors (and how many are warnings)?"""
    df = _convert_types(_load(start_date, end_date))
    df["is_error"] = df["level"].eq("error")
    df["is_warn"] = df["level"].eq("warn")
    daily = (
        df.groupby("date")
        .agg(
            total_events=("event_type", "count"),
            error_events=("is_error", "sum"),
            warn_events=("is_warn", "sum"),
        )
        .reset_index()
    )
    daily["error_rate"] = (daily["error_events"] / daily["total_events"]).round(4)
    return daily.to_dict(orient="records")


def error_rate_by_type(start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
    """Which event types carry the errors and warnings?"""
    df = _convert_types(_load(start_date, end_date))
    df["is_error"] = df["level"].eq("error")
    df["is_warn"] = df["level"].eq("warn")
    by_type = (
        df.groupby("event_type")
        .agg(
            total_events=("event_type", "count"),
            error_events=("is_error", "sum"),
            warn_events=("is_warn", "sum"),
        )
        .reset_index()
    )
    by_type["error_rate"] = (by_type["error_events"] / by_type["total_events"]).round(4)
    return by_type.sort_values(["error_rate", "total_events"], ascending=False).to_dict(orient="records")


def event_type_distribution(start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
    """Which event types dominate the traffic?"""
    df = _convert_types(_load(start_date, end_date))
    counts = df.groupby("event_type").agg(events=("event_type", "count")).reset_index()
    counts["share"] = (counts["events"] / counts["events"].sum()).round(4)
    return counts.sort_values("events", ascending=False).to_dict(orient="records")


def api_latency_by_endpoint(start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
    """Which endpoints are slow, day by day? (latency events are sampled at 10%, 100% of 5xx)"""
    df = _convert_types(_load(start_date, end_date, ["api_latency_recorded"]))
    if df.empty:
        return []
    tags = pd.json_normalize(df["tags"].tolist())
    df = pd.concat([df.reset_index(drop=True), tags], axis=1)
    df["duration_ms"] = pd.to_numeric(df["duration_ms"], errors="coerce")
    df = df.dropna(subset=["endpoint", "duration_ms"])
    result = (
        df.groupby(["date", "endpoint"])
        .agg(
            sampled_requests=("duration_ms", "count"),
            avg_ms=("duration_ms", "mean"),
            max_ms=("duration_ms", "max"),
        )
        .round(1)
        .reset_index()
    )
    return result.sort_values(["date", "avg_ms"], ascending=[True, False]).to_dict(orient="records")


def build_report(start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """Run the whole pipeline for one period. The caller resolves the window once."""
    return {
        "period": {"from": start_date.isoformat(), "to": end_date.isoformat()},
        "metrics": {
            "events_per_day": events_per_day(start_date, end_date),
            "error_rate_by_day": error_rate_by_day(start_date, end_date),
            "error_rate_by_type": error_rate_by_type(start_date, end_date),
            "event_type_distribution": event_type_distribution(start_date, end_date),
            "api_latency_by_endpoint": api_latency_by_endpoint(start_date, end_date),
        },
    }
