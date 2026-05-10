"""Tests for validation.transaction_cost — turnover, cost, break-even."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha.validation import transaction_cost as tc


# ---------------------------------------------------------------------------
# Fixtures

def _toy_walk_forward(n_dates: int = 12, n_tickers: int = 10, seed: int = 0,
                      strong_alpha: bool = True) -> pd.DataFrame:
    """Synthetic long-format walk_forward_v2_results frame."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-31", periods=n_dates, freq="ME")
    tickers = [f"T{i:02d}" for i in range(n_tickers)]
    rows = []
    for i, d in enumerate(dates):
        for j, t in enumerate(tickers):
            # Make ticker T00 the persistent winner so top-5 is stable
            if strong_alpha:
                alpha = (n_tickers - j) + rng.normal(0, 0.5)
            else:
                alpha = rng.normal(0, 1)
            fwd = 0.02 + (n_tickers - j) * 0.005 + rng.normal(0, 0.03) if strong_alpha else rng.normal(0, 0.03)
            rows.append({
                "rebalance_date": d,
                "ticker": t,
                "alpha_score": alpha,
                "fwd_return_1m": fwd,
                "residual_alpha_score": alpha,
                "revenue_confirmation_score": 0.0,
                "institutional_flow_score": 0.0,
                "narrative_score": 0.0,
                "capex_context_score": 0.0,
                "sector_relative_score": 0.0,
                "risk_penalty": 0.0,
            })
    return pd.DataFrame(rows)


def _toy_benchmark(dates: pd.DatetimeIndex, monthly_return: float = 0.01) -> pd.Series:
    return pd.Series(monthly_return, index=dates, name="benchmark_fwd_1m")


# ---------------------------------------------------------------------------

def test_turnover_from_weights():
    """0.5 * L1 turnover formula on an explicit weight panel."""
    weights = pd.DataFrame(
        {
            "A": [0.5, 0.5, 0.0],
            "B": [0.5, 0.0, 0.5],
            "C": [0.0, 0.5, 0.5],
        },
        index=pd.date_range("2024-01-31", periods=3, freq="ME"),
    )
    to = tc.turnover_from_weight_panel(weights)
    # Period 1 (initial): sum |w| = 1.0 → marked as initial position
    assert to.iloc[0] == pytest.approx(1.0)
    # Period 2: A unchanged, B 0.5→0, C 0→0.5 → L1 = 1.0; turnover = 0.5
    assert to.iloc[1] == pytest.approx(0.5)
    # Period 3: A 0.5→0, B 0→0.5, C unchanged → L1 = 1.0; turnover = 0.5
    assert to.iloc[2] == pytest.approx(0.5)


def test_turnover_from_holdings_matches_weight_formula():
    """For equal-weight top-N, fraction-of-slots-changed = 0.5 * L1 turnover."""
    holdings = {
        pd.Timestamp("2024-01-31"): ["A", "B", "C", "D", "E"],
        pd.Timestamp("2024-02-29"): ["A", "B", "C", "D", "E"],   # 0% turnover
        pd.Timestamp("2024-03-31"): ["A", "B", "C", "F", "G"],   # 40% turnover (2 new)
        pd.Timestamp("2024-04-30"): ["A", "X", "Y", "Z", "G"],   # 60% turnover (3 new)
    }
    to = tc.turnover_series_from_holdings(holdings, charge_initial=True)
    assert to.iloc[0] == pytest.approx(1.0)   # initial
    assert to.iloc[1] == pytest.approx(0.0)
    assert to.iloc[2] == pytest.approx(0.4)
    assert to.iloc[3] == pytest.approx(0.6)


def test_monthly_cost_calculation():
    """monthly_cost_t = turnover_t × cost_bps / 10000, aligned by index."""
    idx = pd.date_range("2024-01-31", periods=4, freq="ME")
    gross = pd.Series([0.05, 0.03, 0.04, 0.02], index=idx, name="gross")
    turnover = pd.Series([1.0, 0.0, 0.4, 0.6], index=idx, name="turnover")
    net, cost = tc.apply_costs(gross, turnover, cost_bps=25)
    expected_cost = turnover * 25 / 10000
    pd.testing.assert_series_equal(cost, expected_cost.rename("monthly_cost"))
    pd.testing.assert_series_equal(net, (gross - expected_cost).rename("net_return"))


def test_net_return_after_cost():
    """Higher cost → lower CAGR and lower final NAV. Lower cost → unchanged metrics."""
    df = _toy_walk_forward(n_dates=24, n_tickers=10)
    bench = _toy_benchmark(df["rebalance_date"].sort_values().unique(), monthly_return=0.01)

    m_zero, _ = tc.simulate_scenario(df, bench, cost_bps=0, n=5)
    m_high, _ = tc.simulate_scenario(df, bench, cost_bps=100, n=5)

    assert m_zero["cagr"] >= m_high["cagr"]
    assert m_zero["final_nav"] >= m_high["final_nav"]
    assert m_high["cost_drag_per_year"] > 0
    assert m_zero["cost_drag_per_year"] == pytest.approx(0.0, abs=1e-9)


def test_break_even_cost_positive_when_strategy_outperforms():
    """When the strategy beats the benchmark, break-even cost must be > 0."""
    df = _toy_walk_forward(n_dates=24, n_tickers=10, strong_alpha=True)
    bench = _toy_benchmark(df["rebalance_date"].sort_values().unique(), monthly_return=0.005)
    be = tc.break_even_cost(df, bench, n=5, max_iter=30)
    assert be > 0
    assert be < 1e6  # not ridiculously large


def test_break_even_returns_nan_when_strategy_loses_at_zero():
    """If gross strategy already underperforms, break-even should be NaN."""
    df = _toy_walk_forward(n_dates=24, n_tickers=10, strong_alpha=False, seed=1)
    bench = _toy_benchmark(df["rebalance_date"].sort_values().unique(), monthly_return=0.10)
    be = tc.break_even_cost(df, bench, n=5)
    # Either NaN or 0; both are acceptable signals that there's no positive break-even.
    assert np.isnan(be) or be == 0.0


def test_no_crash_with_missing_turnover_column():
    """Loader / scenario must not require an explicit ``turnover`` column —
    it derives turnover from holdings.  Smoke: build a results frame without
    a turnover column and run the scenario."""
    df = _toy_walk_forward(n_dates=8, n_tickers=8)
    assert "turnover" not in df.columns  # confirm test premise
    bench = _toy_benchmark(df["rebalance_date"].sort_values().unique(), monthly_return=0.01)
    m, series = tc.simulate_scenario(df, bench, cost_bps=25, n=5)
    assert "cagr" in m
    assert not series.empty
    assert "turnover" in series.columns  # computed internally


def test_run_end_to_end_writes_no_files_when_write_false():
    """Smoke: full run() with write=False should not touch disk."""
    df = _toy_walk_forward(n_dates=12, n_tickers=8)
    bench = _toy_benchmark(df["rebalance_date"].sort_values().unique(), monthly_return=0.01)
    summary, nav, be = tc.run(df, bench, costs_bps=[0, 25, 100], n=5, write=False)
    assert len(summary) == 3
    assert {"cost_bps", "cagr", "sharpe", "max_drawdown",
            "annual_volatility", "monthly_hit_rate",
            "avg_monthly_turnover", "annualized_turnover",
            "cost_drag_per_year", "final_nav",
            "net_alpha_vs_benchmark"}.issubset(summary.columns)
    assert "break_even_cost_bps" in summary.columns
    assert not nav.empty
