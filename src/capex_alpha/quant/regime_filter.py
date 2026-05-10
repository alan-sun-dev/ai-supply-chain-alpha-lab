"""Regime filter — classify the current environment to size exposure.

Outputs the latest regime (and a small history) into
``data/output/regime_status.csv``. The fusion engine reads it to apply a
confidence penalty and to emit a recommended ``gross_exposure`` and
``top_n``.

Five mutually-exclusive regimes are scored:

- ``risk_on``: market + AI both above MAs and AI drawdown shallow
- ``neutral``: market still ok but AI weakening
- ``risk_off``: market and AI both below MAs
- ``ai_bubble_warning``: AI 60d return >40% with weak fundamental confirmation
- ``drawdown_control``: strategy NAV drawdown breach

Priority order (first match wins) is: drawdown_control → ai_bubble_warning →
risk_off → neutral → risk_on. We pick the *most defensive* applicable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data_loader import get_close_panel
from ..utils import ensure_dir, get_logger, load_yaml, resolve_path
from . import ai_factor_index as afi

logger = get_logger(__name__)


@dataclass
class RegimeOutput:
    date: pd.Timestamp
    market_regime: str
    ai_regime: str
    risk_level: str
    recommended_gross_exposure: float
    recommended_top_n: int
    notes: str


# ---------------------------------------------------------------------------

def _market_above_ma(price: pd.Series, window: int) -> bool:
    if len(price) < window:
        return False
    return float(price.iloc[-1]) > float(price.tail(window).mean())


def _drawdown(price: pd.Series, window: int) -> float:
    if price.empty:
        return 0.0
    sub = price.tail(window)
    if sub.empty:
        return 0.0
    return float(sub.iloc[-1] / sub.max() - 1.0)


def _n_period_return(price: pd.Series, n: int) -> float:
    if len(price) < n + 1:
        return 0.0
    return float(price.iloc[-1] / price.iloc[-n - 1] - 1.0)


# ---------------------------------------------------------------------------

def classify(
    market_price: pd.Series,
    ai_nav: pd.Series,
    revenue_confirmation: bool = True,
    strategy_drawdown: float = 0.0,
) -> RegimeOutput:
    """Apply the priority cascade and return a single regime."""
    cfg = load_yaml("config/regime_rules.yaml")["regimes"]

    market_above_ma120 = _market_above_ma(market_price, 120)
    ai_above_ma60 = _market_above_ma(ai_nav, 60)
    ai_dd_60 = _drawdown(ai_nav, 60)
    ai_60d_return = _n_period_return(ai_nav, 60)

    notes: list[str] = []
    notes.append(f"market_above_ma120={market_above_ma120}")
    notes.append(f"ai_above_ma60={ai_above_ma60}")
    notes.append(f"ai_drawdown_60d={ai_dd_60:.2%}")
    notes.append(f"ai_60d_return={ai_60d_return:.2%}")
    notes.append(f"strategy_drawdown={strategy_drawdown:.2%}")

    # Priority order: most defensive first
    if strategy_drawdown <= cfg["drawdown_control"]["require"]["strategy_drawdown_min"]:
        regime = "drawdown_control"
    elif (
        ai_60d_return >= cfg["ai_bubble_warning"]["require"]["ai_60d_return_min"]
        and not revenue_confirmation
    ):
        regime = "ai_bubble_warning"
    elif not market_above_ma120 and not ai_above_ma60:
        regime = "risk_off"
    elif market_above_ma120 and not ai_above_ma60:
        regime = "neutral"
    elif (
        market_above_ma120
        and ai_above_ma60
        and ai_dd_60 >= cfg["risk_on"]["require"]["ai_drawdown_60d_min"]
    ):
        regime = "risk_on"
    else:
        regime = "neutral"

    rule = cfg[regime]
    market_regime = "bullish" if market_above_ma120 else "bearish"
    ai_regime = "bullish" if ai_above_ma60 else "bearish"
    if regime == "ai_bubble_warning":
        ai_regime = "frothy"

    risk_level = {
        "risk_on": "low",
        "neutral": "medium",
        "risk_off": "high",
        "ai_bubble_warning": "high",
        "drawdown_control": "very_high",
    }[regime]

    return RegimeOutput(
        date=pd.Timestamp(market_price.index[-1]) if len(market_price) else pd.Timestamp.today().normalize(),
        market_regime=market_regime,
        ai_regime=ai_regime,
        risk_level=risk_level,
        recommended_gross_exposure=float(rule["gross_exposure"]),
        recommended_top_n=int(rule["top_n"]),
        notes=f"regime={regime}; " + "; ".join(notes),
    )


def run(
    write: bool = True,
    ai_index_df: pd.DataFrame | None = None,
    strategy_drawdown: float = 0.0,
    revenue_confirmation: bool = True,
    as_of: pd.Timestamp | None = None,
    market_panel: pd.DataFrame | None = None,
) -> pd.DataFrame:
    cfg_input = load_yaml("config/regime_rules.yaml")["inputs"]
    if market_panel is None:
        market_panel = get_close_panel([cfg_input["market_benchmark"]])
    if market_panel.empty:
        logger.error("Market benchmark missing for regime filter.")
        return pd.DataFrame()

    if ai_index_df is None:
        ai_index_df = afi.run(write=False)

    ai_nav = afi.latest_aggregate_nav(ai_index_df)
    market_price = market_panel[cfg_input["market_benchmark"]].dropna()

    if as_of is not None:
        market_price = market_price.loc[: pd.Timestamp(as_of)]
        ai_nav = ai_nav.loc[: pd.Timestamp(as_of)]
    if market_price.empty:
        logger.error("No market data on/before as_of=%s.", as_of)
        return pd.DataFrame()

    res = classify(
        market_price=market_price,
        ai_nav=ai_nav,
        revenue_confirmation=revenue_confirmation,
        strategy_drawdown=strategy_drawdown,
    )

    out = pd.DataFrame(
        [
            {
                "date": res.date,
                "market_regime": res.market_regime,
                "ai_regime": res.ai_regime,
                "risk_level": res.risk_level,
                "recommended_gross_exposure": res.recommended_gross_exposure,
                "recommended_top_n": res.recommended_top_n,
                "notes": res.notes,
            }
        ]
    )

    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/regime_status.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s", path)

    return out
