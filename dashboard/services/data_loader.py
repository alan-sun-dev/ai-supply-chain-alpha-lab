"""Graceful, cached readers for dashboard inputs.

All loaders return ``None`` (never raise) when the underlying file is
missing or empty so the UI can show an actionable message instead of a
stack trace. Cached with ``ttl=30`` so the dashboard picks up fresh
output from pipeline runs without manual refresh.

Streamlit is imported lazily so this module is unit-testable outside a
Streamlit runtime.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, TypeVar

import pandas as pd

from capex_alpha.utils import resolve_path

T = TypeVar("T")

CACHE_TTL_SECONDS = 30


def _maybe_cache(fn: Callable[..., T]) -> Callable[..., T]:
    """Wrap ``fn`` with ``st.cache_data`` if Streamlit is importable.

    Falls back to the bare function in non-Streamlit contexts (tests).
    """
    try:
        import streamlit as st
    except ImportError:
        return fn
    return st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)(fn)


def _read_csv_safe(rel_path: str, **read_csv_kwargs: Any) -> pd.DataFrame | None:
    p = resolve_path(rel_path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(p, **read_csv_kwargs)
    except (pd.errors.EmptyDataError, OSError):
        return None
    if df.empty:
        return None
    return df


def _read_json_safe(rel_path: str) -> dict | list | None:
    p = resolve_path(rel_path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_text_safe(rel_path: str) -> str | None:
    p = resolve_path(rel_path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Public loaders (cached when Streamlit is available)


@_maybe_cache
def load_alpha_ranking() -> pd.DataFrame | None:
    return _read_csv_safe("data/output/alpha_ranking.csv")


@_maybe_cache
def load_risk_flags() -> pd.DataFrame | None:
    return _read_csv_safe("data/output/risk_flags.csv")


@_maybe_cache
def load_target_weights() -> pd.DataFrame | None:
    return _read_csv_safe("data/output/paper_portfolio/target_weights.csv")


@_maybe_cache
def load_rebalance_log() -> pd.DataFrame | None:
    return _read_csv_safe(
        "data/output/paper_portfolio/rebalance_log.csv",
        parse_dates=["rebalance_date"],
    )


@_maybe_cache
def load_portfolio_long() -> pd.DataFrame | None:
    return _read_csv_safe(
        "data/output/paper_portfolio/portfolio.csv",
        parse_dates=["rebalance_date"],
    )


@_maybe_cache
def load_dashboard_data() -> dict | None:
    data = _read_json_safe("data/output/dashboard_data.json")
    return data if isinstance(data, dict) else None


@_maybe_cache
def load_paper_report_md() -> str | None:
    return _read_text_safe("reports/paper_portfolio_report.md")


@_maybe_cache
def load_universe_df() -> pd.DataFrame | None:
    """Active beneficiary universe — used for theme map. None if missing."""
    try:
        from capex_alpha.data_loader import load_universe
        df = load_universe()
        return df if not df.empty else None
    except (FileNotFoundError, OSError):
        return None


def get_theme_map() -> dict[str, str]:
    """ticker -> theme dict; empty dict when universe is unavailable."""
    df = load_universe_df()
    if df is None or "ticker" not in df.columns or "theme" not in df.columns:
        return {}
    return df.set_index("ticker")["theme"].to_dict()


def clear_all_caches() -> None:
    """Drop all cached loader results (call after a confirm-rebalance write)."""
    try:
        import streamlit as st
        st.cache_data.clear()
    except ImportError:
        return
