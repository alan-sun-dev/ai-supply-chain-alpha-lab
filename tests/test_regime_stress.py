"""Tests for validation.regime_stress (analysis-only module)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha.validation import regime_stress as rs


def _toy_portfolio() -> pd.Series:
    idx = pd.date_range("2020-06-30", periods=12, freq="ME")
    return pd.Series([0.05, -0.02, 0.10, 0.03, -0.05, 0.08,
                      0.04, 0.02, -0.03, 0.06, 0.01, 0.07], index=idx)


def _toy_bench(idx) -> pd.Series:
    return pd.Series(0.01, index=idx)


def _toy_ai(idx) -> pd.Series:
    return pd.Series(0.015, index=idx)


def test_window_total_handles_empty():
    assert rs._window_total(pd.Series(dtype=float)) == 0.0


def test_window_total_compounds_correctly():
    rets = pd.Series([0.10, 0.10],
                     index=pd.date_range("2024-01-31", periods=2, freq="ME"))
    # (1.10)^2 - 1 = 0.21
    assert rs._window_total(rets) == pytest.approx(0.21)


def test_slice_window_inclusive_endpoints():
    s = _toy_portfolio()
    sub = rs._slice_window(s, "2020-06-30", "2020-09-30")
    # Jun-30, Jul-31, Aug-31, Sep-30 → 4 month-ends in [Jun-30, Sep-30]
    assert len(sub) == 4


def test_regime_breakdown_returns_one_row_per_window():
    s = _toy_portfolio()
    bench = _toy_bench(s.index)
    ai = _toy_ai(s.index)
    holdings = {d: ["AAA", "BBB", "CCC"] for d in s.index}
    out = rs.regime_breakdown(s, bench, ai, holdings,
                              regimes=[("Test window", "2020-06-30", "2020-12-31")])
    assert len(out) == 1
    row = out.iloc[0]
    assert row["n_months"] == 7  # Jun, Jul, Aug, Sep, Oct, Nov, Dec month-ends
    assert "cagr" in out.columns
    assert "excess_vs_benchmark_total" in out.columns


def test_event_breakdown_high_vol_subset():
    s = _toy_portfolio()
    bench = _toy_bench(s.index)
    ai = _toy_ai(s.index)
    out = rs.event_breakdown(s, bench, ai, high_vol_quantile=0.5)
    # 4 event-row buckets always returned
    assert len(out) == 4
    expected = {"event_regime", "n_months", "mean_monthly", "hit_rate",
                "total_return", "vs_benchmark", "vs_ai_index"}
    assert expected.issubset(out.columns)


def test_rebuild_alpha_no_risk_adds_back_penalty():
    df = pd.DataFrame({
        "alpha_score":   [1.0, 2.0, 3.0],
        "risk_penalty":  [0.5, 0.0, 1.5],
    })
    out = rs.rebuild_alpha_no_risk(df)
    np.testing.assert_array_almost_equal(out.values, [1.5, 2.0, 4.5])


def test_avg_turnover_in_window_handles_short_window():
    holdings = {pd.Timestamp("2020-06-30"): ["AAA"]}
    assert np.isnan(rs._avg_turnover_in_window(holdings, "2020-01-01", "2020-12-31"))
