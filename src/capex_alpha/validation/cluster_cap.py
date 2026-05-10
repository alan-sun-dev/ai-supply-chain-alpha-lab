"""Phase D2 — AI-infrastructure cluster cap.

Pure backtest layer. Adds a *cluster* cap on top of the existing per-theme
cap (Step-1): no more than ``max_cluster_count`` of the top-N positions
may belong to the AI-infrastructure cluster:

    PCB substrate, LEO satellite, facility/cleanroom, thermal, AI server

Per-stress-test §8 these themes co-drawdown: the worst 5 months had 4-of-5
PCB-cluster names. The per-theme cap (max 2/theme) only constrains a
single theme; this constraint adds a cross-theme constraint.

Scope (per user mandate):
- No model / weight / scoring / gate changes
- Top-N = 5 EW unchanged
- No exposure scaling (D1 was rejected)
- Pure greedy selection refinement
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data_loader import load_universe
from ..utils import ensure_dir, get_logger, resolve_path
from . import exposure_overlay as ov  # reuse metrics_table, drawdown_episodes
from . import portfolio_metrics as pm

logger = get_logger(__name__)


# ---------------------------------------------------------------------------

CLUSTER_THEMES_DEFAULT: set[str] = {
    "pcb_substrate",
    "leo_satellite",
    "facility_cleanroom",
    "thermal",
    "ai_server_assembly",
}


def cap_pct_to_count(cap_pct: float, top_n: int) -> int:
    """Convert a fractional cap into the discrete max-count for top-N.
    Uses ``round`` so 0.50 / 0.60 / 0.70 → 2 / 3 / 4 under top-5.
    Note: floor would make 0.50 → 2 and 0.60 / 0.70 both → 3 (degenerate).
    """
    return max(0, min(top_n, int(round(cap_pct * top_n))))


# ---------------------------------------------------------------------------
# Greedy selection respecting both caps

def _pick_top_n(
    sub_sorted: pd.DataFrame, n: int, theme_map: dict | None,
    max_per_theme: int | None, cluster_themes: set[str] | None,
    max_cluster_count: int | None,
) -> list[str]:
    """Greedy top-N picker respecting per-theme cap AND cluster cap."""
    picks: list[str] = []
    theme_count: dict[str, int] = {}
    cluster_count = 0
    for _, r in sub_sorted.iterrows():
        theme = theme_map.get(r["ticker"], "unknown") if theme_map else "unknown"
        if max_per_theme is not None and theme_count.get(theme, 0) >= max_per_theme:
            continue
        if (cluster_themes is not None and max_cluster_count is not None
                and theme in cluster_themes and cluster_count >= max_cluster_count):
            continue
        picks.append(r["ticker"])
        theme_count[theme] = theme_count.get(theme, 0) + 1
        if cluster_themes is not None and theme in cluster_themes:
            cluster_count += 1
        if len(picks) >= n:
            break
    return picks


def topn_holdings_with_cluster_cap(
    df: pd.DataFrame,
    alpha_col: str = "alpha_score",
    n: int = 5,
    theme_map: dict | None = None,
    max_per_theme: int | None = 2,
    cluster_themes: set[str] | None = None,
    max_cluster_count: int | None = None,
) -> dict[pd.Timestamp, list[str]]:
    """Top-N holdings under both theme cap and cluster cap."""
    cluster_themes = cluster_themes if cluster_themes is not None else CLUSTER_THEMES_DEFAULT
    out: dict[pd.Timestamp, list[str]] = {}
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[alpha_col])
        if len(sub) < n:
            continue
        picks = _pick_top_n(sub.sort_values(alpha_col, ascending=False),
                            n, theme_map, max_per_theme,
                            cluster_themes, max_cluster_count)
        if len(picks) >= n:
            out[pd.Timestamp(t)] = picks
    return out


def topn_returns_with_cluster_cap(
    df: pd.DataFrame,
    alpha_col: str = "alpha_score",
    fwd_col: str = "fwd_return_1m",
    n: int = 5,
    theme_map: dict | None = None,
    max_per_theme: int | None = 2,
    cluster_themes: set[str] | None = None,
    max_cluster_count: int | None = None,
) -> pd.Series:
    """Equal-weight top-N monthly returns under both caps."""
    cluster_themes = cluster_themes if cluster_themes is not None else CLUSTER_THEMES_DEFAULT
    rets, dates = [], []
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[alpha_col, fwd_col])
        if len(sub) < n:
            continue
        picks = _pick_top_n(sub.sort_values(alpha_col, ascending=False),
                            n, theme_map, max_per_theme,
                            cluster_themes, max_cluster_count)
        if len(picks) < n:
            continue
        top = sub[sub["ticker"].isin(picks)]
        rets.append(float(top[fwd_col].mean()))
        dates.append(t)
    return pd.Series(rets, index=pd.DatetimeIndex(dates), name=alpha_col)


# ---------------------------------------------------------------------------
# Exposure path + upside sacrifice analysis

def cluster_exposure_path(
    holdings: dict[pd.Timestamp, list[str]],
    theme_map: dict,
    cluster_themes: set[str] = None,
) -> pd.Series:
    """Per-rebalance: fraction of top-N from cluster themes."""
    cluster_themes = cluster_themes if cluster_themes is not None else CLUSTER_THEMES_DEFAULT
    rows = []
    for date, picks in sorted(holdings.items()):
        if not picks:
            continue
        cluster_n = sum(1 for t in picks if theme_map.get(t) in cluster_themes)
        rows.append({"date": pd.Timestamp(date),
                     "cluster_weight": cluster_n / len(picks),
                     "cluster_count": cluster_n,
                     "n_holdings": len(picks)})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("date")


def upside_sacrifice(
    baseline_returns: pd.Series,
    capped_returns: pd.Series,
    ai_index_returns: pd.Series,
    momentum_threshold: float = 0.05,
) -> dict:
    """During AI-momentum months (AI index forward return > threshold), how much
    return did the cluster cap give up?"""
    common = (baseline_returns.index.intersection(capped_returns.index)
              .intersection(ai_index_returns.index))
    if common.empty:
        return {"n_months": 0}
    momentum_mask = ai_index_returns.loc[common] > momentum_threshold
    momentum_months = common[momentum_mask]
    if len(momentum_months) == 0:
        return {"n_months": 0, "threshold": momentum_threshold}

    base = baseline_returns.loc[momentum_months]
    cap = capped_returns.loc[momentum_months]
    return {
        "n_months":              int(len(momentum_months)),
        "threshold":             float(momentum_threshold),
        "baseline_mean":         float(base.mean()),
        "capped_mean":           float(cap.mean()),
        "sacrifice_per_month":   float(base.mean() - cap.mean()),
        "sacrifice_total_pct":   float((1.0 + base).prod() - (1.0 + cap).prod()),
        "baseline_total":        float((1.0 + base).prod() - 1.0),
        "capped_total":          float((1.0 + cap).prod() - 1.0),
    }


# ---------------------------------------------------------------------------
# Turnover including cluster-cap effect

def base_turnover_series(holdings: dict[pd.Timestamp, list[str]]) -> pd.Series:
    dates = sorted(holdings.keys())
    if len(dates) < 2:
        return pd.Series(dtype=float)
    series = [1.0]
    for prev, curr in zip(dates[:-1], dates[1:]):
        prev_set, curr_set = set(holdings[prev]), set(holdings[curr])
        if not curr_set:
            series.append(0.0)
            continue
        series.append(len(curr_set - prev_set) / len(curr_set))
    return pd.Series(series, index=pd.DatetimeIndex(dates), name="turnover")


# ---------------------------------------------------------------------------
# AI index forward returns aligned to rebalance dates (same logic as
# regime_stress; duplicated here so this module doesn't depend on it)

def ai_index_fwd_returns(
    ai_index_csv: str, rebalance_dates: pd.DatetimeIndex,
) -> pd.Series:
    df = pd.read_csv(resolve_path(ai_index_csv), parse_dates=["date"])
    agg = df[df["theme"] == "aggregate"].set_index("date")["theme_nav"].sort_index()
    if agg.empty:
        return pd.Series(dtype=float)
    out = {}
    sorted_dates = sorted(rebalance_dates)
    for i, t in enumerate(sorted_dates[:-1]):
        next_t = sorted_dates[i + 1]
        try:
            nav_t = float(agg.asof(t))
            nav_next = float(agg.asof(next_t))
        except Exception:
            continue
        if pd.notna(nav_t) and pd.notna(nav_next) and nav_t > 0:
            out[t] = nav_next / nav_t - 1.0
    return pd.Series(out, name="ai_fwd_1m").sort_index()


# ---------------------------------------------------------------------------
# Worst-month attribution helper

def worst_n_months(
    returns: pd.Series,
    holdings: dict[pd.Timestamp, list[str]],
    theme_map: dict,
    n: int = 5,
    cluster_themes: set[str] = None,
) -> pd.DataFrame:
    cluster_themes = cluster_themes if cluster_themes is not None else CLUSTER_THEMES_DEFAULT
    if returns.empty:
        return pd.DataFrame()
    worst = returns.sort_values().head(n)
    rows = []
    for date, ret in worst.items():
        picks = holdings.get(date, [])
        themes = [theme_map.get(t, "?") for t in picks]
        cluster_share = sum(1 for th in themes if th in cluster_themes) / max(len(themes), 1)
        rows.append({
            "month":         pd.Timestamp(date).strftime("%Y-%m"),
            "port_return":   float(ret),
            "n_holdings":    len(picks),
            "cluster_share": float(cluster_share),
            "themes":        ",".join(sorted(set(themes))),
            "tickers":       ",".join(picks),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Orchestrator

@dataclass
class VariantResult:
    label: str
    cap_pct: float
    max_cluster_count: int
    returns: pd.Series
    holdings: dict[pd.Timestamp, list[str]]


def run(
    results_csv: str = "data/output/walk_forward_v2_results.csv",
    ai_index_csv: str = "data/output/ai_factor_index.csv",
    output_dir: str = "data/output",
    cluster_themes: set[str] | None = None,
    cap_pcts: list[float] | None = None,
    top_n: int = 5,
    max_per_theme: int = 2,
    momentum_threshold: float = 0.05,
) -> dict:
    cluster_themes = cluster_themes if cluster_themes is not None else CLUSTER_THEMES_DEFAULT
    cap_pcts = cap_pcts or [0.50, 0.60, 0.70]

    results = pd.read_csv(resolve_path(results_csv), parse_dates=["rebalance_date"])
    universe = load_universe()
    theme_map = universe.set_index("ticker")["theme"].to_dict()

    # Baseline = current active baseline (theme cap on, no cluster cap)
    baseline_holdings = pm.topn_holdings(
        results, alpha_col="alpha_score", n=top_n,
        theme_map=theme_map, max_per_theme=max_per_theme,
    )
    baseline_returns = pm.topn_returns(
        results, alpha_col="alpha_score", n=top_n,
        theme_map=theme_map, max_per_theme=max_per_theme,
    )
    baseline = VariantResult("baseline (no cluster cap)", float("nan"), top_n,
                             baseline_returns, baseline_holdings)

    variants: list[VariantResult] = [baseline]
    for cap_pct in cap_pcts:
        max_count = cap_pct_to_count(cap_pct, top_n)
        label = f"cluster cap {int(cap_pct*100)}% (max {max_count} of {top_n})"
        rets = topn_returns_with_cluster_cap(
            results, alpha_col="alpha_score", n=top_n,
            theme_map=theme_map, max_per_theme=max_per_theme,
            cluster_themes=cluster_themes, max_cluster_count=max_count,
        )
        hold = topn_holdings_with_cluster_cap(
            results, alpha_col="alpha_score", n=top_n,
            theme_map=theme_map, max_per_theme=max_per_theme,
            cluster_themes=cluster_themes, max_cluster_count=max_count,
        )
        variants.append(VariantResult(label, cap_pct, max_count, rets, hold))

    # Metrics table
    summary_rows = []
    for v in variants:
        m = ov.metrics_table(v.returns, v.label)
        m["cap_pct"] = v.cap_pct
        m["max_cluster_count"] = v.max_cluster_count
        summary_rows.append(m)

    # Cost-adjusted variants
    cost_rows = []
    for v in variants:
        ts = base_turnover_series(v.holdings)
        for cost in (25.0, 50.0):
            cost_unit = cost / 10000.0
            cost_series = ts.reindex(v.returns.index).fillna(0.0) * cost_unit
            net = v.returns - cost_series
            m = ov.metrics_table(net, f"{v.label} @ {int(cost)} bps")
            m["cap_pct"] = v.cap_pct
            cost_rows.append(m)
    summary_df = pd.DataFrame(summary_rows + cost_rows)

    # Cluster exposure paths
    expo_rows = []
    for v in variants:
        path = cluster_exposure_path(v.holdings, theme_map, cluster_themes)
        if path.empty:
            continue
        path = path.copy()
        path["variant"] = v.label
        expo_rows.append(path.reset_index())
    expo_df = pd.concat(expo_rows, ignore_index=True) if expo_rows else pd.DataFrame()

    # Upside sacrifice during AI momentum months
    rebal_dates = pd.DatetimeIndex(sorted(baseline.returns.index))
    ai_fwd = ai_index_fwd_returns(ai_index_csv, rebal_dates)
    sacrifice_rows = []
    for v in variants[1:]:  # skip baseline
        s = upside_sacrifice(baseline.returns, v.returns, ai_fwd, momentum_threshold)
        s["variant"] = v.label
        sacrifice_rows.append(s)
    sacrifice_df = pd.DataFrame(sacrifice_rows)

    # Worst 5 months — baseline + each capped variant
    worst_rows = []
    for v in variants:
        wm = worst_n_months(v.returns, v.holdings, theme_map, n=5, cluster_themes=cluster_themes)
        if wm.empty:
            continue
        wm.insert(0, "variant", v.label)
        worst_rows.append(wm)
    worst_df = pd.concat(worst_rows, ignore_index=True) if worst_rows else pd.DataFrame()

    # Write outputs
    ensure_dir(output_dir)
    summary_df.to_csv(resolve_path(f"{output_dir}/phase_d2_summary.csv"), index=False)
    expo_df.to_csv(resolve_path(f"{output_dir}/phase_d2_cluster_exposure_path.csv"), index=False)
    sacrifice_df.to_csv(resolve_path(f"{output_dir}/phase_d2_upside_sacrifice.csv"), index=False)
    worst_df.to_csv(resolve_path(f"{output_dir}/phase_d2_worst_months.csv"), index=False)
    logger.info("Wrote 4 Phase D2 CSVs to %s/", output_dir)

    return {
        "summary": summary_df,
        "cluster_exposure": expo_df,
        "upside_sacrifice": sacrifice_df,
        "worst_months": worst_df,
        "variants": variants,
        "ai_fwd": ai_fwd,
    }
