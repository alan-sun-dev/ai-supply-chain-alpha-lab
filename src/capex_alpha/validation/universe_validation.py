"""Phase C — universe-level backtest comparison.

For each universe variant we:
1. Set the universe override → load_universe() now returns that CSV.
2. Re-build AI factor index from the new universe (so residual alpha is
   measured against an "expanded-universe AI beta" benchmark).
3. Re-compute residual alpha (rolling regression vs market + new AI index).
4. Run the v2 walk-forward (PIT-correct) over the same monthly rebalance
   schedule.
5. Compute portfolio metrics (top-5 EW), concentration, theme exposure,
   per-zone label stats, transaction-cost-aware metrics from B1.

Note on data coverage
---------------------
Phase C does NOT backfill FinMind data (revenue / institutional flow /
valuation) for the new tickers — that's Phase B2/B3.  For new tickers
those columns will be NaN/0, so:
- ``revenue_acceleration`` factor is 0 for new names
- ``institutional_flow_score`` is 0
- ``valuation_risk_score`` is 0 (penalty)
- New tickers rank primarily by ``residual_alpha_score`` — which we already
  showed is the dominant signal in A1/A2 ablation.

This is a *deliberate* design choice for the PoC.  The report flags it.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data_loader import set_universe_override
from ..quant import ai_factor_index as afi
from ..quant import residual_alpha as ra
from ..utils import ensure_dir, get_logger, resolve_path
from . import portfolio_metrics as pm
from . import transaction_cost as tc
from . import walk_forward_v2 as wf

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Universe override context manager

@contextmanager
def universe_context(path: str | None):
    """Set ``load_universe`` override for the duration of the block.

    Also clears the AI-factor-index / residual-alpha caches by passing
    fresh inputs in the calling code (this CM only handles the override).
    """
    set_universe_override(path)
    try:
        yield
    finally:
        set_universe_override(None)


# ---------------------------------------------------------------------------
# Single-universe backtest

@dataclass
class UniverseRunResult:
    universe_name: str
    num_stocks: int
    walk_forward: pd.DataFrame   # long-format from wf.run
    benchmark:    pd.Series       # 1m fwd benchmark return per rebalance


def run_universe(
    universe_path: str | None,
    universe_name: str,
    start: str = "2020-06-30",
    end: str | pd.Timestamp | None = None,
) -> UniverseRunResult:
    """Run the full v2 walk-forward against a given universe CSV."""
    with universe_context(universe_path):
        # Force fresh build so caches don't poison the run
        from ..data_loader import load_universe
        u = load_universe()
        n = int((u["ticker"] != "2330.TW").sum())  # exclude issuer from rankings
        logger.info("[universe=%s] %d ranked tickers", universe_name, n)

        out = wf.run(start=start, end=end, write=False, progress=False)

    bench = out.get("benchmark", pd.Series(dtype=float))
    return UniverseRunResult(
        universe_name=universe_name,
        num_stocks=n,
        walk_forward=out["results"],
        benchmark=bench,
    )


# ---------------------------------------------------------------------------
# Per-universe analytics

def concentration_metrics(
    df: pd.DataFrame, n: int = 5, alpha_col: str = "alpha_score",
    theme_map: dict | None = None, max_per_theme: int | None = None,
) -> dict:
    """Top-5 portfolio concentration: how many distinct tickers ever appeared."""
    holdings = pm.topn_holdings(df, alpha_col=alpha_col, n=n,
                                theme_map=theme_map, max_per_theme=max_per_theme)
    if not holdings:
        return {"top5_concentration": np.nan, "unique_holdings_count": 0}
    universe_size = df["ticker"].nunique()
    n_unique = len({t for hs in holdings.values() for t in hs})
    return {
        "top5_concentration": float(n / universe_size) if universe_size else np.nan,
        "unique_holdings_count": n_unique,
    }


def theme_exposure_per_rebalance(
    df: pd.DataFrame, universe_df: pd.DataFrame, n: int = 5,
    alpha_col: str = "alpha_score",
    theme_map: dict | None = None, max_per_theme: int | None = None,
) -> pd.DataFrame:
    """Per-rebalance theme weights for the top-N portfolio."""
    holdings = pm.topn_holdings(df, alpha_col=alpha_col, n=n,
                                theme_map=theme_map, max_per_theme=max_per_theme)
    if not holdings:
        return pd.DataFrame(columns=["date", "theme", "weight", "num_holdings"])

    theme_map = universe_df.set_index("ticker")["theme"].to_dict()
    rows: list[dict] = []
    for d, tickers in holdings.items():
        themes = [theme_map.get(t, "unknown") for t in tickers]
        c = Counter(themes)
        total = sum(c.values())
        for theme, count in c.items():
            rows.append({
                "date":          pd.Timestamp(d),
                "theme":         theme,
                "weight":        count / total if total else 0.0,
                "num_holdings":  count,
            })
    return pd.DataFrame(rows)


def max_theme_exposure(theme_exposure: pd.DataFrame) -> float:
    """Highest single-theme weight observed across all rebalances."""
    if theme_exposure.empty:
        return float("nan")
    return float(theme_exposure["weight"].max())


def label_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Per-decision-zone hit rate / mean fwd return for one universe."""
    sub = df.dropna(subset=["fwd_return_1m"]).copy()
    if sub.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    for zone, g in sub.groupby("decision_zone"):
        rows.append({
            "decision_zone":           zone,
            "n_obs":                   int(len(g)),
            "n_unique_tickers":        int(g["ticker"].nunique()),
            "hit_rate":                float((g["fwd_return_1m"] > 0).mean()),
            "mean_forward_1m_return":  float(g["fwd_return_1m"].mean()),
            "median_forward_1m_return": float(g["fwd_return_1m"].median()),
            "avg_alpha_score":         float(g["alpha_score"].mean()),
            "avg_confidence_score":    float(g["confidence_score"].mean()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Multi-universe driver

def run_universe_panel(
    universe_specs: list[tuple[str, str | None]],
    start: str = "2020-06-30",
    end: str | pd.Timestamp | None = None,
    cost_scenarios_bps: list[float] | None = None,
    top_n: int = 5,
    apply_theme_cap: bool = True,
) -> dict:
    """Run all universe variants + assemble cross-universe summary.

    ``universe_specs`` is a list of ``(name, path_or_None)``. ``None`` path
    means "use the default ``config/universe.yaml`` setting".
    """
    cost_scenarios_bps = cost_scenarios_bps or [25.0, 50.0, 100.0]

    runs: dict[str, UniverseRunResult] = {}
    for name, path in universe_specs:
        logger.info("=== universe: %s (path=%s) ===", name, path)
        runs[name] = run_universe(path, name, start=start, end=end)

    # Build summary table
    summary_rows: list[dict] = []
    holdings_rows: list[dict] = []
    nav_rows: list[dict] = []
    theme_rows: list[dict] = []
    label_rows: list[dict] = []

    for name, res in runs.items():
        if res.walk_forward.empty:
            logger.warning("[%s] no walk-forward results.", name)
            continue
        df = res.walk_forward
        with universe_context(_path_for(name, universe_specs)):
            from ..data_loader import load_universe
            universe_df = load_universe()
        universe_df = universe_df[universe_df["ticker"] != "2330.TW"]

        # Step-1: theme cap kwargs from this universe
        theme_map = universe_df.set_index("ticker")["theme"].to_dict()
        cap_kwargs = pm.theme_cap_kwargs(theme_map) if apply_theme_cap else {"theme_map": None, "max_per_theme": None}

        conc = concentration_metrics(df, n=top_n, **cap_kwargs)
        theme_exp = theme_exposure_per_rebalance(df, universe_df, n=top_n, **cap_kwargs)
        theme_exp.insert(1, "universe_name", name)
        theme_rows.append(theme_exp)

        labels = label_stats(df)
        labels.insert(0, "universe_name", name)
        label_rows.append(labels)

        # Holdings detail per rebalance
        holdings = pm.topn_holdings(df, n=top_n, **cap_kwargs)
        for d, tks in holdings.items():
            for rank_, t in enumerate(tks, 1):
                holdings_rows.append({
                    "universe_name": name, "date": pd.Timestamp(d),
                    "rank": rank_, "ticker": t,
                })

        # Per-cost summary
        for cost in cost_scenarios_bps:
            metrics, series = tc.simulate_scenario(df, res.benchmark, cost_bps=cost, n=top_n,
                                                   **cap_kwargs)
            # NAV time series
            for _, row in series.iterrows():
                nav_rows.append({
                    "universe_name": name, "cost_bps": cost,
                    "date":          row["date"],
                    "gross_return":  row["gross_portfolio_return"],
                    "net_return":    row["net_portfolio_return"],
                    "benchmark_return": row["benchmark_return"],
                    "turnover":      row["turnover"],
                    "monthly_cost":  row["monthly_cost"],
                    "gross_nav":     row["gross_nav"],
                    "net_nav":       row["net_nav"],
                    "benchmark_nav": row["benchmark_nav"],
                })

            strong = labels[labels["decision_zone"] == "Strong Candidate"]
            watch  = labels[labels["decision_zone"] == "Watchlist"]
            summary_rows.append({
                "universe_name":            name,
                "num_stocks":               res.num_stocks,
                "cost_bps":                 cost,
                "cagr":                     metrics["cagr"],
                "sharpe":                   metrics["sharpe"],
                "max_drawdown":             metrics["max_drawdown"],
                "monthly_hit_rate":         metrics["monthly_hit_rate"],
                "avg_monthly_turnover":     metrics["avg_monthly_turnover"],
                "annualized_turnover":      metrics["annualized_turnover"],
                "final_nav":                metrics["final_nav"],
                "net_alpha_vs_benchmark":   metrics["net_alpha_vs_benchmark"],
                "top5_concentration":       conc["top5_concentration"],
                "max_theme_exposure":       max_theme_exposure(theme_exp),
                "unique_holdings_count":    conc["unique_holdings_count"],
                "strong_count":             int(strong["n_obs"].iloc[0]) if not strong.empty else 0,
                "strong_hit_rate":          float(strong["hit_rate"].iloc[0]) if not strong.empty else float("nan"),
                "watchlist_count":          int(watch["n_obs"].iloc[0]) if not watch.empty else 0,
                "watchlist_hit_rate":       float(watch["hit_rate"].iloc[0]) if not watch.empty else float("nan"),
            })

    return {
        "summary":   pd.DataFrame(summary_rows),
        "holdings":  pd.DataFrame(holdings_rows),
        "nav":       pd.DataFrame(nav_rows),
        "theme":     pd.concat(theme_rows, ignore_index=True) if theme_rows else pd.DataFrame(),
        "labels":    pd.concat(label_rows, ignore_index=True) if label_rows else pd.DataFrame(),
        "runs":      runs,
    }


def _path_for(name: str, specs: list[tuple[str, str | None]]) -> str | None:
    for n, p in specs:
        if n == name:
            return p
    return None


def write_outputs(panel: dict, output_dir: str = "data/output") -> None:
    ensure_dir(output_dir)
    panel["summary"].to_csv(resolve_path(f"{output_dir}/universe_expansion_summary.csv"), index=False)
    panel["holdings"].to_csv(resolve_path(f"{output_dir}/universe_expansion_holdings.csv"), index=False)
    panel["nav"].to_csv(resolve_path(f"{output_dir}/universe_expansion_nav.csv"), index=False)
    panel["theme"].to_csv(resolve_path(f"{output_dir}/universe_expansion_theme_exposure.csv"), index=False)
    panel["labels"].to_csv(resolve_path(f"{output_dir}/universe_expansion_label_stats.csv"), index=False)
    logger.info("Wrote 5 universe-expansion CSVs to %s/", output_dir)
