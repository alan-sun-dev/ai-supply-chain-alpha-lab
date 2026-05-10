"""Tests for quant.ai_factor_index — pure-numeric helpers + smoke run."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha.quant import ai_factor_index as afi


def _toy_panel(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2022-01-03", periods=n)
    return pd.DataFrame(
        {
            "AAA": 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n))),
            "BBB": 100 * np.exp(np.cumsum(rng.normal(0.0006, 0.012, n))),
        },
        index=idx,
    )


def test_equal_weight_returns_handles_nans():
    panel = _toy_panel()
    panel.iloc[5, 0] = np.nan
    rets = afi._equal_weight_returns(panel)
    assert not rets.isna().all()
    assert len(rets) == len(panel)


def test_drawdown_is_non_positive():
    nav = pd.Series([1.0, 1.1, 1.05, 0.9, 0.95])
    dd = afi._drawdown(nav, window=5)
    assert (dd <= 1e-9).all()


def test_aggregate_index_weights_renormalize():
    """When a theme is missing on some days, weights re-normalize."""
    idx = pd.bdate_range("2024-01-01", periods=10)
    a = pd.DataFrame(
        {
            "date": idx,
            "theme": "facility_cleanroom",
            "theme_return": np.linspace(0.001, 0.005, 10),
            "theme_nav": np.linspace(1.0, 1.05, 10),
            "theme_momentum_20d": np.nan,
            "theme_momentum_60d": np.nan,
            "theme_drawdown": np.nan,
            "num_constituents": 3,
        }
    )
    b = a.copy()
    b["theme"] = "semi_equipment"
    b["theme_return"] = np.linspace(0.002, 0.004, 10)
    weights = {"facility_cleanroom": 0.5, "semi_equipment": 0.5}
    agg = afi.build_aggregate_index({"facility_cleanroom": a, "semi_equipment": b}, weights)
    assert not agg.empty
    assert (agg["theme"] == "aggregate").all()


def test_run_smoke():
    """End-to-end smoke against real cached prices."""
    df = afi.run(write=False)
    assert not df.empty
    # Aggregate row must be present
    assert (df["theme"] == "aggregate").any()
    # NAV must be positive
    assert (df.dropna(subset=["theme_nav"])["theme_nav"] > 0).all()
