"""Tests for dashboard.services.data_loader.

Each loader is exercised in two states:
- file missing/empty → returns ``None`` (never raises)
- file present and valid → returns the parsed object

We point ``capex_alpha.utils.resolve_path`` at a tmp project root by
patching ``project_root``, so no real repo files are read or written.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from capex_alpha import utils as cap_utils
from dashboard.services import data_loader as dl


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """Redirect ``capex_alpha.utils.project_root`` to a fresh tmp dir.

    Also clears Streamlit's ``cache_data`` so the loaders don't return stale
    results from a previous test (loaders are wrapped at import time when
    Streamlit is installed).
    """
    monkeypatch.setattr(cap_utils, "project_root", lambda: tmp_path)
    try:
        import streamlit as st
        st.cache_data.clear()
    except ImportError:
        pass
    return tmp_path


def _write_csv(root: Path, rel: str, df: pd.DataFrame) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)


def _write_text(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Missing-file behaviour


def test_alpha_ranking_missing_returns_none(tmp_project):
    assert dl.load_alpha_ranking() is None


def test_risk_flags_missing_returns_none(tmp_project):
    assert dl.load_risk_flags() is None


def test_target_weights_missing_returns_none(tmp_project):
    assert dl.load_target_weights() is None


def test_rebalance_log_missing_returns_none(tmp_project):
    assert dl.load_rebalance_log() is None


def test_portfolio_long_missing_returns_none(tmp_project):
    assert dl.load_portfolio_long() is None


def test_dashboard_data_missing_returns_none(tmp_project):
    assert dl.load_dashboard_data() is None


def test_paper_report_missing_returns_none(tmp_project):
    assert dl.load_paper_report_md() is None


def test_empty_file_returns_none(tmp_project):
    p = tmp_project / "data" / "output" / "alpha_ranking.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    assert dl.load_alpha_ranking() is None


# ---------------------------------------------------------------------------
# Present-file behaviour


def test_alpha_ranking_present(tmp_project):
    df = pd.DataFrame({
        "ticker": ["AAA.TW", "BBB.TW"],
        "alpha_score": [2.1, 1.8],
        "theme": ["thermal", "memory_hbm"],
        "decision_zone": ["Watchlist", "Avoid"],
        "risk_severity": [3, 5],
    })
    _write_csv(tmp_project, "data/output/alpha_ranking.csv", df)
    out = dl.load_alpha_ranking()
    assert out is not None
    assert list(out["ticker"]) == ["AAA.TW", "BBB.TW"]
    assert out.shape == (2, 5)


def test_rebalance_log_parses_dates(tmp_project):
    df = pd.DataFrame({
        "rebalance_date": ["2026-01-31", "2026-02-28"],
        "n_holdings": [5, 5],
        "nav_paper": [1.0, 1.05],
        "nav_paper_25bps": [1.0, 1.04],
        "nav_paper_50bps": [1.0, 1.03],
        "nav_benchmark": [1.0, 1.02],
        "drawdown_paper": [0.0, 0.0],
        "base_turnover": [0.5, 0.4],
    })
    _write_csv(tmp_project, "data/output/paper_portfolio/rebalance_log.csv", df)
    out = dl.load_rebalance_log()
    assert out is not None
    assert pd.api.types.is_datetime64_any_dtype(out["rebalance_date"])
    assert len(out) == 2


def test_dashboard_data_present(tmp_project):
    payload = {"as_of_date": "2026-04-30", "market_regime": {"market_regime": "bullish"}}
    _write_text(tmp_project, "data/output/dashboard_data.json", json.dumps(payload))
    out = dl.load_dashboard_data()
    assert out == payload


def test_paper_report_present(tmp_project):
    _write_text(tmp_project, "reports/paper_portfolio_report.md", "# hi\n")
    assert dl.load_paper_report_md() == "# hi\n"


def test_get_theme_map_when_universe_missing(tmp_project, monkeypatch):
    # load_universe will raise FileNotFoundError → loader returns None →
    # get_theme_map returns {}.
    assert dl.get_theme_map() == {}
