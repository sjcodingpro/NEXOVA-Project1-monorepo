"""Pure transform for weekly_office_performance_flow (no I/O, no database)."""
import itertools

import pandas as pd

OFFICE_CURRENCY = {"valencia": "EUR", "miami": "USD"}
COUNT_EVENTS = {
    "outbound_order_created": "kits_delivered_count",
    "stock_threshold_triggered": "shortage_events_count",
    "kit_cost_variance_detected": "cost_variance_events_count",
}
COUNT_COLUMNS = list(COUNT_EVENTS.values())
KEYS = ["office", "programme_id", "week_start"]
METRICS = ["total_material_cost"] + COUNT_COLUMNS
OUTPUT_COLUMNS = KEYS + METRICS + ["currency"]
TAG_FIELDS = ["office", "programme_id", "currency", "quantity", "unit_cost", "order_id"]


def _utc(value):
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _monday(value):
    ts = _utc(value).normalize()
    return ts - pd.Timedelta(days=ts.weekday())


def transform_weekly_kpis(raw, window_from, window_to, known_programmes=()):
    """raw: DataFrame with timestamp, event_type, tags (dict).
    Returns (result DataFrame, stats dict)."""
    stats = {
        "rows_extracted": int(len(raw)),
        "rows_rejected": 0,
        "duplicates_dropped": 0,
        "events_by_type": raw["event_type"].value_counts().to_dict() if len(raw) else {},
    }
    # 1. expand tags into columns
    tags = pd.DataFrame([t if isinstance(t, dict) else {} for t in raw["tags"]], index=raw.index)
    df = raw[["timestamp", "event_type"]].copy()
    for field in TAG_FIELDS:
        df[field] = tags[field] if field in tags.columns else None
    df["office"] = df["office"].astype("string").str.strip().str.lower()
    df["programme_id"] = df["programme_id"].astype("string").str.strip()
    df["ts"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["unit_cost"] = pd.to_numeric(df["unit_cost"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    # 2. validate and reject (counted, never silently dropped)
    inbound = df["event_type"] == "inbound_order_created"
    valid = (
        df["office"].isin(list(OFFICE_CURRENCY))
        & df["programme_id"].notna()
        & (df["programme_id"] != "")
        & (df["currency"] == df["office"].map(OFFICE_CURRENCY))
        & df["ts"].notna()
        & (~inbound | ((df["unit_cost"] >= 0) & (df["quantity"] > 0)))
    ).fillna(False).astype(bool)
    stats["rows_rejected"] = int((~valid).sum())
    good = df[valid].copy().sort_values("ts")

    # 3. week_start, 4. dedupe order events on (event_type, order_id)
    is_order = good["event_type"].isin(["inbound_order_created", "outbound_order_created"])
    dup = is_order & good["order_id"].notna() & good.duplicated(["event_type", "order_id"])
    stats["duplicates_dropped"] = int(dup.sum())
    good = good[~dup].copy()

    if good.empty:
        grouped = pd.DataFrame(columns=KEYS + METRICS)
    else:
        good["office"] = good["office"].astype(str)
        good["programme_id"] = good["programme_id"].astype(str)
        good["week_start"] = (
            good["ts"].dt.normalize() - pd.to_timedelta(good["ts"].dt.weekday, unit="D")
        ).dt.date
        # 5. inbound cost = unit_cost x quantity
        good["total_material_cost"] = (good["unit_cost"] * good["quantity"]).where(
            good["event_type"] == "inbound_order_created", 0.0
        )
        for event_type, column in COUNT_EVENTS.items():
            good[column] = (good["event_type"] == event_type).astype(int)
        # 6. group and aggregate
        grouped = good.groupby(KEYS, as_index=False)[METRICS].sum()

    # 7. zero-fill every office x programme x week in the window
    weeks, week, end = [], _monday(window_from), _utc(window_to)
    while week < end:
        weeks.append(week.date())
        week += pd.Timedelta(days=7)
    programmes = sorted(set(known_programmes) | set(grouped["programme_id"].astype(str)))
    base = pd.DataFrame(list(itertools.product(OFFICE_CURRENCY, programmes, weeks)), columns=KEYS)
    result = base.merge(grouped, on=KEYS, how="outer")
    result[METRICS] = result[METRICS].fillna(0)
    result[COUNT_COLUMNS] = result[COUNT_COLUMNS].astype(int)
    # 8. round costs to two decimals
    result["total_material_cost"] = result["total_material_cost"].astype(float).round(2)
    result["currency"] = result["office"].map(OFFICE_CURRENCY)
    result = result.sort_values(KEYS).reset_index(drop=True)
    return result[OUTPUT_COLUMNS], stats
