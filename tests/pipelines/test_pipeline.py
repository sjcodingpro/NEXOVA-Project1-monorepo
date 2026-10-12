"""Unit tests for the transformation behind the Weekly Office & Programme Performance KPIs.

In-memory fixtures shaped like Nexova telemetry events (timestamp, event_type, tags).
No database, no Prefect runtime, no network.

Run: cd services/api && uv run python -m pytest ../../tests/pipelines/test_pipeline.py -v
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "data" / "process"))
from weekly_office_performance import transform_weekly_kpis  # noqa: E402

VALENCIA = {"office": "valencia", "programme_id": "b2b-sales", "currency": "EUR"}
MIAMI = {"office": "miami", "programme_id": "b2b-sales", "currency": "USD"}
WEEK = pd.Timestamp("2026-10-05", tz="UTC")  # a Monday
NEXT_WEEK = pd.Timestamp("2026-10-12", tz="UTC")
TUESDAY = "2026-10-06T10:00:00Z"


def event(timestamp, event_type, **tags):
    return {"timestamp": timestamp, "event_type": event_type, "tags": tags}


def run(events, window_to=NEXT_WEEK):
    raw = pd.DataFrame(events, columns=["timestamp", "event_type", "tags"])
    return transform_weekly_kpis(raw, WEEK, window_to, ["b2b-sales"])


def office_row(result, office):
    return result[result["office"] == office].iloc[0]


def test_material_cost_per_office_programme_sums_unit_cost_times_quantity():
    # Hand-calculated: Valencia 10 x 12.50 + 4 x 20.00 = 205.00 EUR; Miami 3 x 10.00 = 30.00 USD.
    result, _ = run([
        event(TUESDAY, "inbound_order_created", quantity=10, unit_cost=12.5, order_id="in-1", **VALENCIA),
        event(TUESDAY, "inbound_order_created", quantity=4, unit_cost=20, order_id="in-2", **VALENCIA),
        event(TUESDAY, "inbound_order_created", quantity=3, unit_cost=10, order_id="in-3", **MIAMI),
    ])
    valencia, miami = office_row(result, "valencia"), office_row(result, "miami")
    assert valencia["total_material_cost"] == 205.0 and valencia["currency"] == "EUR"
    assert miami["total_material_cost"] == 30.0 and miami["currency"] == "USD"  # never summed with EUR


def test_kits_delivered_counts_outbound_orders_per_office_programme_week():
    result, _ = run([
        event(TUESDAY, "outbound_order_created", order_id="out-1", **VALENCIA),
        event(TUESDAY, "outbound_order_created", order_id="out-2", **VALENCIA),
        event(TUESDAY, "outbound_order_created", order_id="out-3", **VALENCIA),
        event(TUESDAY, "outbound_order_created", order_id="out-4", **MIAMI),
    ])
    assert office_row(result, "valencia")["kits_delivered_count"] == 3
    assert office_row(result, "miami")["kits_delivered_count"] == 1


def test_shortage_frequency_counts_stock_threshold_triggered_events():
    result, _ = run([
        event(TUESDAY, "stock_threshold_triggered", **VALENCIA),
        event("2026-10-08T09:00:00Z", "stock_threshold_triggered", **VALENCIA),
    ])
    assert office_row(result, "valencia")["shortage_events_count"] == 2
    assert office_row(result, "miami")["shortage_events_count"] == 0


def test_cost_variance_frequency_counts_kit_cost_variance_detected_events():
    result, _ = run([event(TUESDAY, "kit_cost_variance_detected", **MIAMI)])
    assert office_row(result, "miami")["cost_variance_events_count"] == 1
    assert office_row(result, "valencia")["cost_variance_events_count"] == 0


def test_weekly_rollup_matches_context_definition_for_hand_calculated_input():
    # Mirrors the CONTEXT example: 50 units x 24.81 = 1240.50 EUR, 18 kits, 1 shortage, 0 variance.
    events = [event(TUESDAY, "inbound_order_created", quantity=50, unit_cost=24.81, order_id="in-1", **VALENCIA)]
    events += [event(TUESDAY, "outbound_order_created", order_id=f"out-{i}", **VALENCIA) for i in range(18)]
    events += [event(TUESDAY, "stock_threshold_triggered", **VALENCIA)]
    result, _ = run(events)
    valencia = office_row(result, "valencia")
    assert valencia["total_material_cost"] == 1240.5
    assert valencia["kits_delivered_count"] == 18
    assert valencia["shortage_events_count"] == 1
    assert valencia["cost_variance_events_count"] == 0
    assert valencia["currency"] == "EUR"


def test_events_are_grouped_by_iso_week_starting_monday_utc():
    window_to = pd.Timestamp("2026-10-19", tz="UTC")
    result, _ = run([
        event("2026-10-11T23:59:59Z", "outbound_order_created", order_id="sun", **VALENCIA),  # Sunday
        event("2026-10-12T00:00:00Z", "outbound_order_created", order_id="mon", **VALENCIA),  # next Monday
    ], window_to=window_to)
    kits_by_week = result[result["office"] == "valencia"].set_index("week_start")["kits_delivered_count"].to_dict()
    assert kits_by_week == {date(2026, 10, 5): 1, date(2026, 10, 12): 1}


def test_duplicate_order_events_are_counted_once():
    result, stats = run([
        event(TUESDAY, "outbound_order_created", order_id="out-1", **VALENCIA),
        event("2026-10-06T10:00:05Z", "outbound_order_created", order_id="out-1", **VALENCIA),
    ])
    assert office_row(result, "valencia")["kits_delivered_count"] == 1
    assert stats["duplicates_dropped"] == 1


def test_offices_and_programmes_without_events_are_zero_filled():
    result, stats = run([])
    assert len(result) == 2  # valencia and miami for b2b-sales, one week
    assert (result["total_material_cost"] == 0).all()
    assert (result["kits_delivered_count"] == 0).all()
    assert stats["rows_extracted"] == 0


def test_malformed_events_are_rejected_and_counted_never_silently_dropped():
    result, stats = run([
        event(TUESDAY, "outbound_order_created", office="paris", programme_id="b2b-sales", currency="EUR", order_id="a"),
        event(TUESDAY, "outbound_order_created", office="valencia", programme_id="b2b-sales", currency="USD", order_id="b"),
        event(TUESDAY, "inbound_order_created", quantity=2, order_id="c", **VALENCIA),  # missing unit_cost
        event(TUESDAY, "inbound_order_created", quantity=0, unit_cost=5, order_id="d", **VALENCIA),  # zero quantity
        event("not-a-date", "outbound_order_created", order_id="e", **VALENCIA),  # unparseable timestamp
        {"timestamp": TUESDAY, "event_type": "outbound_order_created", "tags": None},  # no tags at all
        event(TUESDAY, "outbound_order_created", order_id="ok", **VALENCIA),  # the only valid event
    ])
    assert stats["rows_extracted"] == 7
    assert stats["rows_rejected"] == 6
    assert office_row(result, "valencia")["kits_delivered_count"] == 1


def test_total_material_cost_is_rounded_to_two_decimals():
    result, _ = run([event(TUESDAY, "inbound_order_created", quantity=3, unit_cost=33.333, order_id="in-1", **VALENCIA)])
    assert office_row(result, "valencia")["total_material_cost"] == 100.0
