"""Nexova monthly revenue forecast — Random Forest regression on the consolidated series.

Ticket: Finance wants to know whether Nexova's monthly revenue can be predicted with an
acceptable error before committing to an executive dashboard (see CONTEXT.md and
data/raw/nexova_sales.csv, 2016-01 .. 2025-12, `consolidated` rows).

Run (from the repo root):
    uv run python scripts/train_sales_forecast.py

Outputs (data/eval/sales_forecast/):
    metrics.json           all test-set metrics (MSE, PSI, Gini, R², plus RMSE %, MAPE, band coverage)
    test_predictions.csv   month, actual, forecast, P5/P95 band, one-step-ahead forecast
    forecast_vs_actual.png the visualization for the 2 test years (2024-2025)

-----------------------------------------------------------------------------------------
WHY RANDOM FOREST (and not XGBoost) — the criteria the ticket asks us to document
-----------------------------------------------------------------------------------------
1. Data size: after the 24-month warm-up the lag/rolling features need, the training set
   is 72 monthly rows (2018-2023). Boosting fits residuals sequentially and on 72 rows it
   overfits quickly unless learning rate, depth, n_estimators and regularisation are tuned
   together; bagging (averaging many de-correlated trees) is robust to that out of the box.
2. Explainability: the stakeholders are Laura (CEO), Marcos (Sales) and Finance. "300 trees
   each vote on how this month compares to the last 12 months, and we average the votes" is
   explainable in one sentence, and the impurity-based feature importances are reported.
3. Tuning time: this is a feasibility check, not a production model. Random Forest gives a
   sound result with near-default hyper-parameters; we avoid tuning on the test years.
4. Variability range for free: each tree produces its own forecast, so the spread across
   trees gives the variability band the ticket requires without a second model.
Known Random Forest weakness — trees cannot extrapolate above the highest value seen in
training, and Nexova's revenue grows every year (2024-25 exceed the 2016-23 max). We avoid it
by predicting a scale-free *ratio* (revenue / trailing-12-month mean) instead of USD, then
multiplying back by the known trailing mean. The same trick handles scaling (see below).

-----------------------------------------------------------------------------------------
LEAKAGE GUARDS
-----------------------------------------------------------------------------------------
* `active_contracts` x `avg_contract_value_usd` reproduces `revenue_usd` within 0.3%, so
  same-month values of those columns would leak the target. They are NOT used as features.
* Every feature for month t is built only from months < t (`features_from_history`).
* The model is fitted on 2016-2023 rows only. The headline test forecast is *recursive*:
  standing at 2023-12, it forecasts all 24 test months feeding its own predictions back as
  lags — it never sees a 2024-2025 actual. A one-step-ahead variant (forecast next month
  with the actuals known up to last month — how a monthly rolling forecast would run) is
  reported as a secondary number.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = REPO_ROOT / "data" / "raw" / "nexova_sales.csv"
OUTPUT_DIR = REPO_ROOT / "data" / "eval" / "sales_forecast"

RANDOM_STATE = 42  # same seed the dataset was generated with; fixed for reproducibility
EXPECTED_COLUMNS = ["month", "revenue_usd", "active_contracts", "avg_contract_value_usd", "business_line"]
MAIN_BUSINESS_LINE = "consolidated"
TARGET = "revenue_usd"
TRAIN_YEARS, TEST_YEARS = 8, 2
WARMUP_MONTHS = 24  # trailing-12 mean + its value 12 months earlier (YoY growth feature)
BAND_QUANTILES = (5, 95)

# Seasonality documented in CONTEXT/briefing, as ratio to the annual average. Used to
# validate that the data and the engineered features reflect the expected pattern.
AUGUST_DROP_RANGE = (0.75, 0.85)  # 15-25% drop (Spanish summer vacation stalls hiring)
JAN_FEB_RISE_RANGE = (1.15, 1.20)  # 15-20% rise (budget renewals / new hiring plans)
OTHER_MONTHS_BAND = 0.05  # +-5% around trend
GROWTH_RANGE = (0.01, 0.07)  # X +- Y = 4% +- 3%, always positive
VALIDATION_TOLERANCE = 0.02  # monthly noise on top of the stated pattern

FEATURES = [
    "month_num",
    "month_sin",
    "month_cos",
    "is_august",
    "is_jan_feb",
    "lag_1_ratio",
    "lag_2_ratio",
    "lag_12_ratio",
    "rolling_3_mean_ratio",
    "rolling_12_cv",
    "trailing_yoy_growth",
]


# --------------------------------------------------------------------------- data loading
def load_sales(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load the CSV, keep the `consolidated` rows and enforce the CONTEXT.md constraints.

    Null handling: fully empty lines are dropped and text is stripped. Any remaining null or
    non-positive `revenue_usd`, or any missing month in the range, raises — imputing would
    silently alter the August / Jan-Feb seasonality the model has to learn, so we fail loudly
    and let a human fix the source file instead.
    """
    df = pd.read_csv(path, skip_blank_lines=True)
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"nexova_sales.csv is missing columns {missing_cols}")

    df = df.dropna(how="all")
    df["business_line"] = df["business_line"].astype("string").str.strip().str.lower()
    df = df[df["business_line"] == MAIN_BUSINESS_LINE].copy()

    df["month"] = pd.to_datetime(df["month"], format="%Y-%m-%d", errors="coerce")
    for col in ["revenue_usd", "active_contracts", "avg_contract_value_usd"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df["month"].isna().any():
        raise ValueError("Unparseable `month` values in consolidated rows")
    if df["month"].dt.day.ne(1).any():
        raise ValueError("`month` must be the first day of the month (YYYY-MM-01)")
    if df["month"].duplicated().any():
        raise ValueError("Duplicate consolidated rows for the same month")
    if df[TARGET].isna().any():
        bad = df.loc[df[TARGET].isna(), "month"].dt.strftime("%Y-%m").tolist()
        raise ValueError(f"Null revenue_usd for months {bad}")
    if (df[TARGET] <= 0).any():
        raise ValueError("All revenue_usd values must be positive (CONTEXT.md constraint)")

    df = df.sort_values("month").reset_index(drop=True)
    full_range = pd.date_range(df["month"].min(), df["month"].max(), freq="MS")
    missing = full_range.difference(df["month"])
    if len(missing):
        raise ValueError(f"Missing months: {[m.strftime('%Y-%m') for m in missing]}")
    return df


def split_train_test(
    df: pd.DataFrame, train_years: int = TRAIN_YEARS, test_years: int = TEST_YEARS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split: first `train_years` calendar years -> train, last `test_years` -> test."""
    years = sorted(df["month"].dt.year.unique())
    if len(years) != train_years + test_years:
        raise ValueError(f"Expected {train_years + test_years} years of data, found {len(years)}: {years}")
    cutoff_year = years[train_years - 1]
    is_train = df["month"].dt.year <= cutoff_year
    return df[is_train].copy(), df[~is_train].copy()


def validate_patterns(df: pd.DataFrame) -> dict:
    """Check the series reflects the growth/seasonality described in CONTEXT.md.

    Returns a summary dict; raises if a pattern is clearly absent (which would mean the file
    is not the provided dataset or was altered).
    """
    s = df.set_index("month")[TARGET]
    annual_mean = s.groupby(s.index.year).mean()
    growth = annual_mean.pct_change().dropna()
    index = s / s.index.year.map(annual_mean).values
    months = index.index.month

    aug, jan_feb = index[months == 8], index[np.isin(months, [1, 2])]
    other = index[~np.isin(months, [1, 2, 8])]
    tol = VALIDATION_TOLERANCE
    checks = {
        "august_index_range": [round(aug.min(), 3), round(aug.max(), 3)],
        "jan_feb_index_range": [round(jan_feb.min(), 3), round(jan_feb.max(), 3)],
        "other_months_index_range": [round(other.min(), 3), round(other.max(), 3)],
        "annual_growth_pct": {int(y): round(g * 100, 2) for y, g in growth.items()},
    }
    problems = []
    if aug.min() < AUGUST_DROP_RANGE[0] - tol or aug.max() > AUGUST_DROP_RANGE[1] + tol:
        problems.append("August drop outside 15-25%")
    if jan_feb.min() < JAN_FEB_RISE_RANGE[0] - tol or jan_feb.max() > JAN_FEB_RISE_RANGE[1] + tol:
        problems.append("Jan-Feb rise outside 15-20%")
    # "Other months +-5% around trend": the annual mean is pulled up by Jan-Feb, so the
    # other months sit slightly below 1.0; check their spread rather than their centre.
    if other.max() - other.min() > 2 * OTHER_MONTHS_BAND + 2 * tol:
        problems.append("Non-seasonal months fluctuate more than +-5%")
    if (growth <= 0).any() or growth.max() > GROWTH_RANGE[1] + tol:
        problems.append("Annual growth not always positive / within 1-7%")
    if problems:
        raise ValueError(f"Dataset does not match CONTEXT.md patterns: {problems}")
    return checks


# ------------------------------------------------------------------- feature engineering
def features_from_history(history: np.ndarray, month: int) -> dict:
    """Features for the month right after `history` (ordered revenue, oldest first).

    Causal by construction: only receives the past. All revenue-magnitude features are
    divided by the trailing-12-month mean, which (a) is the scaling step — it removes the
    USD magnitude that grows ~4%/yr so 2016 and 2025 months are comparable, and (b) lets the
    trees work on a stationary ratio. Calendar features are already bounded.
    """
    if len(history) < WARMUP_MONTHS:
        raise ValueError(f"Need >= {WARMUP_MONTHS} months of history, got {len(history)}")
    last_12 = history[-12:]
    trailing_mean = last_12.mean()
    prev_trailing_mean = history[-24:-12].mean()
    return {
        "month_num": month,
        "month_sin": np.sin(2 * np.pi * month / 12),
        "month_cos": np.cos(2 * np.pi * month / 12),
        "is_august": int(month == 8),
        "is_jan_feb": int(month in (1, 2)),
        "lag_1_ratio": history[-1] / trailing_mean,
        "lag_2_ratio": history[-2] / trailing_mean,
        "lag_12_ratio": history[-12] / trailing_mean,  # same month last year
        "rolling_3_mean_ratio": history[-3:].mean() / trailing_mean,
        "rolling_12_cv": last_12.std() / trailing_mean,
        # Growth alternates high/low each year (CONTEXT.md); last year's growth is a causal hint.
        "trailing_yoy_growth": trailing_mean / prev_trailing_mean - 1,
        "_trailing_mean": trailing_mean,  # scale used to convert the ratio back to USD
    }


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """One row per month with >= WARMUP_MONTHS of history; target is revenue / trailing mean."""
    values = df[TARGET].to_numpy(dtype=float)
    rows = []
    for i in range(WARMUP_MONTHS, len(df)):
        month = df["month"].iloc[i]
        feats = features_from_history(values[:i], month.month)
        feats["month"] = month
        feats[TARGET] = values[i]
        feats["target_ratio"] = values[i] / feats["_trailing_mean"]
        rows.append(feats)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------- model
def train_model(train_features: pd.DataFrame) -> RandomForestRegressor:
    model = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=2,  # small smoothing for 72 rows; no tuning on the test years
        max_features=0.6,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(train_features[FEATURES], train_features["target_ratio"])
    return model


def _predict_tree_ratios(model: RandomForestRegressor, feats: dict) -> np.ndarray:
    x = pd.DataFrame([{k: feats[k] for k in FEATURES}]).to_numpy()
    return np.array([tree.predict(x)[0] for tree in model.estimators_])


def recursive_forecast(model, history: np.ndarray, months: list[pd.Timestamp]) -> np.ndarray:
    """Forecast `months` in order using only `history`; each tree runs its own path.

    Returns array (n_trees, n_months) in USD. Running every tree recursively on its own
    predictions lets uncertainty compound over the horizon, so the band widens honestly.
    """
    n_trees = len(model.estimators_)
    paths = np.tile(np.asarray(history, dtype=float), (n_trees, 1))
    out = np.empty((n_trees, len(months)))
    for j, month in enumerate(months):
        for t, tree in enumerate(model.estimators_):
            feats = features_from_history(paths[t], month.month)
            x = np.array([[feats[k] for k in FEATURES]])
            out[t, j] = tree.predict(x)[0] * feats["_trailing_mean"]
        paths = np.column_stack([paths, out[:, j]])
    return out


def one_step_forecast(model, df: pd.DataFrame, start_idx: int) -> np.ndarray:
    """Forecast each month from start_idx on using the *actual* history up to the month before."""
    values = df[TARGET].to_numpy(dtype=float)
    preds = []
    for i in range(start_idx, len(values)):
        feats = features_from_history(values[:i], df["month"].iloc[i].month)
        preds.append(_predict_tree_ratios(model, feats).mean() * feats["_trailing_mean"])
    return np.array(preds)


# ----------------------------------------------------------------------------- metrics
def psi(expected: np.ndarray, actual: np.ndarray, bins: int | None = None) -> float:
    """Population Stability Index of `actual` vs `expected`, bins = quantiles of `expected`.

    Default bin count keeps >= ~5 observations per bin in the smaller sample (max 10). With
    only 24 test months, the textbook 10 bins leaves ~2 points per bin, empty bins hit the
    epsilon floor and PSI explodes (>3) from sampling noise alone, not real drift.
    Reading: < 0.10 stable · 0.10-0.25 moderate shift · > 0.25 significant shift.
    """
    if bins is None:
        bins = max(2, min(10, min(len(expected), len(actual)) // 5))
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def gini(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Gini of `actual` when sorted by `predicted` (descending)."""
    order = np.argsort(-np.asarray(predicted), kind="mergesort")
    a = np.asarray(actual, dtype=float)[order]
    n = len(a)
    cum_share = np.cumsum(a) / a.sum()
    return float(cum_share.sum() / n - (n + 1) / (2 * n))


def normalized_gini(actual: np.ndarray, predicted: np.ndarray) -> float:
    """1.0 = the forecast ranks months exactly like reality; 0 = no better than random."""
    return gini(actual, predicted) / gini(actual, actual)


def compute_metrics(actual: np.ndarray, forecast: np.ndarray, low: np.ndarray, high: np.ndarray,
                    train_target_ratio: np.ndarray, test_target_ratio: np.ndarray) -> dict:
    mse = mean_squared_error(actual, forecast)
    rmse = float(np.sqrt(mse))
    avg_rev = float(actual.mean())
    return {
        "mse_usd2": float(mse),
        "rmse_usd": rmse,
        "rmse_pct_of_avg_monthly_revenue": rmse / avg_rev * 100,
        "mae_usd": float(mean_absolute_error(actual, forecast)),
        "mape_pct": float(np.mean(np.abs(forecast - actual) / actual) * 100),
        "avg_monthly_revenue_test_usd": avg_rev,
        "r2_score": float(r2_score(actual, forecast)),
        "gini_normalized": normalized_gini(actual, forecast),
        "psi_forecast_vs_actual_test": psi(actual, forecast),
        "psi_seasonal_ratio_train_vs_test": psi(train_target_ratio, test_target_ratio),
        "band_coverage_pct": float(np.mean((actual >= low) & (actual <= high)) * 100),
        "august_detected_as_lowest_month": None,  # filled in by caller
    }


# ---------------------------------------------------------------------------- plotting
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
FORECAST_BLUE = "#2a78d6"  # categorical slot 1 of the reference palette


def plot_forecast(train_df: pd.DataFrame, test_df: pd.DataFrame, forecast: np.ndarray,
                  low: np.ndarray, high: np.ndarray, metrics: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    test_start = test_df["month"].min()
    forecast_origin = train_df["month"].max().strftime("%Y-%m")
    test_years = f"{test_start.year}–{test_df['month'].max().year}"
    context = train_df[train_df["month"] >= test_start - pd.DateOffset(years=2)]
    musd = 1e6

    ax.plot(context["month"], context[TARGET] / musd, color=INK_MUTED, lw=1.5, alpha=0.6,
            label="Actual, training years (context)")
    ax.fill_between(test_df["month"], low / musd, high / musd, color=FORECAST_BLUE, alpha=0.18,
                    lw=0, label=f"Variability range (P{BAND_QUANTILES[0]}–P{BAND_QUANTILES[1]} across trees)")
    ax.plot(test_df["month"], forecast / musd, color=FORECAST_BLUE, lw=2, ls="--",
            marker="o", ms=4, label=f"Forecast (made at {forecast_origin}, never saw {test_years})")
    ax.plot(test_df["month"], test_df[TARGET] / musd, color=INK, lw=2, marker="o", ms=4,
            label="Actual revenue, test years")

    ax.axvline(test_start, color=INK_MUTED, lw=1, ls=":")
    ax.text(test_start + pd.Timedelta(days=14), 0.985, "test period →", transform=ax.get_xaxis_transform(),
            color=INK_MUTED, fontsize=9, va="top")
    for aug in test_df.loc[test_df["month"].dt.month == 8, "month"]:
        val = test_df.loc[test_df["month"] == aug, TARGET].iloc[0] / musd
        ax.annotate("August\n(summer slowdown)", (aug, val), xytext=(0, -34), textcoords="offset points",
                    ha="center", fontsize=8, color=INK_MUTED)

    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:.1f}M"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    ax.set_ylim(bottom=0.5)

    ax.set_title(f"Nexova monthly revenue — {len(test_df)}-month forecast vs actual ({test_years})",
                 loc="left", fontsize=13, color=INK, pad=24)
    ax.text(0, 1.02, (f"Random Forest · error ±{metrics['rmse_pct_of_avg_monthly_revenue']:.1f}% of an average "
                      f"month (RMSE) · MAPE {metrics['mape_pct']:.1f}% · R² {metrics['r2_score']:.2f} · "
                      f"{metrics['band_coverage_pct']:.0f}% of months inside the range"),
            transform=ax.transAxes, fontsize=9, color=INK_MUTED)
    ax.set_ylabel("Revenue (USD, consolidated)", color=INK_MUTED, fontsize=9)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# -------------------------------------------------------------------------------- main
def run(data_path: Path = DATA_PATH, output_dir: Path = OUTPUT_DIR) -> dict:
    df = load_sales(data_path)
    pattern_check = validate_patterns(df)
    train_df, test_df = split_train_test(df)

    # Features are built on the full series so test rows can use 2023 history as lags, but
    # the model is fitted on rows whose *target month* is in the training years only.
    features = build_feature_frame(df)
    train_feats = features[features["month"] <= train_df["month"].max()]
    test_feats = features[features["month"] >= test_df["month"].min()]
    assert train_feats["month"].max() < test_df["month"].min(), "train rows leak into test"

    model = train_model(train_feats)

    # Headline: recursive 24-month forecast from end of training — no test actuals used.
    paths = recursive_forecast(model, train_df[TARGET].to_numpy(), list(test_df["month"]))
    forecast = paths.mean(axis=0)
    low, high = np.percentile(paths, BAND_QUANTILES, axis=0)
    actual = test_df[TARGET].to_numpy()

    one_step = one_step_forecast(model, df, start_idx=len(train_df))

    metrics = compute_metrics(actual, forecast, low, high,
                              train_feats["target_ratio"].to_numpy(),
                              test_feats["target_ratio"].to_numpy())
    lowest_pred = {y: test_df["month"].iloc[np.argmin(np.where(test_df["month"].dt.year == y, forecast, np.inf))]
                   for y in test_df["month"].dt.year.unique()}
    metrics["august_detected_as_lowest_month"] = all(m.month == 8 for m in lowest_pred.values())
    metrics["one_step_ahead"] = {
        "rmse_pct_of_avg_monthly_revenue": float(np.sqrt(mean_squared_error(actual, one_step)) / actual.mean() * 100),
        "mape_pct": float(np.mean(np.abs(one_step - actual) / actual) * 100),
        "r2_score": float(r2_score(actual, one_step)),
        "gini_normalized": normalized_gini(actual, one_step),
    }
    metrics["psi_business_line_mix"] = ("not computable: nexova_sales.csv only contains "
                                        "`consolidated` rows (no per-line breakdown)")
    metrics["split"] = {
        "train": [train_df["month"].min().strftime("%Y-%m"), train_df["month"].max().strftime("%Y-%m")],
        "test": [test_df["month"].min().strftime("%Y-%m"), test_df["month"].max().strftime("%Y-%m")],
        "train_rows_raw": len(train_df), "train_rows_after_warmup": len(train_feats),
        "test_rows": len(test_df),
    }
    metrics["model"] = {"algorithm": "RandomForestRegressor", "random_state": RANDOM_STATE,
                        **{k: v for k, v in model.get_params().items()
                           if k in ("n_estimators", "min_samples_leaf", "max_features")}}
    metrics["feature_importance"] = dict(sorted(
        ((f, round(float(i), 4)) for f, i in zip(FEATURES, model.feature_importances_)),
        key=lambda kv: -kv[1]))
    metrics["pattern_check"] = pattern_check

    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "month": test_df["month"].dt.strftime("%Y-%m-%d"),
        "actual_revenue_usd": actual.round(2),
        "forecast_revenue_usd": forecast.round(2),
        f"band_p{BAND_QUANTILES[0]}_usd": low.round(2),
        f"band_p{BAND_QUANTILES[1]}_usd": high.round(2),
        "one_step_forecast_usd": one_step.round(2),
        "abs_error_pct": (np.abs(forecast - actual) / actual * 100).round(2),
    }).to_csv(output_dir / "test_predictions.csv", index=False)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    plot_forecast(train_df, test_df, forecast, low, high, metrics, output_dir / "forecast_vs_actual.png")
    return metrics


def main() -> None:
    m = run()
    print("Nexova revenue forecast — test set 2024-01..2025-12 (recursive, 24 months)")
    print(f"  MSE                 {m['mse_usd2']:,.0f} USD²")
    print(f"  RMSE                ${m['rmse_usd']:,.0f}  = {m['rmse_pct_of_avg_monthly_revenue']:.2f}% of avg month "
          f"(${m['avg_monthly_revenue_test_usd']:,.0f})")
    print(f"  MAPE                {m['mape_pct']:.2f}%")
    print(f"  R² score            {m['r2_score']:.3f}")
    print(f"  Gini (normalized)   {m['gini_normalized']:.3f}")
    print(f"  PSI forecast/actual {m['psi_forecast_vs_actual_test']:.3f}")
    print(f"  PSI seasonal ratio train vs test {m['psi_seasonal_ratio_train_vs_test']:.3f}")
    print(f"  Band coverage       {m['band_coverage_pct']:.0f}%   August lowest each year: "
          f"{m['august_detected_as_lowest_month']}")
    print(f"  One-step-ahead      {m['one_step_ahead']}")
    print(f"Outputs in {OUTPUT_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
