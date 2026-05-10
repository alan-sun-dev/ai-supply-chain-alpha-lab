"""Tests for the GDELT news-event helpers (no network access)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def news_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "fetch_news_events.py"
    spec = importlib.util.spec_from_file_location("fetch_news_events", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_theme_queries_anchored_on_tsmc(news_module) -> None:
    # Every per-theme query starts with TSMC so GDELT does not match unrelated
    # capex / 2nm articles from other companies.
    assert news_module.THEME_QUERIES, "Expected at least one theme query"
    for theme, q in news_module.THEME_QUERIES.items():
        assert "TSMC" in q, f"theme {theme} query must mention TSMC"


def test_tag_themes_multi_match(news_module) -> None:
    title = "TSMC announces CoWoS capacity expansion at Arizona fab"
    tags = news_module._tag_themes(title)
    assert "advanced_packaging" in tags
    assert "overseas_fab" in tags


def test_tag_themes_no_match(news_module) -> None:
    assert news_module._tag_themes("Apple unveils new iPhone") == []


def test_normalise_pads_missing_columns(news_module) -> None:
    sample = [
        {"url": "https://example.com/a", "title": "TSMC capex up", "seendate": "20260115T120000Z"},
        {"url": "https://example.com/b", "title": "CoWoS demand surge", "seendate": "20260116T120000Z",
         "domain": "ex.com", "language": "English", "sourcecountry": "US"},
    ]
    df = news_module._normalise(sample)
    assert len(df) == 2
    assert set(df.columns) == set(news_module.OUTPUT_COLS)
    assert "capex" in df.iloc[0]["themes_matched"]
    assert "advanced_packaging" in df.iloc[1]["themes_matched"]
