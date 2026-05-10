"""Out-of-regime stress test.

Analysis-only module — does NOT change the active model, weights, or scoring
logic. Consumes the existing ``walk_forward_v2_results.csv``, benchmark
forward returns, and ``ai_factor_index.csv`` to produce regime-conditional
performance breakdowns.

Two flavors of "regime":
- **Calendar regimes** — fixed windows like "2022 bear", "2024 AI mania"
- **Event regimes** — month sets defined by data conditions (high vol,
  drawdown periods, benchmark/AI underperform months)

Plus three diagnostic exhibits:
- worst / best 5 months with holdings + risk-flag attribution
- risk_penalty effectiveness per regime (rebuild alpha with vs without)
- top-5 turnover per regime
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data_loader import load_universe
from ..utils import ensure_dir, get_logger, resolve_path
from . import portfolio_metrics as pm

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Regime definitions

CALENDAR_REGIMES: list[tuple[str, str, str]] = [
    ("2020 COVID rebound",     "2020-06-30", "2020-12-31"),
    ("2021 liquidity bull",    "2021-01-01", "2021-12-31"),
    ("2022 bear / rate hike",  "2022-01-01", "2022-12-31"),
    ("2023 AI recovery",       "2023-01-01", "2023-12-31"),
    ("2024 AI mania",          "2024-01-01", "2024-12-31"),
    ("2025 AI mania",          "2025-01-01", "2025-12-31"),
    ("2026 YTD",               "2026-01-01", "2026-04-30"),
    ("Pre-AI mania (≤2022-12)", "2020-06-30", "2022-12-31"),
    ("AI era (2023-2026)",     "2023-01-01", "2026-04-30"),
]


# ---------------------------------------------------------------------------
# Series builders

def build_portfolio_returns(
    results: pd.DataFrame,
    theme_map: dict | None,
    max_per_theme: int | None = 2,
    n: int = 5,
    alpha_col: str = "alpha_score",
) -> pd.Series:
    """Top-N EW (with theme cap) monthly returns from walk-forward results."""
    return pm.topn_returns(
        results, alpha_col=alpha_col, n=n,
        theme_map=theme_map, max_per_theme=max_per_theme,
    )


def build_benchmark_series(benchmark_csv_path: str) -> pd.Series:
    df = pd.read_csv(resolve_path(benchmark_csv_path), parse_dates=["rebalance_date"])
    return df.set_index("rebalance_date")["benchmark_fwd_1m"].sort_index()


def build_ai_index_fwd_returns(
    ai_index_csv_path: str,
    rebalance_dates: pd.DatetimeIndex,
) -> pd.Series:
    """Aggregate AI index forward 1m return aligned to rebalance dates."""
    df = pd.read_csv(resolve_path(ai_index_csv_path), parse_dates=["date"])
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


def rebuild_alpha_no_risk(results: pd.DataFrame) -> pd.Series:
    """Recompute alpha_score with risk_penalty subtraction *removed* —
    used to measure risk_penalty's drawdown-control effectiveness."""
    return results["alpha_score"] + results["risk_penalty"]


# ---------------------------------------------------------------------------
# Per-window metrics

@dataclass
class RegimeMetrics:
    name: str
    n_months: int
    cagr: float
    sharpe: float
    max_dd: float
    monthly_hit_rate: float
    total_return: float
    mean_monthly: float
    benchmark_total: float
    benchmark_cagr: float
    ai_index_total: float
    ai_index_cagr: float
    excess_vs_benchmark_total: float
    excess_vs_ai_total: float
    avg_one_way_turnover: float

    def as_row(self) -> dict:
        return {**self.__dict__}


def _slice_window(s: pd.Series, start: str, end: str) -> pd.Series:
    return s.loc[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]


def _window_total(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    return float((1.0 + returns.fillna(0.0)).prod() - 1.0)


def _avg_turnover_in_window(holdings: dict[pd.Timestamp, list[str]],
                            start: str, end: str) -> float:
    dates = [d for d in sorted(holdings) if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    if len(dates) < 2:
        return float("nan")
    changes = []
    for prev, curr in zip(dates[:-1], dates[1:]):
        prev_set, curr_set = set(holdings[prev]), set(holdings[curr])
        if not curr_set:
            continue
        changes.append(len(curr_set - prev_set) / len(curr_set))
    return float(np.mean(changes)) if changes else float("nan")


def regime_breakdown(
    portfolio: pd.Series,
    benchmark: pd.Series,
    ai_index: pd.Series,
    holdings: dict[pd.Timestamp, list[str]],
    regimes: list[tuple[str, str, str]] = None,
) -> pd.DataFrame:
    """Per-regime portfolio + benchmark + AI-index metrics."""
    regimes = regimes or CALENDAR_REGIMES
    rows = []
    for name, start, end in regimes:
        sub = _slice_window(portfolio, start, end)
        if sub.empty:
            continue
        bench = _slice_window(benchmark, start, end).reindex(sub.index).fillna(0.0)
        ai = _slice_window(ai_index, start, end).reindex(sub.index).fillna(0.0)
        m = RegimeMetrics(
            name=name,
            n_months=int(len(sub)),
            cagr=pm.cagr(sub),
            sharpe=pm.sharpe(sub),
            max_dd=pm.max_drawdown(sub),
            monthly_hit_rate=pm.monthly_hit_rate(sub),
            total_return=_window_total(sub),
            mean_monthly=float(sub.mean()),
            benchmark_total=_window_total(bench),
            benchmark_cagr=pm.cagr(bench),
            ai_index_total=_window_total(ai),
            ai_index_cagr=pm.cagr(ai),
            excess_vs_benchmark_total=_window_total(sub) - _window_total(bench),
            excess_vs_ai_total=_window_total(sub) - _window_total(ai),
            avg_one_way_turnover=_avg_turnover_in_window(holdings, start, end),
        )
        rows.append(m.as_row())
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Event-conditional regimes

def event_breakdown(
    portfolio: pd.Series,
    benchmark: pd.Series,
    ai_index: pd.Series,
    high_vol_quantile: float = 0.80,
    dd_threshold: float = -0.05,
) -> pd.DataFrame:
    """Conditional regimes defined by data:
    - high-volatility months (rolling 3m std ≥ q)
    - drawdown periods (NAV < 95% of cummax)
    - benchmark-underperform months (port < bench)
    - AI-index-underperform months (port < ai)
    """
    rows = []

    rolling_std = portfolio.rolling(3, min_periods=2).std()
    threshold = rolling_std.quantile(high_vol_quantile)
    high_vol_mask = rolling_std >= threshold
    rows.append(_event_row("High-vol months (top 20% rolling 3m std)",
                            portfolio[high_vol_mask], benchmark, ai_index))

    nav = (1.0 + portfolio.fillna(0.0)).cumprod()
    in_dd_mask = nav < nav.cummax() * (1.0 + dd_threshold)
    rows.append(_event_row("Drawdown periods (NAV ≤ 95% of peak)",
                            portfolio[in_dd_mask], benchmark, ai_index))

    underperform_bench = portfolio < benchmark.reindex(portfolio.index).fillna(0.0)
    rows.append(_event_row("0050 underperform months (port < bench)",
                            portfolio[underperform_bench], benchmark, ai_index))

    ai_aligned = ai_index.reindex(portfolio.index).fillna(0.0)
    underperform_ai = portfolio < ai_aligned
    rows.append(_event_row("AI-index underperform months (port < AI agg)",
                            portfolio[underperform_ai], benchmark, ai_index))

    return pd.DataFrame(rows)


def _event_row(name: str, sub: pd.Series, benchmark: pd.Series, ai_index: pd.Series) -> dict:
    if sub.empty:
        return {"event_regime": name, "n_months": 0,
                "mean_monthly": float("nan"), "hit_rate": float("nan"),
                "total_return": float("nan"),
                "vs_benchmark": float("nan"), "vs_ai_index": float("nan")}
    bench = benchmark.reindex(sub.index).fillna(0.0)
    ai = ai_index.reindex(sub.index).fillna(0.0)
    return {
        "event_regime":   name,
        "n_months":       int(len(sub)),
        "mean_monthly":   float(sub.mean()),
        "hit_rate":       float((sub > 0).mean()),
        "total_return":   _window_total(sub),
        "vs_benchmark":   _window_total(sub) - _window_total(bench),
        "vs_ai_index":    _window_total(sub) - _window_total(ai),
    }


# ---------------------------------------------------------------------------
# Worst / best month attribution

def worst_best_months(
    portfolio: pd.Series,
    holdings: dict[pd.Timestamp, list[str]],
    results: pd.DataFrame,
    risk_flags_csv: str | None = None,
    benchmark: pd.Series | None = None,
    n: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (worst_n, best_n) DataFrames with holdings + ticker-level fwd returns."""
    if portfolio.empty:
        return pd.DataFrame(), pd.DataFrame()
    sorted_returns = portfolio.sort_values()
    worst = sorted_returns.head(n)
    best = sorted_returns.tail(n).iloc[::-1]

    universe_themes = load_universe().set_index("ticker")["theme"].to_dict()

    def _enrich(month_series: pd.Series) -> pd.DataFrame:
        rows = []
        results_idx = results.set_index(["rebalance_date", "ticker"]) if not results.empty else pd.DataFrame()
        for date, port_ret in month_series.items():
            tickers = holdings.get(date, [])
            if not results_idx.empty:
                fwd_per = []
                for t in tickers:
                    try:
                        row = results_idx.loc[(date, t)]
                        fwd_per.append((t, universe_themes.get(t, "?"),
                                        float(row["fwd_return_1m"]) if pd.notna(row.get("fwd_return_1m")) else float("nan"),
                                        float(row["alpha_score"]) if pd.notna(row.get("alpha_score")) else float("nan"),
                                        float(row.get("risk_penalty", 0))))
                    except KeyError:
                        fwd_per.append((t, universe_themes.get(t, "?"), float("nan"), float("nan"), float("nan")))
                fwd_str = "; ".join(
                    f"{t}({theme[:8]}): fwd={fwd*100:+.1f}%, α={a:.2f}, rp={rp:.2f}"
                    for t, theme, fwd, a, rp in fwd_per
                )
            else:
                fwd_str = "; ".join(tickers)
            bench_val = float(benchmark.loc[date]) if benchmark is not None and date in benchmark.index else float("nan")
            rows.append({
                "month":           pd.Timestamp(date).strftime("%Y-%m"),
                "port_return":     float(port_ret),
                "benchmark_return": bench_val,
                "vs_benchmark":    float(port_ret) - bench_val if pd.notna(bench_val) else float("nan"),
                "n_holdings":      len(tickers),
                "themes":          ",".join(sorted({universe_themes.get(t, "?") for t in tickers})),
                "holdings_detail": fwd_str,
            })
        return pd.DataFrame(rows)

    return _enrich(worst), _enrich(best)


# ---------------------------------------------------------------------------
# Risk-penalty effectiveness per regime

def risk_penalty_effect(
    results: pd.DataFrame,
    theme_map: dict,
    max_per_theme: int = 2,
    n: int = 5,
    regimes: list[tuple[str, str, str]] = None,
) -> pd.DataFrame:
    """Compare two strategies per regime:
    - **with_risk** (current): top-5 by alpha_score (which includes -risk_penalty)
    - **no_risk**: top-5 by (alpha_score + risk_penalty) — i.e. risk subtraction undone

    A useful gauge of whether the risk_penalty is buying real DD protection.
    """
    regimes = regimes or CALENDAR_REGIMES

    df = results.copy()
    df["alpha_no_risk"] = rebuild_alpha_no_risk(df)

    port_with = pm.topn_returns(df, alpha_col="alpha_score", n=n,
                                theme_map=theme_map, max_per_theme=max_per_theme)
    port_no = pm.topn_returns(df, alpha_col="alpha_no_risk", n=n,
                              theme_map=theme_map, max_per_theme=max_per_theme)

    rows = []
    for name, start, end in regimes:
        sub_w = _slice_window(port_with, start, end)
        sub_n = _slice_window(port_no, start, end)
        if sub_w.empty or sub_n.empty:
            continue
        rows.append({
            "regime":            name,
            "n_months":          int(len(sub_w)),
            "with_risk_cagr":    pm.cagr(sub_w),
            "no_risk_cagr":      pm.cagr(sub_n),
            "with_risk_sharpe":  pm.sharpe(sub_w),
            "no_risk_sharpe":    pm.sharpe(sub_n),
            "with_risk_max_dd":  pm.max_drawdown(sub_w),
            "no_risk_max_dd":    pm.max_drawdown(sub_n),
            "dd_improvement_pts": pm.max_drawdown(sub_w) - pm.max_drawdown(sub_n),
            "cagr_cost_pts":     pm.cagr(sub_n) - pm.cagr(sub_w),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Residual-alpha standalone behaviour

def residual_alpha_per_regime(
    results: pd.DataFrame,
    theme_map: dict,
    max_per_theme: int = 2,
    n: int = 5,
    regimes: list[tuple[str, str, str]] = None,
) -> pd.DataFrame:
    """Top-5 by `residual_alpha_score` only (rebuilt alpha = pure tier1).
    Used to ask: does residual alpha still work outside AI mania?"""
    regimes = regimes or CALENDAR_REGIMES
    df = results.copy()
    port = pm.topn_returns(df, alpha_col="residual_alpha_score", n=n,
                           theme_map=theme_map, max_per_theme=max_per_theme)
    rows = []
    for name, start, end in regimes:
        sub = _slice_window(port, start, end)
        if sub.empty:
            continue
        rows.append({
            "regime":           name,
            "n_months":         int(len(sub)),
            "cagr":             pm.cagr(sub),
            "sharpe":           pm.sharpe(sub),
            "max_dd":           pm.max_drawdown(sub),
            "monthly_hit_rate": pm.monthly_hit_rate(sub),
            "mean_monthly":     float(sub.mean()),
            "total_return":     _window_total(sub),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Orchestrator

def run(
    results_csv: str = "data/output/walk_forward_v2_results.csv",
    benchmark_csv: str = "data/output/walk_forward_v2_benchmark.csv",
    ai_index_csv: str = "data/output/ai_factor_index.csv",
    risk_flags_csv: str = "data/output/risk_flags.csv",
    output_dir: str = "data/output",
    max_per_theme: int = 2,
    top_n: int = 5,
) -> dict:
    """End-to-end stress test; returns dict of frames + writes CSVs."""
    results = pd.read_csv(resolve_path(results_csv), parse_dates=["rebalance_date"])
    benchmark = build_benchmark_series(benchmark_csv)
    rebal_dates = pd.DatetimeIndex(sorted(benchmark.index))
    ai_index = build_ai_index_fwd_returns(ai_index_csv, rebal_dates)

    universe = load_universe()
    theme_map = universe.set_index("ticker")["theme"].to_dict()
    portfolio = build_portfolio_returns(results, theme_map, max_per_theme=max_per_theme, n=top_n)
    holdings = pm.topn_holdings(results, n=top_n, theme_map=theme_map, max_per_theme=max_per_theme)

    cal = regime_breakdown(portfolio, benchmark, ai_index, holdings)
    evt = event_breakdown(portfolio, benchmark, ai_index)
    worst, best = worst_best_months(portfolio, holdings, results, benchmark=benchmark)
    rp_effect = risk_penalty_effect(results, theme_map, max_per_theme=max_per_theme, n=top_n)
    ra_only = residual_alpha_per_regime(results, theme_map, max_per_theme=max_per_theme, n=top_n)

    ensure_dir(output_dir)
    cal.to_csv(resolve_path(f"{output_dir}/regime_calendar.csv"), index=False)
    evt.to_csv(resolve_path(f"{output_dir}/regime_event.csv"), index=False)
    worst.to_csv(resolve_path(f"{output_dir}/regime_worst_months.csv"), index=False)
    best.to_csv(resolve_path(f"{output_dir}/regime_best_months.csv"), index=False)
    rp_effect.to_csv(resolve_path(f"{output_dir}/regime_risk_penalty_effect.csv"), index=False)
    ra_only.to_csv(resolve_path(f"{output_dir}/regime_residual_alpha_only.csv"), index=False)

    logger.info("Wrote 6 regime-stress CSVs to %s/", output_dir)

    return {
        "calendar": cal, "event": evt,
        "worst": worst, "best": best,
        "risk_penalty_effect": rp_effect,
        "residual_alpha_only": ra_only,
        "portfolio": portfolio,
        "benchmark": benchmark,
        "ai_index": ai_index,
    }
