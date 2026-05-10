"""Universe helpers — theme grouping, benchmark resolution."""
from __future__ import annotations

import pandas as pd

from .data_loader import load_universe
from .utils import load_universe_config


def get_universe_df() -> pd.DataFrame:
    """Return the beneficiary universe as a DataFrame."""
    return load_universe()


def get_tickers_by_theme(theme: str | None = None) -> dict[str, list[str]]:
    """Group universe tickers by theme. Optional filter to a single theme."""
    df = load_universe()
    grouped: dict[str, list[str]] = {}
    for t, sub in df.groupby("theme"):
        grouped[t] = sub["ticker"].tolist()
    if theme is not None:
        return {theme: grouped.get(theme, [])}
    return grouped


def get_theme_for_ticker(ticker: str) -> str | None:
    df = load_universe()
    row = df.loc[df["ticker"] == ticker]
    if row.empty:
        return None
    return row.iloc[0]["theme"]


def get_benchmark(kind: str = "primary") -> str:
    """Return the benchmark ticker. ``kind`` is ``primary`` or ``secondary``."""
    cfg = load_universe_config()
    return cfg["benchmark"][kind]


def get_theme_metadata() -> dict[str, dict]:
    """Return the theme registry from ``config/universe.yaml``."""
    return load_universe_config().get("themes", {})
