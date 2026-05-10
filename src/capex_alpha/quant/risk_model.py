"""Per-stock risk flags (PIT-aware).

Each row in the output is a (ticker, risk_flag) pair with a severity label.
Used by the fusion engine to cap the decision zone (a stock with severe
flags can never be Strong Candidate).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data_loader import (
    get_close_panel,
    load_institutional_flow,
    load_monthly_revenue,
    load_universe,
    load_valuation,
)
from ..utils import ensure_dir, get_logger, resolve_path
from . import residual_alpha as ra
from .factor_model_v2 import REVENUE_REPORTING_LAG_DAYS

logger = get_logger(__name__)


SEVERITY_BLOCKS_STRONG = {"high", "critical"}


# ---------------------------------------------------------------------------

def _slice_panel(panel: pd.DataFrame, as_of: pd.Timestamp | None) -> pd.DataFrame:
    if as_of is None or panel.empty:
        return panel
    return panel.loc[: pd.Timestamp(as_of)]


def _check_overbought(price_panel: pd.DataFrame, ticker: str) -> tuple[bool, str]:
    if ticker not in price_panel.columns:
        return False, ""
    s = price_panel[ticker].dropna()
    if len(s) < 60:
        return False, ""
    ret = float(s.iloc[-1] / s.iloc[-60] - 1.0)
    return ret > 0.40, f"3m return {ret:.1%}"


def _check_drawdown(price_panel: pd.DataFrame, ticker: str) -> tuple[bool, str]:
    if ticker not in price_panel.columns:
        return False, ""
    s = price_panel[ticker].dropna()
    if len(s) < 60:
        return False, ""
    sub = s.tail(120)
    dd = float(sub.iloc[-1] / sub.max() - 1.0)
    return dd < -0.25, f"120d drawdown {dd:.1%}"


def _check_high_beta(residual_snap: pd.DataFrame, ticker: str) -> list[tuple[str, str, str]]:
    flags: list[tuple[str, str, str]] = []
    row = residual_snap[residual_snap["ticker"] == ticker]
    if row.empty:
        return flags
    bai = row.iloc[0].get("beta_ai", np.nan)
    bm = row.iloc[0].get("beta_market", np.nan)
    if pd.notna(bai) and bai > 2.0:
        flags.append(("high_beta_ai", "high", f"beta_ai={bai:.2f}"))
    if pd.notna(bm) and bm > 1.6:
        flags.append(("high_beta_market", "medium", f"beta_market={bm:.2f}"))
    return flags


def _check_revenue_confirmation(
    rev: pd.DataFrame, price_panel: pd.DataFrame, ticker: str, as_of: pd.Timestamp | None
) -> list[tuple[str, str, str]]:
    flags: list[tuple[str, str, str]] = []
    sub = rev[rev["ticker"] == ticker].dropna(subset=["yoy_pct"]).copy()
    if not sub.empty:
        sub["year_month"] = pd.to_datetime(sub["year_month"])
        if as_of is not None:
            cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=REVENUE_REPORTING_LAG_DAYS)
            sub = sub[sub["year_month"] <= cutoff]
    sub = sub.sort_values("year_month")
    if sub.empty:
        flags.append(("revenue_not_confirmed", "medium", "no monthly revenue data"))
        return flags
    latest_yoy = float(sub["yoy_pct"].iloc[-1])
    if ticker in price_panel.columns and len(price_panel[ticker].dropna()) >= 60:
        s = price_panel[ticker].dropna()
        ret_3m = float(s.iloc[-1] / s.iloc[-60] - 1.0)
        if ret_3m > 0.20 and latest_yoy < 0:
            flags.append(
                (
                    "price_up_revenue_down",
                    "high",
                    f"price 3m={ret_3m:.1%}, latest yoy={latest_yoy:.1f}%",
                )
            )
    if latest_yoy < -10:
        flags.append(
            ("revenue_not_confirmed", "high", f"latest yoy={latest_yoy:.1f}%")
        )
    return flags


def _check_valuation(
    val: pd.DataFrame, ticker: str, as_of: pd.Timestamp | None
) -> list[tuple[str, str, str]]:
    flags: list[tuple[str, str, str]] = []
    sub = val[val["ticker"] == ticker].copy()
    if sub.empty:
        return flags
    sub["date"] = pd.to_datetime(sub["date"])
    if as_of is not None:
        sub = sub[sub["date"] <= pd.Timestamp(as_of)]
    if sub.empty:
        return flags
    last = sub.sort_values("date").iloc[-1]
    per = last.get("per", np.nan)
    pbr = last.get("pbr", np.nan)
    if pd.notna(per) and per > 60:
        flags.append(("valuation_extreme", "high", f"PER={per:.1f}"))
    elif pd.notna(per) and per > 40:
        flags.append(("valuation_extreme", "medium", f"PER={per:.1f}"))
    if pd.notna(pbr) and pbr > 7:
        flags.append(("valuation_extreme", "medium", f"PBR={pbr:.2f}"))
    return flags


def _check_liquidity(price_panel: pd.DataFrame, ticker: str) -> list[tuple[str, str, str]]:
    flags: list[tuple[str, str, str]] = []
    if ticker not in price_panel.columns:
        return flags
    s = price_panel[ticker].dropna().tail(20)
    if len(s) < 10:
        flags.append(("liquidity_warning", "medium", "<10 trading days of price data"))
    return flags


# ---------------------------------------------------------------------------

def run(
    write: bool = True,
    residual_df: pd.DataFrame | None = None,
    as_of: pd.Timestamp | None = None,
    price_panel: pd.DataFrame | None = None,
    monthly_revenue: pd.DataFrame | None = None,
    valuation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    universe = load_universe()
    universe = universe[universe["ticker"] != "2330.TW"]

    if price_panel is None:
        price_panel = get_close_panel(universe["ticker"].tolist())
    price_panel = _slice_panel(price_panel, as_of)

    if monthly_revenue is None:
        monthly_revenue = load_monthly_revenue()
    if valuation is None:
        valuation = load_valuation()

    if residual_df is None:
        residual_df = ra.run(write=False)
    snap = ra.latest_snapshot(residual_df, as_of=as_of)

    rows: list[dict] = []
    for _, urow in universe.iterrows():
        ticker = urow["ticker"]
        company = urow["company_name"]
        theme = urow["theme"]

        ovb, msg = _check_overbought(price_panel, ticker)
        if ovb:
            rows.append(
                {"ticker": ticker, "company_name": company, "theme": theme,
                 "risk_flag": "overbought", "severity": "high", "description": msg}
            )

        dd_flag, msg = _check_drawdown(price_panel, ticker)
        if dd_flag:
            rows.append(
                {"ticker": ticker, "company_name": company, "theme": theme,
                 "risk_flag": "excessive_drawdown", "severity": "high", "description": msg}
            )

        for flag, sev, msg in _check_high_beta(snap, ticker):
            rows.append(
                {"ticker": ticker, "company_name": company, "theme": theme,
                 "risk_flag": flag, "severity": sev, "description": msg}
            )

        for flag, sev, msg in _check_revenue_confirmation(monthly_revenue, price_panel, ticker, as_of):
            rows.append(
                {"ticker": ticker, "company_name": company, "theme": theme,
                 "risk_flag": flag, "severity": sev, "description": msg}
            )

        for flag, sev, msg in _check_valuation(valuation, ticker, as_of):
            rows.append(
                {"ticker": ticker, "company_name": company, "theme": theme,
                 "risk_flag": flag, "severity": sev, "description": msg}
            )

        for flag, sev, msg in _check_liquidity(price_panel, ticker):
            rows.append(
                {"ticker": ticker, "company_name": company, "theme": theme,
                 "risk_flag": flag, "severity": sev, "description": msg}
            )

    out = pd.DataFrame(rows, columns=[
        "ticker", "company_name", "theme", "risk_flag", "severity", "description",
    ])

    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/risk_flags.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d flags)", path, len(out))

    return out


def severity_score(flags_for_ticker: pd.DataFrame) -> int:
    if flags_for_ticker.empty:
        return 0
    weights = {"low": 1, "medium": 2, "high": 3, "critical": 5}
    return int(flags_for_ticker["severity"].map(weights).fillna(1).sum())
