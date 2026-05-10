"""Transcript parser — placeholder.

Future: read TSMC and supplier earnings-call transcripts, extract
guidance/demand/capacity/pricing/visibility scores. For MVP we expose
a deterministic stub that returns neutral scores so downstream code can
unconditionally call into it.
"""
from __future__ import annotations

import re
from typing import TypedDict


class TranscriptSignals(TypedDict):
    demand_score: float
    capacity_score: float
    pricing_score: float
    visibility_score: float
    risk_score: float
    key_quotes: list[str]


_POSITIVE_PHRASES = [
    "demand exceeds supply",
    "stronger than expected",
    "raise our forecast",
    "tight supply",
    "fully booked",
    "higher utilization",
]

_NEGATIVE_PHRASES = [
    "soft demand",
    "weaker than expected",
    "lower our forecast",
    "inventory correction",
    "utilization decline",
    "delay",
]


def extract_transcript_signals(text: str) -> TranscriptSignals:
    """Extremely simple lexicon-based stub.

    Production will replace this with a proper LLM/NLP pass — the interface
    is fixed so the rest of the pipeline can call it today.
    """
    if not text:
        return TranscriptSignals(
            demand_score=0.0,
            capacity_score=0.0,
            pricing_score=0.0,
            visibility_score=0.0,
            risk_score=0.0,
            key_quotes=[],
        )

    text_lower = text.lower()
    pos_hits = [p for p in _POSITIVE_PHRASES if p in text_lower]
    neg_hits = [p for p in _NEGATIVE_PHRASES if p in text_lower]

    base = len(pos_hits) - len(neg_hits)

    quotes: list[str] = []
    for phrase in pos_hits + neg_hits:
        for m in re.finditer(re.escape(phrase), text_lower):
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            quotes.append(text[start:end].strip())
    quotes = quotes[:5]

    return TranscriptSignals(
        demand_score=float(max(-3, min(3, base))),
        capacity_score=float(max(-3, min(3, base * 0.8))),
        pricing_score=float(max(-3, min(3, base * 0.5))),
        visibility_score=float(max(-3, min(3, base * 0.6))),
        risk_score=float(max(-3, min(3, len(neg_hits)))),
        key_quotes=quotes,
    )
