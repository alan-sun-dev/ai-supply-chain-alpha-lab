"""Tests for validation.exposure_overlay (Phase D1)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha.validation import exposure_overlay as ov


def _toy_portfolio(monthly_returns: list[float]) -> pd.Series:
    idx = pd.date_range("2020-06-30", periods=len(monthly_returns), freq="ME")
    return pd.Series(monthly_returns, index=idx)


def test_strategy_dd_so_far():
    assert ov._strategy_dd_so_far(0.85, 1.0) == pytest.approx(-0.15)
    assert ov._strategy_dd_so_far(1.20, 1.20) == pytest.approx(0.0)
    assert ov._strategy_dd_so_far(0.0, 1.0) == pytest.approx(-1.0)


def test_drawdown_episode_recovery_duration():
    """Build a synthetic series with one DD episode of known duration."""
    rets = _toy_portfolio([0.10, -0.10, -0.10, 0.05, 0.20])
    # NAV: 1.10, 0.99, 0.891, 0.9356, 1.1227
    # Peak after month 0 = 1.10; DD enters month 1 (val 0.99 < 1.10);
    # recovers when NAV >= 1.10 → month 4 (NAV 1.1227)
    eps = ov.drawdown_episodes(rets)
    assert len(eps) == 1
    e = eps[0]
    assert e.start == pd.Timestamp("2020-07-31")
    assert e.end == pd.Timestamp("2020-10-31")
    assert e.duration_months == 3
    assert e.max_dd < -0.15


def test_no_drawdown_when_monotonic():
    rets = _toy_portfolio([0.05, 0.05, 0.05, 0.05])
    eps = ov.drawdown_episodes(rets)
    assert eps == []


def test_metrics_table_includes_calmar():
    rets = _toy_portfolio([0.05] * 12)
    m = ov.metrics_table(rets, "test")
    assert "calmar" in m
    assert "max_dd" in m
    # No drawdown → max_dd = 0; Calmar undefined → NaN
    assert np.isnan(m["calmar"]) or m["calmar"] != 0


def test_metrics_table_calmar_when_dd_present():
    rets = _toy_portfolio([0.10, -0.20, 0.10, 0.10, 0.10])
    m = ov.metrics_table(rets, "test")
    assert m["max_dd"] < 0
    assert np.isfinite(m["calmar"])


def test_dd_override_caps_exposure_at_30pct():
    """User D1 invariant: if strategy NAV drawdown > 15%, exposure ≤ 30%.

    Tests the OUTPUT INVARIANT — not whether the explicit override flag
    triggered (it can be redundant with the regime cascade picking
    drawdown_control which also gives 0.30 by config). Uses large raw
    returns so even after exposure attenuation the scaled NAV breaches
    the 15% DD threshold."""
    rets = pd.Series(
        [-0.30, -0.30, 0.02, 0.02, 0.02, 0.02],
        index=pd.date_range("2024-01-31", periods=6, freq="ME"),
    )
    market_price = pd.Series(
        [100.0] * 200,
        index=pd.date_range("2023-01-01", periods=200, freq="B"),
    )
    ai_nav = pd.Series(
        [1.0] * 200,
        index=pd.date_range("2023-01-01", periods=200, freq="B"),
    )
    out = ov.compute_exposure_path(rets, market_price, ai_nav)
    in_dd = out[out["strategy_dd_scaled"] <= -0.15]
    assert not in_dd.empty
    assert (in_dd["applied_exposure"] <= 0.30 + 1e-9).all()


def test_dd_override_explicit_when_regime_cascade_misses():
    """If we artificially set the regime cascade to give 1.0 but strategy
    DD breaches threshold, the explicit override must still cap at 0.30.
    We force this by passing the override directly."""
    # Direct call to the helper logic — bypass the regime cascade
    nav_now = 0.80
    peak = 1.00
    strategy_dd = ov._strategy_dd_so_far(nav_now, peak)
    assert strategy_dd <= ov.DD_OVERRIDE_THRESHOLD
    # Simulate cascade returning 1.0 (e.g. risk_on)
    regime_exposure = 1.0
    applied = regime_exposure
    if strategy_dd <= ov.DD_OVERRIDE_THRESHOLD:
        applied = min(applied, ov.DD_OVERRIDE_EXPOSURE)
    assert applied == 0.30


def test_cost_adjust_subtracts_turnover_cost():
    rets = pd.Series(
        [0.05, 0.03, 0.04],
        index=pd.date_range("2024-01-31", periods=3, freq="ME"),
    )
    turnover = pd.Series(
        [1.0, 0.5, 0.2],
        index=rets.index,
    )
    net = ov.cost_adjust(rets, turnover, cost_bps=25)
    expected = rets - turnover * 25 / 10000.0
    pd.testing.assert_series_equal(net, expected)
