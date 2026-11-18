"""Unit tests for the time-aware cross-validation used to evaluate the Nexova revenue forecast.

Checks that the folds preserve chronological order (no index from a later fold appears before
one from an earlier fold, nothing shuffled), that lag/rolling features cannot leak across a
fold boundary, that the 2024-2025 test years are never touched, and the minimum-window guard.

Run (repo root): uv run pytest tests/pipelines/test_model_evaluation.py -v
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from evaluate_sales_forecast import (  # noqa: E402
    FOLD_SIZE,
    N_SPLITS,
    fold_feature_frame,
    time_series_folds,
)
from train_sales_forecast import (  # noqa: E402
    DATA_PATH,
    FEATURES,
    MIN_TRAIN_FEATURE_MONTHS,
    TARGET,
    build_feature_frame,
    load_sales,
    split_train_test,
    train_model,
)


@pytest.fixture(scope="module")
def train_df():
    train, _ = split_train_test(load_sales(DATA_PATH))
    return train


@pytest.fixture(scope="module")
def feature_rows(train_df):
    return build_feature_frame(train_df)


@pytest.fixture(scope="module")
def folds(feature_rows):
    return time_series_folds(len(feature_rows))


# ---------------------------------------------------------------- chronological order
def test_at_least_five_folds_over_the_training_set(folds, feature_rows):
    assert len(folds) == N_SPLITS >= 5
    assert max(va[-1] for _, va in folds) == len(feature_rows) - 1  # ends at 2023-12


def test_indices_inside_each_fold_are_strictly_increasing(folds):
    for tr, va in folds:
        assert np.all(np.diff(tr) == 1), "training indices shuffled or skipped"
        assert np.all(np.diff(va) == 1), "validation indices shuffled or skipped"


def test_every_training_index_comes_before_every_validation_index(folds):
    for tr, va in folds:
        assert tr.max() < va.min()


def test_no_index_from_a_later_fold_appears_before_one_from_an_earlier_fold(folds):
    for (_, earlier), (_, later) in zip(folds, folds[1:]):
        assert earlier.max() < later.min()
        assert set(earlier).isdisjoint(later)


def test_training_window_expands_and_each_validation_fold_is_one_calendar_year(folds, feature_rows):
    sizes = [len(tr) for tr, _ in folds]
    assert sizes == sorted(sizes) and len(set(sizes)) == len(sizes)
    for _, va in folds:
        months = feature_rows["month"].iloc[va]
        assert len(va) == FOLD_SIZE
        assert months.dt.year.nunique() == 1 and list(months.dt.month) == list(range(1, 13))


def test_month_order_matches_index_order(folds, feature_rows):
    months = feature_rows["month"]
    for tr, va in folds:
        assert months.iloc[tr].is_monotonic_increasing and months.iloc[va].is_monotonic_increasing
        assert months.iloc[tr].max() < months.iloc[va].min()


# ---------------------------------------------------------------- leakage
def test_cross_validation_never_touches_the_test_years(train_df, feature_rows):
    assert train_df["month"].max() == pd.Timestamp("2023-12-01")
    assert feature_rows["month"].max() == pd.Timestamp("2023-12-01")


def test_fold_features_only_contain_months_up_to_the_validation_end(train_df, folds, feature_rows):
    for _, va in folds:
        val_end = feature_rows["month"].iloc[va[-1]]
        assert fold_feature_frame(train_df, val_end)["month"].max() == val_end


def test_rebuilding_per_fold_gives_the_same_features_as_the_full_series(train_df, folds, feature_rows):
    """Lags/rolling stats only look backwards, so truncating the future changes nothing."""
    for tr, va in folds:
        val_end = feature_rows["month"].iloc[va[-1]]
        per_fold = fold_feature_frame(train_df, val_end)
        idx = np.concatenate([tr, va])
        pd.testing.assert_frame_equal(per_fold.iloc[idx][FEATURES].reset_index(drop=True),
                                      feature_rows.iloc[idx][FEATURES].reset_index(drop=True))


def test_training_rows_do_not_change_when_the_validation_year_changes(train_df, folds, feature_rows):
    """If a training-row lag/rolling feature or target peeked into the validation fold,
    tripling the validation-year revenue would move it."""
    for tr, va in folds:
        val_months = set(feature_rows["month"].iloc[va])
        tampered = train_df.copy()
        tampered.loc[tampered["month"].isin(val_months), TARGET] *= 3.0
        before = build_feature_frame(train_df).iloc[tr]
        after = build_feature_frame(tampered).iloc[tr]
        cols = FEATURES + ["target_ratio", "_trailing_mean"]
        pd.testing.assert_frame_equal(before[cols], after[cols])


# ---------------------------------------------------------------- corrective action guard
def test_production_training_refuses_a_window_shorter_than_the_minimum(feature_rows):
    with pytest.raises(ValueError, match="Training window too short"):
        train_model(feature_rows.iloc[: MIN_TRAIN_FEATURE_MONTHS - 1])


def test_production_training_accepts_the_minimum_window(feature_rows):
    model = train_model(feature_rows.iloc[:MIN_TRAIN_FEATURE_MONTHS])
    assert len(model.estimators_) > 0
