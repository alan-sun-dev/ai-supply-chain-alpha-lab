"""v2 walk-forward engine.

For each month-end rebalance date in [start, end]:
  1. Run scoring_model_v2.run(as_of=t) — point-in-time correct
  2. Record per-ticker (alpha_score, decision_zone, all tier scores)
  3. Compute forward 1-month return per ticker (close-to-close)

Output: ``data/output/walk_forward_v2_results.csv`` (long format,
rebalance_date × ticker).

Notes
-----
- Pre-loads all data sources once; passes them into scoring to avoid 60×
  repeated I/O.
- Rebalance dates snap to the nearest prior trading day in the price panel.
- Forward return uses the next rebalance date's close (≈ 1 calendar month).
- Last rebalance date has no forward return (NaN).
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from ..data_loader import (
    get_close_panel,
    load_institutional_flow,
    load_monthly_revenue,
    load_universe,
    load_valuation,
)
from ..fusion import scoring_model_v2 as sm
from ..narrative import capex_interpreter as ci
from ..quant import ai_factor_index as afi
from ..quant import residual_alpha as ra
from ..utils import ensure_dir, get_logger, resolve_path

logger = get_logger(__name__)


# ---------------------------------------------------------------------------

def generate_rebalance_dates(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    trading_index: pd.DatetimeIndex,
) -> list[pd.Timestamp]:
    """Last trading day of each month within [start, end]."""
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    months = pd.date_range(start, end, freq="ME")  # month-end (calendar)
    out: list[pd.Timestamp] = []
    for m in months:
        # Snap to nearest prior trading day
        mask = trading_index <= m
        if not mask.any():
            continue
        out.append(trading_index[mask][-1])
    # De-dup in case multiple months snap to same trading day (unlikely)
    out = sorted(set(out))
    return out


def _compute_forward_returns(
    ranking: pd.DataFrame,
    price_panel: pd.DataFrame,
    rebalance_dates: list[pd.Timestamp],
) -> pd.Series:
    """Map (rebalance_date, ticker) → 1-month forward simple return."""
    next_date = {t: rebalance_dates[i + 1] for i, t in enumerate(rebalance_dates[:-1])}
    fwd = pd.Series(np.nan, index=ranking.index, dtype=float)
    for idx, row in ranking.iterrows():
        t = pd.Timestamp(row["rebalance_date"])
        ticker = row["ticker"]
        if t not in next_date or ticker not in price_panel.columns:
            continue
        try:
            p_now = price_panel.at[t, ticker]
            p_next = price_panel.at[next_date[t], ticker]
        except KeyError:
            continue
        if pd.notna(p_now) and pd.notna(p_next) and p_now > 0:
            fwd.at[idx] = float(p_next / p_now - 1.0)
    return fwd


def _benchmark_returns(
    benchmark_panel: pd.DataFrame,
    rebalance_dates: list[pd.Timestamp],
    ticker: str,
) -> pd.Series:
    """1-month forward return of benchmark for each rebalance date."""
    s = benchmark_panel[ticker].dropna()
    out = {}
    for i, t in enumerate(rebalance_dates[:-1]):
        next_t = rebalance_dates[i + 1]
        if t in s.index and next_t in s.index:
            out[t] = float(s.loc[next_t] / s.loc[t] - 1.0)
    return pd.Series(out, name="benchmark_fwd_1m")


# ---------------------------------------------------------------------------

def run(
    start: str | pd.Timestamp = "2020-06-30",
    end: str | pd.Timestamp | None = None,
    write: bool = True,
    progress: bool = True,
) -> dict[str, pd.DataFrame]:
    """End-to-end walk-forward; returns dict of frames."""
    universe = load_universe()
    universe = universe[universe["ticker"] != "2330.TW"]
    tickers = universe["ticker"].tolist()

    logger.info("Pre-loading data sources …")
    ai_index = afi.run(write=False)
    residual = ra.run(write=False, ai_index_df=ai_index)
    capex_ctx = ci.run(write=False)
    monthly_rev = load_monthly_revenue()
    institutional_flow = load_institutional_flow()
    valuation = load_valuation()
    price_panel = get_close_panel(tickers)
    benchmark_panel = get_close_panel(["0050.TW"])

    if end is None:
        end = price_panel.index.max()

    rebalance_dates = generate_rebalance_dates(
        start, end, trading_index=price_panel.index
    )
    logger.info("Walk-forward over %d rebalance dates [%s → %s]",
                len(rebalance_dates), rebalance_dates[0].date(), rebalance_dates[-1].date())

    parts: list[pd.DataFrame] = []
    for i, as_of in enumerate(rebalance_dates):
        if progress and (i % 6 == 0 or i == len(rebalance_dates) - 1):
            logger.info("[%d/%d] %s", i + 1, len(rebalance_dates), as_of.date())
        ranking = sm.run(
            write=False,
            residual_df=residual,
            ai_index_df=ai_index,
            capex_context=capex_ctx,
            as_of=as_of,
            price_panel=price_panel,
            monthly_revenue=monthly_rev,
            institutional_flow=institutional_flow,
            valuation=valuation,
            market_panel=benchmark_panel,
        )
        if ranking.empty:
            continue
        ranking = ranking.copy()
        ranking["rebalance_date"] = as_of
        parts.append(ranking)

    if not parts:
        logger.error("No walk-forward rows produced.")
        return {"results": pd.DataFrame()}

    out = pd.concat(parts, ignore_index=True)
    out["fwd_return_1m"] = _compute_forward_returns(out, price_panel, rebalance_dates)

    bench = _benchmark_returns(benchmark_panel, rebalance_dates, "0050.TW")

    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/walk_forward_v2_results.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows, %d unique dates)", path, len(out), out["rebalance_date"].nunique())
        bench_path = resolve_path("data/output/walk_forward_v2_benchmark.csv")
        bench.reset_index().rename(columns={"index": "rebalance_date"}).to_csv(bench_path, index=False)
        logger.info("Wrote %s", bench_path)

    return {"results": out, "benchmark": bench, "rebalance_dates": rebalance_dates}
