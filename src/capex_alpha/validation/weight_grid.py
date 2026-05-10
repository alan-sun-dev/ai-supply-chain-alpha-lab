"""Phase A2 — weight grid search with train/test split and overfit guard.

We recompute ``alpha_score`` analytically from the per-(date, ticker) tier
scores recorded during walk-forward, instead of re-running scoring at each
grid cell. Each recorded tier value is

    recorded_tier = raw_tier_score * SCALE * (current_tier_weight / orig_weight)

So under a candidate weight ``w``, the new tier value is

    new_tier = recorded_tier * (w / current_weight)

Risk penalty is added directly during scoring; we apply a multiplier on the
recorded value.

Sector_relative and narrative weights are pinned at 0 (Phase A1 conclusion).
CAPEX context score is always 0 in the recorded data (no per-ticker context
attribution implemented yet), so its weight has no effect — we omit it from
the sweep but keep it in the YAML for hierarchy completeness.

Grid dimensions
---------------
- residual_alpha_score:        0.30 .. 0.55, step 0.05  (6 values)
- revenue_confirmation_score:  0.10 .. 0.30, step 0.05  (5 values)
- institutional_flow_score:    0.05 .. 0.20, step 0.05  (4 values)
- risk_penalty_multiplier:     0.5  .. 2.0,  step 0.25  (7 values)
- min_alpha (Strong threshold): 2.5 .. 4.0,  step 0.5   (4 values)

Total cells: 6 * 5 * 4 * 7 * 4 = 3,360.

Train / test split
------------------
- Train: rebalance_date <= 2023-12-29  (43 months)
- Test:  rebalance_date >= 2024-01-31  (28 months)
- Robustness filter: keep only cells where test_sharpe >= 0.80 * train_sharpe
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..utils import ensure_dir, get_logger, resolve_path

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants

# Original tier weights at the time walk_forward_v2_results.csv was generated
# (i.e. the A1 weights used in the scoring run we're rebuilding from).
ORIG_WEIGHTS = {
    "residual_alpha_score":       0.35,
    "revenue_confirmation_score": 0.20,
    "institutional_flow_score":   0.15,
}

GRID = {
    # A2-rerun (post-B3, 2026-05-03): widened ranges based on B3 ablation
    # findings (residual_alpha_only and no_revenue both beat full model).
    # rev=0 and flw=0 explicitly included so the grid can recommend dropping
    # those tiers entirely if the data supports it.
    "residual_alpha_score":       [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60],
    "revenue_confirmation_score": [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    "institutional_flow_score":   [0.00, 0.05, 0.10, 0.15, 0.20],
    "risk_penalty_multiplier":    [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
    "min_alpha":                  [2.5, 3.0, 3.5, 4.0],
}

# Watchlist threshold for hit-rate bucketing (mirror of YAML default).
WATCHLIST_ALPHA_DEFAULT = 2.0

TRAIN_END   = pd.Timestamp("2023-12-29")
TEST_START  = pd.Timestamp("2024-01-31")
ROBUSTNESS_THRESHOLD = 0.80
MIN_STRONG_OBS = 15


# ---------------------------------------------------------------------------
# Core math

def rebuild_alpha(df: pd.DataFrame, residual_w: float, revenue_w: float,
                  flow_w: float, risk_mult: float) -> pd.Series:
    """Recompute alpha_score under the candidate weights.

    Vectorised — operates on the full long-format frame.
    """
    a = df["residual_alpha_score"]      * (residual_w / ORIG_WEIGHTS["residual_alpha_score"])
    b = df["revenue_confirmation_score"] * (revenue_w / ORIG_WEIGHTS["revenue_confirmation_score"])
    c = df["institutional_flow_score"]   * (flow_w    / ORIG_WEIGHTS["institutional_flow_score"])
    pen = df["risk_penalty"] * risk_mult
    # sector + narrative + capex_context are zero in A1; keep that.
    return a + b + c - pen


def _greedy_pick(sub_sorted: pd.DataFrame, n: int,
                 theme_map: dict | None, max_per_theme: int | None) -> list[str]:
    """Top-N picker honouring per-theme cap when both are set."""
    if theme_map is None or max_per_theme is None or max_per_theme >= n:
        return sub_sorted.head(n)["ticker"].tolist()
    picks: list[str] = []
    theme_count: dict[str, int] = {}
    for _, r in sub_sorted.iterrows():
        theme = theme_map.get(r["ticker"], "unknown")
        if theme_count.get(theme, 0) >= max_per_theme:
            continue
        picks.append(r["ticker"])
        theme_count[theme] = theme_count.get(theme, 0) + 1
        if len(picks) >= n:
            break
    return picks


def topn_returns(df: pd.DataFrame, alpha_col: str, n: int = 5,
                 theme_map: dict | None = None,
                 max_per_theme: int | None = None) -> pd.Series:
    """Equal-weight top-N at each rebalance → monthly portfolio return series."""
    rets, dates = [], []
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[alpha_col, "fwd_return_1m"])
        if len(sub) < n:
            continue
        picks = _greedy_pick(sub.sort_values(alpha_col, ascending=False),
                             n, theme_map, max_per_theme)
        if len(picks) < n:
            continue
        top = sub[sub["ticker"].isin(picks)]
        rets.append(float(top["fwd_return_1m"].mean()))
        dates.append(t)
    return pd.Series(rets, index=pd.DatetimeIndex(dates), name=alpha_col)


def topn_holdings(df: pd.DataFrame, alpha_col: str, n: int = 5,
                  theme_map: dict | None = None,
                  max_per_theme: int | None = None) -> dict[pd.Timestamp, list[str]]:
    """Same selection as ``topn_returns`` but returns the holdings dict."""
    out: dict[pd.Timestamp, list[str]] = {}
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[alpha_col])
        if len(sub) < n:
            continue
        picks = _greedy_pick(sub.sort_values(alpha_col, ascending=False),
                             n, theme_map, max_per_theme)
        if len(picks) >= n:
            out[pd.Timestamp(t)] = picks
    return out


def annualised_turnover(holdings: dict[pd.Timestamp, list[str]]) -> float:
    """One-way turnover annualised, excluding the initial deployment month."""
    dates = sorted(holdings.keys())
    if len(dates) < 2:
        return float("nan")
    changes = []
    for prev, curr in zip(dates[:-1], dates[1:]):
        prev_set, curr_set = set(holdings[prev]), set(holdings[curr])
        if not curr_set:
            continue
        changes.append(len(curr_set - prev_set) / len(curr_set))
    if not changes:
        return float("nan")
    return float(np.mean(changes) * 12.0)


def alpha_bucket_hits(df: pd.DataFrame, alpha_col: str,
                      strong_min: float, watch_min: float) -> dict:
    """Hit rates by alpha bucket — proxy for decision-zone hit rates.

    Buckets:
      - strong:  alpha >= strong_min
      - watch:   watch_min <= alpha < strong_min
      - neutral: 0 <= alpha < watch_min
      - avoid:   alpha < 0
    """
    sub = df.dropna(subset=[alpha_col, "fwd_return_1m"]).copy()
    if sub.empty:
        return {"strong_n": 0, "strong_hit": np.nan,
                "watch_n": 0,  "watch_hit": np.nan,
                "neutral_n": 0, "neutral_hit": np.nan,
                "avoid_n": 0,  "avoid_hit": np.nan}
    a = sub[alpha_col]
    fr = sub["fwd_return_1m"]
    s_mask = a >= strong_min
    w_mask = (a >= watch_min) & (a < strong_min)
    n_mask = (a >= 0) & (a < watch_min)
    av_mask = a < 0
    def _h(mask):
        if mask.sum() == 0:
            return np.nan
        return float((fr[mask] > 0).mean())
    return {
        "strong_n":  int(s_mask.sum()), "strong_hit":  _h(s_mask),
        "watch_n":   int(w_mask.sum()), "watch_hit":   _h(w_mask),
        "neutral_n": int(n_mask.sum()), "neutral_hit": _h(n_mask),
        "avoid_n":   int(av_mask.sum()), "avoid_hit":  _h(av_mask),
    }


def metrics(returns: pd.Series) -> dict:
    if returns.empty or returns.std(ddof=0) == 0:
        return {"sharpe": np.nan, "max_dd": 0.0, "total": 0.0, "mean_monthly": np.nan, "n": 0}
    sharpe = float(returns.mean() / returns.std(ddof=0) * np.sqrt(12))
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    max_dd = float((nav / nav.cummax() - 1.0).min())
    total = float(nav.iloc[-1] - 1.0)
    return {
        "sharpe": sharpe,
        "max_dd": max_dd,
        "total": total,
        "mean_monthly": float(returns.mean()),
        "n": int(returns.shape[0]),
    }


def strong_stats(df: pd.DataFrame, alpha_col: str, min_alpha: float) -> dict:
    sub = df[df[alpha_col] >= min_alpha].dropna(subset=["fwd_return_1m"])
    if sub.empty:
        return {"strong_n": 0, "strong_unique": 0, "strong_hit": np.nan, "strong_mean": np.nan}
    return {
        "strong_n":      int(len(sub)),
        "strong_unique": int(sub["ticker"].nunique()),
        "strong_hit":    float((sub["fwd_return_1m"] > 0).mean()),
        "strong_mean":   float(sub["fwd_return_1m"].mean()),
    }


# ---------------------------------------------------------------------------
# Sweep

def run_grid(results_df: pd.DataFrame, top_n: int = 5,
             theme_map: dict | None = None,
             max_per_theme: int | None = None,
             cost_bps_for_net_cagr: float = 25.0) -> pd.DataFrame:
    """Execute the full grid sweep. Returns one row per cell.

    A2-rerun additions:
    - ``theme_map`` + ``max_per_theme`` apply Step-1 portfolio-construction cap
    - per-cell `annualised_turnover` and `net_cagr_25bps`
    - per-cell zone-bucket hit rates (`watch_hit_full`, `neutral_hit_full`)
    """
    weight_combos = list(itertools.product(
        GRID["residual_alpha_score"],
        GRID["revenue_confirmation_score"],
        GRID["institutional_flow_score"],
        GRID["risk_penalty_multiplier"],
    ))

    train_df = results_df[results_df["rebalance_date"] <= TRAIN_END].copy()
    test_df  = results_df[results_df["rebalance_date"] >= TEST_START].copy()
    full_df  = results_df.copy()

    rows: list[dict] = []
    for i, (ra_w, rev_w, flw_w, risk_m) in enumerate(weight_combos):
        if i % 100 == 0:
            logger.info("[%d/%d] ra=%.2f rev=%.2f flw=%.2f risk×=%.2f",
                        i, len(weight_combos), ra_w, rev_w, flw_w, risk_m)

        train_df["alpha_recomputed"] = rebuild_alpha(train_df, ra_w, rev_w, flw_w, risk_m)
        test_df["alpha_recomputed"]  = rebuild_alpha(test_df,  ra_w, rev_w, flw_w, risk_m)
        full_df["alpha_recomputed"]  = rebuild_alpha(full_df,  ra_w, rev_w, flw_w, risk_m)

        train_port = topn_returns(train_df, "alpha_recomputed", n=top_n,
                                  theme_map=theme_map, max_per_theme=max_per_theme)
        test_port  = topn_returns(test_df,  "alpha_recomputed", n=top_n,
                                  theme_map=theme_map, max_per_theme=max_per_theme)
        full_port  = topn_returns(full_df,  "alpha_recomputed", n=top_n,
                                  theme_map=theme_map, max_per_theme=max_per_theme)
        full_holdings = topn_holdings(full_df, "alpha_recomputed", n=top_n,
                                       theme_map=theme_map, max_per_theme=max_per_theme)
        train_m = metrics(train_port)
        test_m  = metrics(test_port)
        full_m  = metrics(full_port)
        ann_to  = annualised_turnover(full_holdings)

        # 25-bps net CAGR on the full window
        cost_unit = cost_bps_for_net_cagr / 10000.0
        # Approximate cost = ann_turnover * cost_unit; deduct from each month
        if not np.isnan(ann_to):
            monthly_cost = (ann_to / 12.0) * cost_unit
            net_full = full_port - monthly_cost
            nav = (1.0 + net_full.fillna(0.0)).cumprod()
            years = max(len(net_full) / 12.0, 1e-9)
            net_cagr = float(nav.iloc[-1] ** (1.0 / years) - 1.0) if len(nav) else float("nan")
            net_sharpe = float(net_full.mean() / net_full.std(ddof=0) * np.sqrt(12)) if net_full.std(ddof=0) else float("nan")
        else:
            net_cagr = float("nan")
            net_sharpe = float("nan")

        for min_a in GRID["min_alpha"]:
            full_strong = strong_stats(full_df, "alpha_recomputed", min_a)
            buckets = alpha_bucket_hits(full_df, "alpha_recomputed",
                                        strong_min=min_a,
                                        watch_min=WATCHLIST_ALPHA_DEFAULT)
            rows.append({
                "ra_w": ra_w, "rev_w": rev_w, "flw_w": flw_w,
                "risk_mult": risk_m, "min_alpha": min_a,
                "train_sharpe":   train_m["sharpe"],
                "train_max_dd":   train_m["max_dd"],
                "train_total":    train_m["total"],
                "train_mean":     train_m["mean_monthly"],
                "test_sharpe":    test_m["sharpe"],
                "test_max_dd":    test_m["max_dd"],
                "test_total":     test_m["total"],
                "test_mean":      test_m["mean_monthly"],
                "full_sharpe":    full_m["sharpe"],
                "full_total":     full_m["total"],
                "full_max_dd":    full_m["max_dd"],
                "annualised_turnover":     ann_to,
                "net_cagr_25bps":          net_cagr,
                "net_sharpe_25bps":        net_sharpe,
                "strong_n_full":  full_strong["strong_n"],
                "strong_unique":  full_strong["strong_unique"],
                "strong_hit":     full_strong["strong_hit"],
                "strong_mean":    full_strong["strong_mean"],
                "watch_n_full":   buckets["watch_n"],
                "watch_hit_full": buckets["watch_hit"],
                "neutral_n_full": buckets["neutral_n"],
                "neutral_hit_full": buckets["neutral_hit"],
                "avoid_n_full":   buckets["avoid_n"],
                "avoid_hit_full": buckets["avoid_hit"],
            })

    grid = pd.DataFrame(rows)
    grid["robust_ratio"] = grid["test_sharpe"] / grid["train_sharpe"]
    grid["passes_robust"] = grid["robust_ratio"] >= ROBUSTNESS_THRESHOLD
    grid["passes_strong"] = grid["strong_n_full"] >= MIN_STRONG_OBS
    grid["passes_all"] = grid["passes_robust"] & grid["passes_strong"]
    # Simplicity score: count of zero weights (more zeros = simpler)
    grid["n_zero_weights"] = (
        (grid["rev_w"] == 0).astype(int)
        + (grid["flw_w"] == 0).astype(int)
    )
    return grid


# ---------------------------------------------------------------------------
# Selection

def top_combos(grid: pd.DataFrame, k: int = 10, by: str = "train_sharpe") -> pd.DataFrame:
    """Top-K combos passing all filters, ranked by ``by``."""
    survivors = grid[grid["passes_all"]].copy()
    if survivors.empty:
        # Fall back to robustness-only filter
        survivors = grid[grid["passes_robust"]].copy()
        if survivors.empty:
            return grid.sort_values(by, ascending=False).head(k)
    return survivors.sort_values(by, ascending=False).head(k)


def baseline_a1_row(grid: pd.DataFrame) -> pd.DataFrame:
    """Pull the A1 row from the grid (residual=0.35, rev=0.20, flw=0.15,
    risk_mult=1.0, min_alpha=4.0)."""
    return grid[
        (grid["ra_w"] == 0.35) & (grid["rev_w"] == 0.20) &
        (grid["flw_w"] == 0.15) & (grid["risk_mult"] == 1.0) &
        (grid["min_alpha"] == 4.0)
    ]


def write(grid: pd.DataFrame) -> pd.DataFrame:
    ensure_dir("data/output")
    path = resolve_path("data/output/weight_grid_results.csv")
    grid.to_csv(path, index=False)
    logger.info("Wrote %s (%d cells)", path, len(grid))
    return grid
