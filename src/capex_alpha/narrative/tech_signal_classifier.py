"""Lightweight tech-driver classifier — used by news_parser & narrative_scorer.

Right now it's a thin wrapper over the keyword YAML. Centralized here so
future ML classifiers (zero-shot, finetuned model) can swap in cleanly.
"""
from __future__ import annotations

from ..utils import load_yaml


def classify_text(text: str) -> list[str]:
    """Return all theme tags whose keywords appear in ``text``."""
    if not text:
        return []
    text_lower = text.lower()
    out: list[str] = []
    cfg = load_yaml("config/narrative_keywords.yaml")["themes"]
    for theme, body in cfg.items():
        for kw in body["keywords"]:
            if kw.lower() in text_lower:
                out.append(theme)
                break
    return out
