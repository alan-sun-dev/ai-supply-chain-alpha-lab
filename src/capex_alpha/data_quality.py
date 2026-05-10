"""Data-quality / coverage reporter — used by Phase B3 (and any future
data-completeness audit) to score how well each ticker is covered across
the four primary data sources: prices, monthly revenue, institutional flow,
and valuation.

Output (CSV-friendly):
    ticker, company_name, theme,
    price_n, price_first, price_last, price_missing_ratio,
    revenue_n, revenue_first, revenue_last, revenue_yoy_n_nonnull,
    flow_n, flow_first, flow_last,
    valuation_n, valuation_first, valuation_last,
    tier2_complete  (True iff revenue_n>=24 AND flow_n>=24 AND valuation_n>=24)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data_loader import (
    get_close_panel,
    load_institutional_flow,
    load_monthly_revenue,
    load_universe,
    load_valuation,
)
from .utils import ensure_dir, get_logger, resolve_path

logger = get_logger(__name__)


# ---------------------------------------------------------------------------

@dataclass
class _PerSource:
    n: int
    first: pd.Timestamp | None
    last: pd.Timestamp | None
    missing_ratio: float = 0.0


def _summarise_revenue(rev: pd.DataFrame, ticker: str) -> tuple[_PerSource, int]:
    sub = rev[rev["ticker"] == ticker]
    if sub.empty:
        return _PerSource(0, None, None), 0
    sub_sorted = sub.sort_values("year_month")
    yoy_nn = int(sub["yoy_pct"].notna().sum())
    return _PerSource(
        n=int(len(sub)),
        first=pd.Timestamp(sub_sorted["year_month"].iloc[0]),
        last=pd.Timestamp(sub_sorted["year_month"].iloc[-1]),
    ), yoy_nn


def _summarise_flow(flow: pd.DataFrame, ticker: str) -> _PerSource:
    sub = flow[flow["ticker"] == ticker]
    if sub.empty:
        return _PerSource(0, None, None)
    s = sub.sort_values("date")
    return _PerSource(
        n=int(len(s)),
        first=pd.Timestamp(s["date"].iloc[0]),
        last=pd.Timestamp(s["date"].iloc[-1]),
    )


def _summarise_valuation(val: pd.DataFrame, ticker: str) -> _PerSource:
    sub = val[val["ticker"] == ticker]
    if sub.empty:
        return _PerSource(0, None, None)
    s = sub.sort_values("date")
    return _PerSource(
        n=int(len(s)),
        first=pd.Timestamp(s["date"].iloc[0]),
        last=pd.Timestamp(s["date"].iloc[-1]),
    )


def _summarise_price(price_panel: pd.DataFrame, ticker: str) -> _PerSource:
    if ticker not in price_panel.columns:
        return _PerSource(0, None, None, 1.0)
    s = price_panel[ticker]
    s_clean = s.dropna()
    if s_clean.empty:
        return _PerSource(0, None, None, 1.0)
    missing = float(1.0 - len(s_clean) / len(s))
    return _PerSource(
        n=int(len(s_clean)),
        first=pd.Timestamp(s_clean.index[0]),
        last=pd.Timestamp(s_clean.index[-1]),
        missing_ratio=missing,
    )


# ---------------------------------------------------------------------------

def coverage_report(
    universe_df: pd.DataFrame | None = None,
    rev: pd.DataFrame | None = None,
    flow: pd.DataFrame | None = None,
    val: pd.DataFrame | None = None,
    price_panel: pd.DataFrame | None = None,
    tier2_min_obs: int = 24,
) -> pd.DataFrame:
    """Compute per-ticker per-factor coverage stats."""
    if universe_df is None:
        universe_df = load_universe()
    if rev is None:
        rev = load_monthly_revenue()
    if flow is None:
        flow = load_institutional_flow()
    if val is None:
        val = load_valuation()
    if price_panel is None:
        price_panel = get_close_panel(universe_df["ticker"].tolist())

    rows: list[dict] = []
    for _, urow in universe_df.iterrows():
        ticker = urow["ticker"]
        company = urow.get("company_name", "")
        theme = urow.get("theme", "")

        price_s = _summarise_price(price_panel, ticker)
        rev_s, yoy_nn = _summarise_revenue(rev, ticker)
        flow_s = _summarise_flow(flow, ticker)
        val_s = _summarise_valuation(val, ticker)

        tier2_complete = (
            rev_s.n >= tier2_min_obs
            and flow_s.n >= tier2_min_obs
            and val_s.n >= tier2_min_obs
        )

        rows.append({
            "ticker":               ticker,
            "company_name":         company,
            "theme":                theme,
            "price_n":              price_s.n,
            "price_first":          price_s.first,
            "price_last":           price_s.last,
            "price_missing_ratio":  round(price_s.missing_ratio, 3),
            "revenue_n":            rev_s.n,
            "revenue_first":        rev_s.first,
            "revenue_last":         rev_s.last,
            "revenue_yoy_n_nonnull": yoy_nn,
            "flow_n":               flow_s.n,
            "flow_first":           flow_s.first,
            "flow_last":            flow_s.last,
            "valuation_n":          val_s.n,
            "valuation_first":      val_s.first,
            "valuation_last":       val_s.last,
            "tier2_complete":       bool(tier2_complete),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------

def coverage_summary(report: pd.DataFrame) -> dict:
    """Headline coverage numbers used by the Phase B3 report."""
    if report.empty:
        return {}
    n = len(report)
    return {
        "n_universe": n,
        "n_with_price":      int((report["price_n"] > 0).sum()),
        "n_with_revenue":    int((report["revenue_n"] > 0).sum()),
        "n_with_flow":       int((report["flow_n"] > 0).sum()),
        "n_with_valuation":  int((report["valuation_n"] > 0).sum()),
        "n_tier2_complete":  int(report["tier2_complete"].sum()),
        "pct_tier2_complete": float(report["tier2_complete"].sum() / n),
        "pct_revenue":       float((report["revenue_n"] > 0).sum() / n),
        "pct_flow":          float((report["flow_n"] > 0).sum() / n),
        "pct_valuation":     float((report["valuation_n"] > 0).sum() / n),
        "earliest_revenue":  report["revenue_first"].min(),
        "earliest_flow":     report["flow_first"].min(),
        "earliest_valuation": report["valuation_first"].min(),
    }


def write(report: pd.DataFrame, output_dir: str = "data/output") -> str:
    ensure_dir(output_dir)
    path = resolve_path(f"{output_dir}/data_coverage_report.csv")
    report.to_csv(path, index=False)
    logger.info("Wrote %s (%d rows)", path, len(report))
    return str(path)
