"""Phase B1 — transaction-cost simulator on top of A2 walk-forward results.

Cost convention (per spec)
--------------------------
- ``one_way_turnover`` = fraction of the equal-weight top-N portfolio that
  changed names since the previous rebalance.  For top-5 EW, two replaced
  names → 2 / 5 = 40%.
- ``one_way_cost_bps`` = cost charged per unit of one-way turnover, expressed
  in basis points of portfolio NAV.
- ``monthly_cost = one_way_turnover * one_way_cost_bps / 10000``.

This convention treats the cost as a single round-trip charge per *fraction of
portfolio rotated*, not as a separate buy + sell leg.  For a fully-invested
portfolio that doesn't change net allocation, buy% ≡ sell%, so this captures
cost per rebalanced slot rather than per leg.  To compare against published
broker fee schedules:

- Taiwan retail (commission 0.1425% / side max + 0.30% sell tax + slippage):
  full real-world round-trip ≈ 60-90 bps in this spec's units.
- Discount broker / institutional: ≈ 25-50 bps.

Initial-month turnover convention
---------------------------------
The first rebalance has no prior holdings → 100% turnover (full deployment
from cash).  We charge it as ``initial_position_turnover``; the report calls
this out so the reader can subtract it if comparing to other studies that
exclude initial deployment.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from ..utils import ensure_dir, get_logger, resolve_path
from . import portfolio_metrics as pm

logger = get_logger(__name__)


DEFAULT_COSTS_BPS: list[int] = [0, 10, 25, 50, 100]


# ---------------------------------------------------------------------------
# Turnover

def equal_weight_top_n_holdings(
    df: pd.DataFrame,
    alpha_col: str = "alpha_score",
    n: int = 5,
    theme_map: dict | None = None,
    max_per_theme: int | None = None,
) -> dict[pd.Timestamp, list[str]]:
    """Wrap ``pm.topn_holdings`` — kept here so callers don't need to import pm."""
    return pm.topn_holdings(df, alpha_col=alpha_col, n=n,
                            theme_map=theme_map, max_per_theme=max_per_theme)


def turnover_series_from_holdings(
    holdings: dict[pd.Timestamp, list[str]],
    charge_initial: bool = True,
) -> pd.Series:
    """Per-rebalance one-way turnover, indexed by rebalance date.

    Initial month: 100% turnover (cash → fully invested) iff
    ``charge_initial`` is True; otherwise 0.
    """
    dates = sorted(holdings.keys())
    if not dates:
        return pd.Series(dtype=float, name="turnover")

    rows = []
    for i, d in enumerate(dates):
        if i == 0:
            t = 1.0 if charge_initial else 0.0
        else:
            prev = set(holdings[dates[i - 1]])
            curr = set(holdings[d])
            t = len(curr - prev) / len(curr) if curr else 0.0
        rows.append((d, t))
    s = pd.Series(
        [t for _, t in rows],
        index=pd.DatetimeIndex([d for d, _ in rows]),
        name="turnover",
    )
    return s


def turnover_from_weight_panel(weights_wide: pd.DataFrame) -> pd.Series:
    """Generic ``0.5 * L1`` turnover from a wide DataFrame indexed by date,
    columns = tickers, values = portfolio weights.

    For equal-weight top-N portfolios this reduces to fraction-of-slots-changed.
    First row is treated as the initial-position cost = sum(|weights|).
    """
    if weights_wide.empty:
        return pd.Series(dtype=float, name="turnover")
    diff = weights_wide.fillna(0.0).diff().abs().sum(axis=1) * 0.5
    diff.iloc[0] = weights_wide.iloc[0].fillna(0.0).abs().sum()
    diff.name = "turnover"
    return diff


# ---------------------------------------------------------------------------
# Cost application

def apply_costs(
    gross_returns: pd.Series,
    turnover: pd.Series,
    cost_bps: float,
) -> tuple[pd.Series, pd.Series]:
    """Return ``(net_returns, monthly_cost)``.

    ``monthly_cost_t = turnover_t * (cost_bps / 10000)``.  Aligned by index
    (left-joined on the gross-returns dates).
    """
    cost_unit = cost_bps / 10000.0
    monthly_cost = (turnover.reindex(gross_returns.index).fillna(0.0) * cost_unit)
    monthly_cost.name = "monthly_cost"
    net = (gross_returns - monthly_cost).rename("net_return")
    return net, monthly_cost


# ---------------------------------------------------------------------------
# Single-scenario simulation

def simulate_scenario(
    df: pd.DataFrame,
    benchmark_returns: pd.Series,
    cost_bps: float,
    n: int = 5,
    alpha_col: str = "alpha_score",
    fwd_col: str = "fwd_return_1m",
    charge_initial: bool = True,
    theme_map: dict | None = None,
    max_per_theme: int | None = None,
) -> tuple[dict, pd.DataFrame]:
    """Run one cost scenario.

    Returns ``(metrics_dict, per_month_dataframe)``.  ``df`` should be the
    walk_forward_v2_results.csv long-format frame.  ``benchmark_returns`` is
    a date-indexed series of 1-month forward benchmark returns.

    ``theme_map`` + ``max_per_theme`` apply the Step-1 portfolio-construction
    theme cap (if both provided).
    """
    holdings = equal_weight_top_n_holdings(
        df, alpha_col=alpha_col, n=n,
        theme_map=theme_map, max_per_theme=max_per_theme,
    )
    turnover = turnover_series_from_holdings(holdings, charge_initial=charge_initial)
    gross = pm.topn_returns(df, alpha_col=alpha_col, fwd_col=fwd_col, n=n,
                            theme_map=theme_map, max_per_theme=max_per_theme)
    net, monthly_cost = apply_costs(gross, turnover, cost_bps)

    common = gross.index.intersection(turnover.index)
    if common.empty:
        return {"cost_bps": cost_bps}, pd.DataFrame()

    gross = gross.loc[common]
    net = net.loc[common]
    turnover = turnover.loc[common]
    monthly_cost = monthly_cost.loc[common]
    bench = benchmark_returns.reindex(common).fillna(0.0)

    gross_nav = (1.0 + gross.fillna(0.0)).cumprod()
    net_nav = (1.0 + net.fillna(0.0)).cumprod()
    bench_nav = (1.0 + bench).cumprod()

    metrics = {
        "cost_bps":             float(cost_bps),
        "total_return":         float(net_nav.iloc[-1] - 1.0),
        "cagr":                 pm.cagr(net),
        "annual_volatility":    float(net.std(ddof=0) * np.sqrt(12)),
        "sharpe":               pm.sharpe(net),
        "max_drawdown":         pm.max_drawdown(net),
        "monthly_hit_rate":     pm.monthly_hit_rate(net),
        "avg_monthly_return":   float(net.mean()),
        "avg_monthly_turnover": float(turnover.mean()),
        "annualized_turnover":  float(turnover.mean() * 12.0),
        "net_alpha_vs_benchmark": pm.cagr(net) - pm.cagr(bench),
        "cost_drag_per_year":   float(monthly_cost.sum() / max(len(monthly_cost) / 12.0, 1e-9)),
        "final_nav":            float(net_nav.iloc[-1]),
    }

    series = pd.DataFrame({
        "date":                  common,
        "gross_portfolio_return": gross.values,
        "benchmark_return":      bench.values,
        "turnover":              turnover.values,
        "cost_bps":              float(cost_bps),
        "monthly_cost":          monthly_cost.values,
        "net_portfolio_return":  net.values,
        "gross_nav":             gross_nav.values,
        "net_nav":               net_nav.values,
        "benchmark_nav":         bench_nav.values,
        "gross_excess_nav":      (gross_nav - bench_nav).values,
        "net_excess_nav":        (net_nav - bench_nav).values,
    })

    return metrics, series


# ---------------------------------------------------------------------------
# Break-even

def break_even_cost(
    df: pd.DataFrame,
    benchmark_returns: pd.Series,
    n: int = 5,
    alpha_col: str = "alpha_score",
    fwd_col: str = "fwd_return_1m",
    charge_initial: bool = True,
    tol: float = 1e-4,
    max_iter: int = 50,
    theme_map: dict | None = None,
    max_per_theme: int | None = None,
) -> float:
    """Binary-search the one-way cost (bps) where net_cagr ≈ benchmark_cagr.

    Returns:
    - finite bps when a break-even exists in the searched range
    - ``+inf`` if the strategy beats benchmark even at 10,000 bps
    - ``nan`` if the strategy fails to beat benchmark even at 0 bps
    """
    common_index = pm.topn_returns(df, alpha_col=alpha_col, fwd_col=fwd_col, n=n,
                                   theme_map=theme_map, max_per_theme=max_per_theme).index
    bench_aligned = benchmark_returns.reindex(common_index).fillna(0.0)
    bench_cagr = pm.cagr(bench_aligned)

    def net_cagr_at(cost: float) -> float:
        m, _ = simulate_scenario(
            df, benchmark_returns, cost, n=n,
            alpha_col=alpha_col, fwd_col=fwd_col,
            charge_initial=charge_initial,
            theme_map=theme_map, max_per_theme=max_per_theme,
        )
        return m["cagr"]

    if net_cagr_at(0.0) <= bench_cagr:
        return float("nan")

    lo, hi = 0.0, 1000.0
    if net_cagr_at(hi) > bench_cagr:
        # Expand the upper bound aggressively.
        for hi_candidate in (2000.0, 5000.0, 10000.0):
            if net_cagr_at(hi_candidate) <= bench_cagr:
                hi = hi_candidate
                break
        else:
            return float("inf")

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        c = net_cagr_at(mid)
        if abs(c - bench_cagr) < tol:
            return float(mid)
        if c > bench_cagr:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


# ---------------------------------------------------------------------------
# End-to-end runner

def run(
    df: pd.DataFrame,
    benchmark_returns: pd.Series,
    costs_bps: Iterable[float] = tuple(DEFAULT_COSTS_BPS),
    n: int = 5,
    alpha_col: str = "alpha_score",
    fwd_col: str = "fwd_return_1m",
    output_dir: str = "data/output",
    write: bool = True,
    theme_map: dict | None = None,
    max_per_theme: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Run all scenarios + break-even; return ``(summary_df, nav_df, break_even_bps)``."""
    summaries: list[dict] = []
    nav_frames: list[pd.DataFrame] = []
    for cost in costs_bps:
        m, s = simulate_scenario(df, benchmark_returns, cost, n=n,
                                 alpha_col=alpha_col, fwd_col=fwd_col,
                                 theme_map=theme_map, max_per_theme=max_per_theme)
        summaries.append(m)
        nav_frames.append(s)

    summary_df = pd.DataFrame(summaries)
    nav_df = pd.concat(nav_frames, ignore_index=True)

    be = break_even_cost(df, benchmark_returns, n=n, alpha_col=alpha_col, fwd_col=fwd_col,
                          theme_map=theme_map, max_per_theme=max_per_theme)
    summary_df["break_even_cost_bps"] = be

    if write:
        ensure_dir(output_dir)
        summary_df.to_csv(resolve_path(f"{output_dir}/transaction_cost_summary.csv"), index=False)
        nav_df.to_csv(resolve_path(f"{output_dir}/transaction_cost_nav.csv"), index=False)
        logger.info("Wrote transaction_cost_summary.csv (%d rows)", len(summary_df))
        logger.info("Wrote transaction_cost_nav.csv (%d rows)", len(nav_df))

    return summary_df, nav_df, be
