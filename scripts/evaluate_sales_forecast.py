"""Formal evaluation of the Nexova revenue forecast (Random Forest) before promotion to staging.

Ticket questions this script answers with evidence (report: data/eval/evaluation_report.md):
  1. Underfitting, overfitting, or reasonably well fitted?  -> learning curve + train/val gap
  2. How stable is performance when the training window changes? -> time-aware CV, mean ± std
  3. If there is a problem, what is the specific corrective action? -> complexity sweep

Scope: ONLY the training years (2016-01 .. 2023-12) from scripts/train_sales_forecast.py.
The 2024-2025 test years stay untouched, so this evaluation cannot leak into the final test.

Run (repo root):
    uv run python scripts/evaluate_sales_forecast.py

Outputs (data/eval/):
    learning_curve.png                 training vs validation error as the training window grows
    model_evaluation/cv_folds.csv      per-fold MAE / RMSE (train and validation), fold dates
    model_evaluation/learning_curve.csv
    model_evaluation/complexity_sweep.csv
    model_evaluation/evaluation_metrics.json

-----------------------------------------------------------------------------------------
TIME-AWARE CROSS-VALIDATION
-----------------------------------------------------------------------------------------
* sklearn TimeSeriesSplit(n_splits=5, test_size=12) over the 72 feature rows of the training
  years (2018-01 .. 2023-12, after the 24-month lag warm-up). Each validation fold is exactly
  one calendar year (2019, 2020, 2021, 2022, 2023), so every fold contains a full August dip
  and Jan-Feb peak, and each training window is everything before it (expanding window).
  No shuffling anywhere: indices are strictly increasing inside each fold.
* Leakage across the fold boundary: every feature for month t is computed by
  `features_from_history(values[:t])`, i.e. from months < t only. For each fold we REBUILD
  the feature frame from the series truncated at the end of that fold's validation year,
  so no value after the validation window can exist in memory while the fold is scored, and
  training rows (all earlier than validation) cannot contain any validation-month value.
  The unit tests in tests/pipelines/test_model_evaluation.py check both properties.
* Validation predictions are one-step-ahead (features use actual revenue up to the month
  before), which is how a monthly rolling forecast is run in production.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error  # noqa: E402
from sklearn.model_selection import TimeSeriesSplit  # noqa: E402

from train_sales_forecast import (  # noqa: E402
    DATA_PATH,
    FEATURES,
    MIN_TRAIN_FEATURE_MONTHS,
    RANDOM_STATE,
    REPO_ROOT,
    TARGET,
    WARMUP_MONTHS,
    build_feature_frame,
    load_sales,
    split_train_test,
)

EVAL_DIR = REPO_ROOT / "data" / "eval"
DETAIL_DIR = EVAL_DIR / "model_evaluation"
N_SPLITS = 5
FOLD_SIZE = 12  # one calendar year per validation fold
LEARNING_CURVE_SIZES = [12, 24, 36, 48, 60]  # months of training data

# The production configuration from train_sales_forecast.train_model.
BASE_PARAMS = {"n_estimators": 300, "min_samples_leaf": 2, "max_features": 0.6}
# Complexity sweep: min_samples_leaf is the main capacity knob of a Random Forest
# (1 = trees grow until every leaf is a single month, i.e. maximum memorisation).
LEAF_SWEEP = [1, 2, 3, 5, 8, 12]


# --------------------------------------------------------------------------- folds
def time_series_folds(n_rows: int, n_splits: int = N_SPLITS, fold_size: int = FOLD_SIZE):
    """Expanding-window folds over row positions 0..n_rows-1, chronological, never shuffled."""
    return list(TimeSeriesSplit(n_splits=n_splits, test_size=fold_size).split(np.arange(n_rows)))


def fold_feature_frame(train_df: pd.DataFrame, val_end: pd.Timestamp) -> pd.DataFrame:
    """Feature rows rebuilt from the series truncated at `val_end` (nothing later exists)."""
    visible = train_df[train_df["month"] <= val_end].reset_index(drop=True)
    return build_feature_frame(visible)


# --------------------------------------------------------------------------- model
def make_model(**overrides) -> RandomForestRegressor:
    params = {**BASE_PARAMS, **overrides}
    return RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=-1, **params)


def _usd(model, rows: pd.DataFrame) -> np.ndarray:
    """Model predicts revenue / trailing-12-month mean; convert back to USD."""
    return model.predict(rows[FEATURES]) * rows["_trailing_mean"].to_numpy()


def _errors(actual: np.ndarray, pred: np.ndarray) -> dict:
    err = pred - actual
    return {
        "mae": float(mean_absolute_error(actual, pred)),
        "rmse": float(np.sqrt(mean_squared_error(actual, pred))),
        "bias": float(err.mean()),  # > 0 means the model over-forecasts on average
        "over_forecast_share": float((err > 0).mean()),
        "max_abs": float(np.abs(err).max()),
    }


def fit_and_score(train_rows: pd.DataFrame, val_rows: pd.DataFrame, **overrides) -> dict:
    """Train/validation errors in USD, plus out-of-bag (OOB) training error.

    In-sample training error of a Random Forest is always optimistic: each tree has seen most
    of the rows it is scored on. OOB error scores every training month only with the trees
    that did NOT see it, so it is an honest "unseen data" error inside the training window.
    If OOB ~ validation, the train/validation gap is in-sample optimism, not memorisation.
    """
    model = make_model(oob_score=True, **overrides)
    model.fit(train_rows[FEATURES], train_rows["target_ratio"])
    actual_tr = train_rows[TARGET].to_numpy()
    tr = _errors(actual_tr, _usd(model, train_rows))
    oob_pred = model.oob_prediction_ * train_rows["_trailing_mean"].to_numpy()
    oob = _errors(actual_tr, oob_pred)
    va = _errors(val_rows[TARGET].to_numpy(), _usd(model, val_rows))
    return {"train": tr, "oob": oob, "val": va, "val_mean_revenue": float(val_rows[TARGET].mean())}


# --------------------------------------------------------------------------- evaluation steps
def cross_validate(train_df: pd.DataFrame, **overrides) -> pd.DataFrame:
    all_rows = build_feature_frame(train_df)
    rows = []
    for k, (tr_idx, va_idx) in enumerate(time_series_folds(len(all_rows)), start=1):
        val_end = all_rows["month"].iloc[va_idx[-1]]
        feats = fold_feature_frame(train_df, val_end)  # nothing after the validation year
        tr, va = feats.iloc[tr_idx], feats.iloc[va_idx]
        assert tr["month"].max() < va["month"].min()
        s = fit_and_score(tr, va, **overrides)
        rows.append({
            "fold": k,
            "train_from": tr["month"].min().strftime("%Y-%m"),
            "train_to": tr["month"].max().strftime("%Y-%m"),
            "val_from": va["month"].min().strftime("%Y-%m"),
            "val_to": va["month"].max().strftime("%Y-%m"),
            "train_months": len(tr),
            "train_mae": s["train"]["mae"], "train_rmse": s["train"]["rmse"],
            "oob_mae": s["oob"]["mae"], "oob_rmse": s["oob"]["rmse"],
            "val_mae": s["val"]["mae"], "val_rmse": s["val"]["rmse"],
            "val_bias": s["val"]["bias"], "val_over_forecast_share": s["val"]["over_forecast_share"],
            "val_max_abs_error": s["val"]["max_abs"],
            "val_mae_pct": s["val"]["mae"] / s["val_mean_revenue"] * 100,
            "val_rmse_pct": s["val"]["rmse"] / s["val_mean_revenue"] * 100,
        })
    return pd.DataFrame(rows)


def learning_curve(train_df: pd.DataFrame, sizes=LEARNING_CURVE_SIZES) -> pd.DataFrame:
    """For each training size n and each fold that has >= n earlier months, train on the
    n months immediately before the validation year and score both sides."""
    all_rows = build_feature_frame(train_df)
    out = []
    for n in sizes:
        for k, (tr_idx, va_idx) in enumerate(time_series_folds(len(all_rows)), start=1):
            if len(tr_idx) < n:
                continue
            val_end = all_rows["month"].iloc[va_idx[-1]]
            feats = fold_feature_frame(train_df, val_end)
            tr, va = feats.iloc[tr_idx[-n:]], feats.iloc[va_idx]
            s = fit_and_score(tr, va)
            out.append({"train_months": n, "fold": k,
                        "train_mae": s["train"]["mae"], "oob_mae": s["oob"]["mae"], "val_mae": s["val"]["mae"],
                        "train_rmse": s["train"]["rmse"], "val_rmse": s["val"]["rmse"]})
    return pd.DataFrame(out)


def naive_seasonal_baseline(train_df: pd.DataFrame) -> dict:
    """Same-month-last-year x trailing growth: the 'no model' reference on the same folds."""
    all_rows = build_feature_frame(train_df)
    maes, rmses = [], []
    for _, va_idx in time_series_folds(len(all_rows)):
        va = all_rows.iloc[va_idx]
        pred = va["lag_12_ratio"] * (1 + va["trailing_yoy_growth"]) * va["_trailing_mean"]
        maes.append(mean_absolute_error(va[TARGET], pred))
        rmses.append(np.sqrt(mean_squared_error(va[TARGET], pred)))
    return {"val_mae_mean": float(np.mean(maes)), "val_mae_std": float(np.std(maes, ddof=1)),
            "val_rmse_mean": float(np.mean(rmses)), "val_rmse_std": float(np.std(rmses, ddof=1))}


def complexity_sweep(train_df: pd.DataFrame, leaves=LEAF_SWEEP) -> pd.DataFrame:
    rows = []
    for leaf in leaves:
        cv = cross_validate(train_df, min_samples_leaf=leaf)
        rows.append({"min_samples_leaf": leaf,
                     "train_mae_mean": cv["train_mae"].mean(), "oob_mae_mean": cv["oob_mae"].mean(),
                     "val_mae_mean": cv["val_mae"].mean(),
                     "val_mae_std": cv["val_mae"].std(ddof=1),
                     "train_rmse_mean": cv["train_rmse"].mean(), "val_rmse_mean": cv["val_rmse"].mean(),
                     "val_rmse_std": cv["val_rmse"].std(ddof=1),
                     "gap_mae_ratio": cv["val_mae"].mean() / cv["train_mae"].mean()})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- plotting
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
TRAIN_COLOR, VAL_COLOR = "#2a78d6", "#d9622b"


def plot_learning_curve(lc: pd.DataFrame, cv_summary: dict, baseline: dict, path: Path) -> None:
    g = lc.groupby("train_months").agg(train_mae=("train_mae", "mean"), train_sd=("train_mae", "std"),
                                       oob_mae=("oob_mae", "mean"),
                                       val_mae=("val_mae", "mean"), val_sd=("val_mae", "std"),
                                       folds=("fold", "count")).reset_index()
    g = g.fillna({"train_sd": 0.0, "val_sd": 0.0})
    k = 1e3
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    x = g["train_months"]
    for col, sd, color, label in [("train_mae", "train_sd", TRAIN_COLOR, "Training error"),
                                  ("val_mae", "val_sd", VAL_COLOR, "Validation error (next calendar year)")]:
        ax.fill_between(x, (g[col] - g[sd]) / k, (g[col] + g[sd]) / k, color=color, alpha=0.15, lw=0)
        ax.plot(x, g[col] / k, color=color, lw=2.2, marker="o", ms=5, label=label)
    ax.plot(x, g["oob_mae"] / k, color=TRAIN_COLOR, lw=1.6, ls=":", marker="s", ms=4,
            label="Out-of-bag error (training months each tree never saw)")
    ax.axhline(baseline["val_mae_mean"] / k, color=INK_MUTED, lw=1, ls="--")
    ax.text(x.iloc[-1], baseline["val_mae_mean"] / k, "  naive seasonal baseline (validation)",
            color=INK_MUTED, fontsize=8, va="bottom", ha="right")
    for _, r in g.iterrows():
        ax.annotate(f"{int(r['folds'])} fold{'s' if r['folds'] > 1 else ''}", (r["train_months"], r["val_mae"] / k),
                    xytext=(0, 9), textcoords="offset points", ha="center", fontsize=7.5, color=INK_MUTED)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{m} mo\n({m // 12} yr)" for m in x])
    ax.set_xlabel("Training window (most recent months before the validation year)", color=INK_MUTED, fontsize=9)
    ax.set_ylabel("MAE, USD thousands per month", color=INK_MUTED, fontsize=9)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    ax.set_title("Nexova revenue forecast — learning curve (training years 2016–2023 only)",
                 loc="left", fontsize=13, color=INK, pad=24)
    ax.text(0, 1.02, (f"Random Forest · 5-fold TimeSeriesSplit validation MAE "
                      f"\\${cv_summary['val_mae_mean'] / k:,.1f}k ± \\${cv_summary['val_mae_std'] / k:,.1f}k "
                      f"(mean ± sd across folds) · shaded = ±1 sd across folds"),
            transform=ax.transAxes, fontsize=9, color=INK_MUTED)
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# --------------------------------------------------------------------------- main
def _mean_sd(s: pd.Series) -> tuple[float, float]:
    return float(s.mean()), float(s.std(ddof=1))


def run(data_path: Path = DATA_PATH) -> dict:
    df = load_sales(data_path)
    train_df, _test_df_never_used = split_train_test(df)

    cv = cross_validate(train_df)
    lc = learning_curve(train_df)
    sweep = complexity_sweep(train_df)
    baseline = naive_seasonal_baseline(train_df)

    summary = {}
    for col in ["train_mae", "train_rmse", "oob_mae", "oob_rmse", "val_mae", "val_rmse", "val_mae_pct", "val_rmse_pct", "val_bias"]:
        m, sd = _mean_sd(cv[col])
        summary[f"{col}_mean"], summary[f"{col}_std"] = m, sd
    summary["val_mae_cv_pct"] = summary["val_mae_std"] / summary["val_mae_mean"] * 100
    summary["gap_mae_ratio"] = summary["val_mae_mean"] / summary["train_mae_mean"]
    summary["gap_rmse_ratio"] = summary["val_rmse_mean"] / summary["train_rmse_mean"]
    summary["rmse_over_mae"] = summary["val_rmse_mean"] / summary["val_mae_mean"]

    # Stability once the minimum training window is respected (folds 2-5).
    ok = cv[cv["train_months"] >= MIN_TRAIN_FEATURE_MONTHS]
    summary_min_window = {"folds": ok["fold"].tolist(), "min_train_feature_months": MIN_TRAIN_FEATURE_MONTHS}
    for col in ["train_mae", "oob_mae", "val_mae", "train_rmse", "val_rmse", "val_mae_pct", "val_rmse_pct"]:
        m, sd = _mean_sd(ok[col])
        summary_min_window[f"{col}_mean"], summary_min_window[f"{col}_std"] = m, sd

    metrics = {
        "scope": {"evaluated_on": [train_df["month"].min().strftime("%Y-%m"), train_df["month"].max().strftime("%Y-%m")],
                  "feature_rows": int(len(train_df) - WARMUP_MONTHS),
                  "test_years_used": False},
        "cv_strategy": {"type": "TimeSeriesSplit", "n_splits": N_SPLITS, "test_size_months": FOLD_SIZE,
                        "shuffle": False, "window": "expanding",
                        "features_rebuilt_per_fold_from_truncated_series": True},
        "model": {"algorithm": "RandomForestRegressor", "random_state": RANDOM_STATE, **BASE_PARAMS},
        "cv_summary_usd": summary,
        "cv_summary_usd_min_window_respected": summary_min_window,
        "naive_seasonal_baseline_usd": baseline,
        "learning_curve_by_size": lc.groupby("train_months")[["train_mae", "oob_mae", "val_mae", "train_rmse", "val_rmse"]]
                                    .mean().round(2).to_dict(orient="index"),
        "complexity_sweep": sweep.round(4).to_dict(orient="records"),
    }

    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    cv.round(4).to_csv(DETAIL_DIR / "cv_folds.csv", index=False)
    lc.round(2).to_csv(DETAIL_DIR / "learning_curve.csv", index=False)
    sweep.round(4).to_csv(DETAIL_DIR / "complexity_sweep.csv", index=False)
    (DETAIL_DIR / "evaluation_metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    plot_learning_curve(lc, summary, baseline, EVAL_DIR / "learning_curve.png")
    return {"cv": cv, "lc": lc, "sweep": sweep, "baseline": baseline, "summary": summary,
            "summary_min_window": summary_min_window}


def main() -> None:
    r = run()
    s = r["summary"]
    print("Nexova revenue forecast — time-aware evaluation on training years 2016-2023")
    print(r["cv"][["fold", "train_from", "train_to", "val_from", "val_to", "train_mae", "val_mae",
                   "train_rmse", "val_rmse", "val_bias"]].round(0).to_string(index=False))
    print(f"  Train MAE  ${s['train_mae_mean']:,.0f} ± ${s['train_mae_std']:,.0f}")
    print(f"  Val   MAE  ${s['val_mae_mean']:,.0f} ± ${s['val_mae_std']:,.0f}  "
          f"({s['val_mae_pct_mean']:.2f}% ± {s['val_mae_pct_std']:.2f}% of an average month)")
    print(f"  Train RMSE ${s['train_rmse_mean']:,.0f} ± ${s['train_rmse_std']:,.0f}")
    print(f"  Val   RMSE ${s['val_rmse_mean']:,.0f} ± ${s['val_rmse_std']:,.0f}")
    print(f"  Val/Train MAE ratio {s['gap_mae_ratio']:.2f}   RMSE/MAE {s['rmse_over_mae']:.2f}   "
          f"bias ${s['val_bias_mean']:,.0f}")
    w = r["summary_min_window"]
    print(f"  Folds with >= {w['min_train_feature_months']} training months {w['folds']}: "
          f"val MAE ${w['val_mae_mean']:,.0f} ± ${w['val_mae_std']:,.0f}, "
          f"val RMSE ${w['val_rmse_mean']:,.0f} ± ${w['val_rmse_std']:,.0f}, OOB MAE ${w['oob_mae_mean']:,.0f}")
    print(f"  Naive seasonal baseline val MAE ${r['baseline']['val_mae_mean']:,.0f} ± ${r['baseline']['val_mae_std']:,.0f}")
    print("Learning curve (mean over folds):")
    print(r["lc"].groupby("train_months")[["train_mae", "oob_mae", "val_mae"]].mean().round(0).to_string())
    print("Complexity sweep:")
    print(r["sweep"].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
