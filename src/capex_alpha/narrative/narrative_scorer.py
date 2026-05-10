"""Combine news + CAPEX context (+ transcripts when available) into a single
narrative_score per ticker. Score is bounded ±5; we also return positive /
negative drivers so the daily report can explain the score.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data_loader import load_universe
from ..utils import ensure_dir, get_logger, resolve_path
from . import capex_interpreter as ci
from . import news_parser as np_mod

logger = get_logger(__name__)


def run(
    write: bool = True,
    news_signals: pd.DataFrame | None = None,
    capex_context: pd.DataFrame | None = None,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if news_signals is None:
        news_signals = np_mod.run(write=False, as_of=as_of)
    if capex_context is None:
        capex_context = ci.run(write=False)

    universe = load_universe()
    universe = universe[universe["ticker"] != "2330.TW"]

    capex_per_theme = ci.latest_context_per_theme(capex_context).set_index("theme") if not capex_context.empty else pd.DataFrame()

    rows: list[dict] = []
    news_idx = news_signals.set_index("ticker") if not news_signals.empty else pd.DataFrame()

    for _, urow in universe.iterrows():
        ticker = urow["ticker"]
        theme = urow["theme"]

        ns = news_idx.loc[ticker] if ticker in news_idx.index else None
        narrative_score = float(ns["narrative_score"]) if ns is not None else 0.0
        narrative_confidence = float(ns["narrative_confidence"]) if ns is not None else 0.0

        # CAPEX context as confidence multiplier — small effect only
        cctx = float(capex_per_theme.loc[theme, "capex_context_score"]) if theme in capex_per_theme.index else 0.0
        narrative_score += cctx  # already capped to ±0.5 upstream

        positive_drivers: list[str] = []
        negative_drivers: list[str] = []
        if ns is not None:
            if ns["positive_signal_count"] > 0:
                positive_drivers.append(f"{int(ns['positive_signal_count'])} positive headlines / 30d")
            if ns["negative_signal_count"] > 0:
                negative_drivers.append(f"{int(ns['negative_signal_count'])} negative headlines / 30d")
            if ns["dominant_tags"]:
                positive_drivers.append(f"tags: {ns['dominant_tags']}")
            if ns["source_count"] >= 5:
                positive_drivers.append(f"multi-source ({int(ns['source_count'])} domains)")
        if cctx > 0:
            positive_drivers.append(f"CAPEX context +{cctx:.2f}")
        elif cctx < 0:
            negative_drivers.append(f"CAPEX context {cctx:.2f}")

        narrative_score = float(np.clip(narrative_score, -5.0, 5.0))

        summary = ""
        if narrative_score >= 2:
            summary = "narrative bullish"
        elif narrative_score <= -2:
            summary = "narrative bearish"
        elif positive_drivers or negative_drivers:
            summary = "narrative mixed"
        else:
            summary = "no narrative signal"

        rows.append(
            {
                "ticker": ticker,
                "theme": theme,
                "narrative_score": narrative_score,
                "narrative_confidence": narrative_confidence,
                "positive_drivers": "; ".join(positive_drivers),
                "negative_drivers": "; ".join(negative_drivers),
                "narrative_summary": summary,
            }
        )

    out = pd.DataFrame(rows)
    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/narrative_signals_aggregated.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(out))
    return out
