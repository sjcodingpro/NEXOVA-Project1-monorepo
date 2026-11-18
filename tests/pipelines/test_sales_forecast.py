"""Unit tests for the Nexova sales-forecast split (8 training years / 2 test years) and leakage guards.

Uses the provided data/raw/nexova_sales.csv plus small in-memory/tmp fixtures. No network.

Run (repo root): uv run pytest tests/pipelines/test_sales_forecast.py -v
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from train_sales_forecast import (  # noqa: E402
    DATA_PATH,
    FEATURES,
    TARGET,
    build_feature_frame,
    load_sales,
    split_train_test,
)


@pytest.fixture(scope="module")
def sales():
    return load_sales(DATA_PATH)


@pytest.fixture(scope="module")
def split(sales):
    return split_train_test(sales)


def synthetic_sales(start="2016-01-01", years=10):
    months = pd.date_range(start, periods=12 * years, freq="MS")
    revenue = 700_000 * (1.04 ** (np.arange(len(months)) / 12))
    return pd.DataFrame({
        "month": months, "revenue_usd": revenue, "active_contracts": 200,
        "avg_contract_value_usd": revenue / 200, "business_line": "consolidated",
    })


# ------------------------------------------------------------------------- 8 / 2 rule
def test_provided_dataset_covers_ten_full_years_of_consolidated_rows(sales):
    assert len(sales) == 120
    assert sales["month"].min() == pd.Timestamp("2016-01-01")
    assert sales["month"].max() == pd.Timestamp("2025-12-01")
    assert (sales["business_line"] == "consolidated").all()


def test_training_set_is_exactly_the_first_eight_years(split):
    train, _ = split
    assert sorted(train["month"].dt.year.unique()) == list(range(2016, 2024))
    assert len(train) == 96
    assert train["month"].min() == pd.Timestamp("2016-01-01")
    assert train["month"].max() == pd.Timestamp("2023-12-01")


def test_test_set_is_exactly_the_two_most_recent_years(split):
    _, test = split
    assert sorted(test["month"].dt.year.unique()) == [2024, 2025]
    assert len(test) == 24
    assert test["month"].min() == pd.Timestamp("2024-01-01")
    assert test["month"].max() == pd.Timestamp("2025-12-01")


def test_no_overlap_and_strictly_chronological(sales, split):
    train, test = split
    assert set(train["month"]).isdisjoint(set(test["month"]))
    assert train["month"].max() < test["month"].min()
    assert len(train) + len(test) == len(sales)  # nothing dropped, nothing duplicated


def test_split_is_chronological_even_if_rows_arrive_shuffled():
    shuffled = synthetic_sales().sample(frac=1, random_state=0)
    train, test = split_train_test(shuffled)
    assert train["month"].dt.year.max() == 2023 and test["month"].dt.year.min() == 2024
    assert len(train) == 96 and len(test) == 24


def test_split_refuses_a_dataset_that_is_not_ten_years():
    with pytest.raises(ValueError, match="Expected 10 years"):
        split_train_test(synthetic_sales(years=9))


# ------------------------------------------------------------------------- leakage
def test_training_features_do_not_change_when_test_years_change(sales):
    """If any training-row feature or target depended on 2024-25, perturbing those years would move it."""
    baseline = build_feature_frame(sales)
    tampered = sales.copy()
    is_test = tampered["month"] >= "2024-01-01"
    tampered.loc[is_test, TARGET] *= 3.0
    altered = build_feature_frame(tampered)

    train_rows = baseline["month"] < "2024-01-01"
    cols = FEATURES + ["target_ratio", "_trailing_mean"]
    pd.testing.assert_frame_equal(baseline.loc[train_rows, cols], altered.loc[train_rows, cols])


def test_features_for_a_month_use_only_earlier_months(sales):
    """Changing month t's own revenue must not alter its features (only its target)."""
    idx = sales.index[sales["month"] == "2020-08-01"][0]
    tampered = sales.copy()
    tampered.loc[idx, TARGET] *= 2.0
    a = build_feature_frame(sales).set_index("month").loc["2020-08-01", FEATURES]
    b = build_feature_frame(tampered).set_index("month").loc["2020-08-01", FEATURES]
    pd.testing.assert_series_equal(a, b)


def test_same_month_contract_columns_are_not_model_features():
    # revenue_usd ~= active_contracts * avg_contract_value_usd -> using them would leak the target
    assert not {"active_contracts", "avg_contract_value_usd"} & set(FEATURES)


# ------------------------------------------------------------------------- data guards
def _write(tmp_path, df):
    path = tmp_path / "nexova_sales.csv"
    df.assign(month=df["month"].dt.strftime("%Y-%m-%d")).to_csv(path, index=False)
    return path


def test_load_rejects_missing_month(tmp_path):
    df = synthetic_sales()
    df = df[df["month"] != "2019-08-01"]
    with pytest.raises(ValueError, match="Missing months"):
        load_sales(_write(tmp_path, df))


def test_load_rejects_null_or_non_positive_revenue(tmp_path):
    df = synthetic_sales()
    df.loc[5, "revenue_usd"] = np.nan
    with pytest.raises(ValueError, match="Null revenue_usd"):
        load_sales(_write(tmp_path, df))
    df.loc[5, "revenue_usd"] = -1.0
    with pytest.raises(ValueError, match="positive"):
        load_sales(_write(tmp_path, df))
