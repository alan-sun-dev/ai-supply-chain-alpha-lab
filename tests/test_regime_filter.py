"""Tests for quant.regime_filter — priority cascade."""
from __future__ import annotations

import numpy as np
import pandas as pd

from capex_alpha.quant import regime_filter as rf


def _series(values: list[float], start: str = "2024-01-01") -> pd.Series:
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx)


def test_drawdown_control_overrides_everything():
    """Regardless of market state, large strategy DD → drawdown_control."""
    market = _series(list(np.linspace(100, 130, 200)))  # bull market
    ai = _series(list(np.linspace(100, 140, 200)))      # also bull
    out = rf.classify(
        market_price=market,
        ai_nav=ai,
        revenue_confirmation=True,
        strategy_drawdown=-0.30,
    )
    assert out.risk_level == "very_high"
    assert "drawdown_control" in out.notes


def test_risk_off_when_market_and_ai_below_ma():
    market = _series([100] * 60 + list(np.linspace(100, 80, 80)))
    ai = _series([100] * 60 + list(np.linspace(100, 70, 80)))
    out = rf.classify(market, ai, revenue_confirmation=True, strategy_drawdown=0.0)
    assert out.risk_level == "high"
    assert "risk_off" in out.notes


def test_risk_on_when_market_and_ai_strong():
    market = _series(list(np.linspace(80, 120, 200)))
    ai = _series(list(np.linspace(80, 130, 200)))
    out = rf.classify(market, ai, revenue_confirmation=True, strategy_drawdown=0.0)
    # Because we're using a smooth ramp, it should be in risk_on / neutral
    assert out.risk_level in {"low", "medium"}


def test_run_smoke_writes_single_row():
    df = rf.run(write=False)
    assert len(df) == 1
    assert "recommended_gross_exposure" in df.columns
    assert 0.0 <= df.iloc[0]["recommended_gross_exposure"] <= 1.0
