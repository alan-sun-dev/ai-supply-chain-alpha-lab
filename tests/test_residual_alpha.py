"""Tests for quant.residual_alpha — rolling regression + smoke run."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha.quant import residual_alpha as ra


def test_rolling_regression_recovers_known_betas():
    """If y = 0.5*x1 + 0.3*x2 + noise, betas should be near (0.5, 0.3)."""
    rng = np.random.default_rng(7)
    n = 240
    idx = pd.bdate_range("2022-01-03", periods=n)
    x1 = pd.Series(rng.normal(0.0005, 0.01, n), index=idx)
    x2 = pd.Series(rng.normal(0.0006, 0.012, n), index=idx)
    y = 0.5 * x1 + 0.3 * x2 + rng.normal(0, 0.001, n)
    y = pd.Series(y.values, index=idx)
    x = pd.concat([x1.rename("r1"), x2.rename("r2")], axis=1)

    out = ra._rolling_beta_residual(y, x, window=120, min_obs=60)
    last = out.dropna().iloc[-1]
    assert abs(last["beta_r1"] - 0.5) < 0.05
    assert abs(last["beta_r2"] - 0.3) < 0.05


def test_min_obs_falls_back_to_raw():
    """With min_obs > available rows, residual should equal raw y."""
    idx = pd.bdate_range("2024-01-01", periods=30)
    y = pd.Series(np.random.default_rng(0).normal(0, 0.01, 30), index=idx)
    x = pd.DataFrame({"r": y * 0.5}, index=idx)
    out = ra._rolling_beta_residual(y, x, window=120, min_obs=200)
    # All beta values should be NaN; residual_return should equal raw y
    assert out["beta_r"].isna().all()
    np.testing.assert_array_almost_equal(out["residual_return"].values, y.values)


def test_run_produces_residual_columns():
    """End-to-end smoke. Confirms the required residual columns exist."""
    df = ra.run(write=False)
    assert not df.empty
    required = {
        "ticker", "company_name", "theme",
        "raw_return", "benchmark_return", "ai_index_return",
        "beta_market", "beta_ai",
        "residual_return", "residual_momentum_20d", "residual_momentum_60d",
        "residual_volatility_60d", "residual_drawdown_60d",
        "alpha_quality_score",
    }
    assert required.issubset(df.columns)
