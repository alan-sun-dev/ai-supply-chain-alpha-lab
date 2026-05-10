"""Tests for narrative engine — bounds + capex_interpreter caps."""
from __future__ import annotations

import pandas as pd

from capex_alpha.narrative import capex_interpreter as ci
from capex_alpha.narrative import narrative_scorer as ns
from capex_alpha.narrative import news_parser as np_mod
from capex_alpha.narrative.transcript_parser import extract_transcript_signals


def test_narrative_score_bounded():
    """Whatever the news, score must stay within ±5."""
    out = ns.run(write=False)
    if out.empty:
        return
    assert (out["narrative_score"] <= 5.0).all()
    assert (out["narrative_score"] >= -5.0).all()


def test_capex_context_bounded():
    """capex_interpreter must never exceed ±0.5 score."""
    out = ci.run(write=False)
    if out.empty:
        return
    assert (out["context_score"].abs() <= 0.5).all()


def test_capex_per_theme_aggregation_caps():
    df = ci.run(write=False)
    agg = ci.latest_context_per_theme(df)
    if agg.empty:
        return
    assert (agg["capex_context_score"].abs() <= 0.5).all()


def test_news_parser_runs_without_data():
    """Empty or missing news file → empty frame, no crash."""
    df = np_mod.run(write=False)
    # Either empty or well-formed
    if not df.empty:
        for col in ["ticker", "narrative_score", "narrative_confidence"]:
            assert col in df.columns


def test_transcript_parser_returns_valid_shape():
    sig = extract_transcript_signals("Demand exceeds supply for our advanced packaging.")
    assert "demand_score" in sig
    assert -3 <= sig["demand_score"] <= 3
    sig_neg = extract_transcript_signals("Soft demand and inventory correction continues.")
    assert sig_neg["risk_score"] >= 1


def test_transcript_parser_handles_empty():
    sig = extract_transcript_signals("")
    assert sig["demand_score"] == 0.0
    assert sig["key_quotes"] == []
