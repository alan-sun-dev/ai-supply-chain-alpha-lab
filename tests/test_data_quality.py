"""Tests for data_quality coverage report."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha import data_quality as dq


def _toy_universe() -> pd.DataFrame:
    return pd.DataFrame([
        {"ticker": "AAA.TW", "company_name": "Big Co",   "theme": "x"},
        {"ticker": "BBB.TW", "company_name": "Small Co", "theme": "y"},
        {"ticker": "CCC.TW", "company_name": "No-Data",  "theme": "z"},
    ])


def _toy_revenue() -> pd.DataFrame:
    rows = []
    for ticker in ("AAA.TW", "BBB.TW"):
        for ym in pd.date_range("2020-01", "2024-01", freq="MS"):
            rows.append({"ticker": ticker, "year_month": ym, "yoy_pct": 5.0,
                         "revenue": 1.0e8})
    return pd.DataFrame(rows)


def _toy_flow() -> pd.DataFrame:
    rows = []
    for ticker in ("AAA.TW",):
        for d in pd.date_range("2022-01-03", "2024-01-01", freq="B"):
            rows.append({"ticker": ticker, "date": d, "foreign_net": 1000})
    return pd.DataFrame(rows)


def _toy_valuation() -> pd.DataFrame:
    rows = []
    for ticker in ("AAA.TW",):
        for d in pd.date_range("2020-01-02", "2024-01-01", freq="B"):
            rows.append({"ticker": ticker, "date": d, "per": 20.0, "pbr": 3.0})
    return pd.DataFrame(rows)


def _toy_panel(tickers: list[str]) -> pd.DataFrame:
    idx = pd.bdate_range("2018-01-02", "2024-01-01")
    data = {t: 100.0 + np.arange(len(idx)) * 0.1 for t in tickers if t != "CCC.TW"}
    return pd.DataFrame(data, index=idx)


def test_coverage_report_schema():
    rep = dq.coverage_report(
        universe_df=_toy_universe(),
        rev=_toy_revenue(),
        flow=_toy_flow(),
        val=_toy_valuation(),
        price_panel=_toy_panel(["AAA.TW", "BBB.TW"]),
    )
    expected = {
        "ticker", "company_name", "theme",
        "price_n", "price_first", "price_last", "price_missing_ratio",
        "revenue_n", "revenue_first", "revenue_last", "revenue_yoy_n_nonnull",
        "flow_n", "flow_first", "flow_last",
        "valuation_n", "valuation_first", "valuation_last",
        "tier2_complete",
    }
    assert expected.issubset(set(rep.columns))


def test_coverage_report_handles_missing_ticker():
    """Ticker absent from price panel + all FinMind sources → all-zero counts, tier2 False."""
    rep = dq.coverage_report(
        universe_df=_toy_universe(),
        rev=_toy_revenue(),
        flow=_toy_flow(),
        val=_toy_valuation(),
        price_panel=_toy_panel(["AAA.TW", "BBB.TW"]),
    )
    ccc = rep[rep["ticker"] == "CCC.TW"].iloc[0]
    assert ccc["price_n"] == 0
    assert ccc["revenue_n"] == 0
    assert ccc["flow_n"] == 0
    assert ccc["valuation_n"] == 0
    assert ccc["tier2_complete"] is False or ccc["tier2_complete"] == False


def test_tier2_complete_true_when_all_sources_present():
    rep = dq.coverage_report(
        universe_df=_toy_universe(),
        rev=_toy_revenue(),
        flow=_toy_flow(),
        val=_toy_valuation(),
        price_panel=_toy_panel(["AAA.TW", "BBB.TW"]),
    )
    aaa = rep[rep["ticker"] == "AAA.TW"].iloc[0]
    assert aaa["tier2_complete"] == True


def test_summary_pcts_match_counts():
    rep = dq.coverage_report(
        universe_df=_toy_universe(),
        rev=_toy_revenue(),
        flow=_toy_flow(),
        val=_toy_valuation(),
        price_panel=_toy_panel(["AAA.TW", "BBB.TW"]),
    )
    s = dq.coverage_summary(rep)
    assert s["n_universe"] == 3
    assert s["n_with_revenue"] == 2
    assert s["n_with_flow"] == 1
    assert s["n_with_valuation"] == 1
    # Only AAA has all three → only 1 tier2_complete
    assert s["n_tier2_complete"] == 1
    assert s["pct_tier2_complete"] == pytest.approx(1 / 3)
