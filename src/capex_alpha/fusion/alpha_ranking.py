"""Slice the alpha ranking into per-purpose CSVs.

Reads the unified ``alpha_ranking.csv`` (or accepts a frame) and writes:

- ``data/output/alpha_ranking.csv``      — primary, full universe
- ``data/output/theme_ranking.csv``      — theme-level avg
- ``data/output/watchlist.csv``          — Watchlist + Strong Candidate

Top-N convenience getters are exposed for the dashboard.
"""
from __future__ import annotations

import pandas as pd

from ..utils import ensure_dir, get_logger, resolve_path
from . import scoring_model_v2 as sm

logger = get_logger(__name__)


def _theme_ranking(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby("theme").agg(
        ticker_count=("ticker", "count"),
        avg_alpha=("alpha_score", "mean"),
        max_alpha=("alpha_score", "max"),
        avg_confidence=("confidence_score", "mean"),
        strong_candidates=("decision_zone", lambda s: int((s == "Strong Candidate").sum())),
        watchlist_count=("decision_zone", lambda s: int((s == "Watchlist").sum())),
    ).reset_index().sort_values("avg_alpha", ascending=False)
    return grouped


def _watchlist(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df[df["decision_zone"].isin(["Strong Candidate", "Watchlist"])].copy()


def run(write: bool = True, ranking: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    if ranking is None:
        ranking = sm.run(write=False)

    theme = _theme_ranking(ranking)
    wl = _watchlist(ranking)

    if write:
        ensure_dir("data/output")
        ranking.to_csv(resolve_path("data/output/alpha_ranking.csv"), index=False)
        theme.to_csv(resolve_path("data/output/theme_ranking.csv"), index=False)
        wl.to_csv(resolve_path("data/output/watchlist.csv"), index=False)
        logger.info("Alpha ranking + theme ranking + watchlist written.")

    return {"alpha_ranking": ranking, "theme_ranking": theme, "watchlist": wl}


def top_alpha_candidates(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return df.head(n)


def top_residual_alpha(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return df.sort_values("residual_alpha_score", ascending=False).head(n)


def top_narrative_watch(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return df[df["decision_zone"] == "Narrative Watch"].head(n)


def top_risk_warnings(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return df.sort_values("risk_penalty", ascending=False).head(n)
