"""Common utilities: project paths, YAML loading, logging, calendar helpers."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def project_root() -> Path:
    """Resolve the project root.

    Walks upward from this file until it finds a directory containing
    ``pyproject.toml``. Falls back to the package parent if not found, so the
    code still works if installed in non-editable mode.
    """
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parents[2]


def resolve_path(rel: str | os.PathLike[str]) -> Path:
    """Resolve a project-relative path to an absolute :class:`Path`."""
    p = Path(rel)
    return p if p.is_absolute() else (project_root() / p)


def ensure_dir(path: str | os.PathLike[str]) -> Path:
    """Create directory if missing and return it."""
    p = resolve_path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_CACHE: dict[str, Any] = {}


def load_yaml(rel_path: str) -> dict[str, Any]:
    """Load a YAML file relative to the project root, with a small cache."""
    key = str(rel_path)
    if key in _CONFIG_CACHE:
        return _CONFIG_CACHE[key]
    path = resolve_path(rel_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _CONFIG_CACHE[key] = data
    return data


def load_universe_config() -> dict[str, Any]:
    return load_yaml("config/universe.yaml")


def load_strategy_config() -> dict[str, Any]:
    return load_yaml("config/strategy_rules.yaml")


def load_data_sources_config() -> dict[str, Any]:
    return load_yaml("config/data_sources.yaml")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str = "capex_alpha") -> logging.Logger:
    """Return a configured logger. Idempotent."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# Trading calendar helpers
# ---------------------------------------------------------------------------

def next_trading_day(target: pd.Timestamp, trading_index: pd.DatetimeIndex) -> pd.Timestamp | None:
    """Return the first trading day on/after ``target``, or ``None`` if missing."""
    if len(trading_index) == 0:
        return None
    target = pd.Timestamp(target).normalize()
    pos = trading_index.searchsorted(target, side="left")
    if pos >= len(trading_index):
        return None
    return trading_index[pos]


def offset_trading_days(
    anchor: pd.Timestamp,
    n: int,
    trading_index: pd.DatetimeIndex,
) -> pd.Timestamp | None:
    """Return the trading day ``n`` sessions away from ``anchor`` (n can be negative)."""
    if len(trading_index) == 0:
        return None
    anchor = pd.Timestamp(anchor).normalize()
    pos = trading_index.searchsorted(anchor, side="left")
    if pos >= len(trading_index) or trading_index[pos] != anchor:
        # anchor is not a trading day; round forward then offset
        if pos >= len(trading_index):
            return None
    target_pos = pos + n
    if target_pos < 0 or target_pos >= len(trading_index):
        return None
    return trading_index[target_pos]
