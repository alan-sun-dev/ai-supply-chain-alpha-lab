"""AI supply chain theme indices.

Builds equal-weight theme baskets from the beneficiary universe and an
aggregate AI supply chain index used as a *theme beta* benchmark in the
residual alpha model. Indices are pure return series — no fundamentals.

Output: ``data/output/ai_factor_index.csv`` (long format, one row per
date × theme + one row per date with theme = ``aggregate``).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data_loader import get_close_panel, load_universe
from ..utils import ensure_dir, get_logger, load_yaml, resolve_path

logger = get_logger(__name__)


# ---------------------------------------------------------------------------

@dataclass
class FactorIndexConfig:
    theme_weights: dict[str, float]
    history_start: str

    @classmethod
    def from_yaml(cls) -> "FactorIndexConfig":
        cfg = load_yaml("config/alpha_model_v2.yaml")["ai_factor_index"]
        return cls(
            theme_weights=cfg["theme_weights"],
            history_start=cfg.get("history_start", "2018-01-01"),
        )


# ---------------------------------------------------------------------------

def _equal_weight_returns(panel: pd.DataFrame) -> pd.Series:
    """Mean of daily simple returns across the columns present each day."""
    if panel.empty:
        return pd.Series(dtype=float)
    rets = panel.pct_change()
    # Mean across available columns each day; days with all-NaN return NaN.
    return rets.mean(axis=1, skipna=True)


def _drawdown(nav: pd.Series, window: int) -> pd.Series:
    if nav.empty:
        return pd.Series(dtype=float)
    rolling_max = nav.rolling(window=window, min_periods=1).max()
    return nav / rolling_max - 1.0


def build_theme_index(theme: str, tickers: list[str], start: str) -> pd.DataFrame:
    """Build a single theme NAV index from constituent prices."""
    if not tickers:
        logger.warning("Theme %s has no tickers; returning empty.", theme)
        return pd.DataFrame()
    panel = get_close_panel(tickers, start=start)
    if panel.empty:
        logger.warning("Theme %s: no price data; returning empty.", theme)
        return pd.DataFrame()

    rets = _equal_weight_returns(panel)
    rets = rets.dropna()
    if rets.empty:
        return pd.DataFrame()

    nav = (1.0 + rets).cumprod()
    df = pd.DataFrame(
        {
            "date": rets.index,
            "theme": theme,
            "theme_return": rets.values,
            "theme_nav": nav.values,
            "theme_momentum_20d": nav.pct_change(20).values,
            "theme_momentum_60d": nav.pct_change(60).values,
            "theme_drawdown": _drawdown(nav, window=120).values,
            "num_constituents": panel.notna().sum(axis=1).reindex(rets.index).values,
        }
    )
    return df


def build_aggregate_index(theme_frames: dict[str, pd.DataFrame], weights: dict[str, float]) -> pd.DataFrame:
    """Weighted average of theme returns → aggregate AI supply chain index."""
    if not theme_frames:
        return pd.DataFrame()

    pieces = []
    for theme, df in theme_frames.items():
        if df.empty or theme not in weights:
            continue
        s = df.set_index("date")["theme_return"].rename(theme)
        pieces.append(s)
    if not pieces:
        return pd.DataFrame()

    wide = pd.concat(pieces, axis=1).sort_index()
    # Re-normalize weights by available themes each day.
    w = pd.Series({c: weights.get(c, 0.0) for c in wide.columns}, dtype=float)
    if w.sum() <= 0:
        return pd.DataFrame()

    avail = wide.notna().astype(float)
    w_matrix = avail.mul(w, axis=1)
    w_sum = w_matrix.sum(axis=1).replace(0.0, np.nan)
    weighted = (wide.fillna(0.0) * w_matrix).sum(axis=1) / w_sum

    weighted = weighted.dropna()
    nav = (1.0 + weighted).cumprod()

    return pd.DataFrame(
        {
            "date": weighted.index,
            "theme": "aggregate",
            "theme_return": weighted.values,
            "theme_nav": nav.values,
            "theme_momentum_20d": nav.pct_change(20).values,
            "theme_momentum_60d": nav.pct_change(60).values,
            "theme_drawdown": _drawdown(nav, window=120).values,
            "num_constituents": wide.notna().sum(axis=1).reindex(weighted.index).values,
        }
    )


# ---------------------------------------------------------------------------

def run(write: bool = True) -> pd.DataFrame:
    """Build all theme indices + aggregate; return long-format DataFrame."""
    cfg = FactorIndexConfig.from_yaml()
    universe = load_universe()
    # Drop the issuer (TSMC) from beneficiary themes — it's reference, not a beneficiary.
    universe = universe[universe["ticker"] != "2330.TW"]

    theme_frames: dict[str, pd.DataFrame] = {}
    for theme in cfg.theme_weights:
        tickers = universe.loc[universe["theme"] == theme, "ticker"].tolist()
        df = build_theme_index(theme, tickers, start=cfg.history_start)
        if not df.empty:
            theme_frames[theme] = df

    aggregate = build_aggregate_index(theme_frames, cfg.theme_weights)

    parts = list(theme_frames.values())
    if not aggregate.empty:
        parts.append(aggregate)

    if not parts:
        logger.error("No theme indices could be built.")
        return pd.DataFrame()

    out = pd.concat(parts, ignore_index=True).sort_values(["theme", "date"])

    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/ai_factor_index.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(out))

    return out


def latest_aggregate_return_panel(df: pd.DataFrame) -> pd.Series:
    """Pull the daily aggregate-AI return as a date-indexed Series."""
    sub = df[df["theme"] == "aggregate"]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.set_index("date")["theme_return"].sort_index()


def latest_aggregate_nav(df: pd.DataFrame) -> pd.Series:
    sub = df[df["theme"] == "aggregate"]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.set_index("date")["theme_nav"].sort_index()
