"""Smoke tests for the universe loaders."""
from __future__ import annotations

import pandas as pd

from capex_alpha.universe import (
    get_benchmark,
    get_theme_metadata,
    get_tickers_by_theme,
    get_universe_df,
)


def test_universe_loads_non_empty() -> None:
    df = get_universe_df()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert {"ticker", "theme", "company_name"}.issubset(df.columns)


def test_themes_match_config() -> None:
    grouped = get_tickers_by_theme()
    themes_in_data = set(grouped.keys())
    themes_in_cfg = set(get_theme_metadata().keys())
    # Every theme used in the CSV must exist in config.
    assert themes_in_data.issubset(themes_in_cfg), (
        f"Themes present in CSV but missing from config: {themes_in_data - themes_in_cfg}"
    )


def test_benchmark_resolves() -> None:
    assert get_benchmark("primary") == "0050.TW"
    # secondary should resolve, even if value differs
    assert get_benchmark("secondary")
