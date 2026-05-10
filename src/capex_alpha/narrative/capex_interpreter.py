"""CAPEX events → context tags.

CAPEX is no longer a trading trigger (validation rejected it at p=0.67).
This module reduces each CAPEX event to a structured ``context_type`` and
list of ``affected_themes``, capped at a small ``context_score`` (≤ 0.5)
that may be used as a *confidence multiplier* — never as alpha.
"""
from __future__ import annotations

import re

import pandas as pd

from ..data_loader import load_capex_events
from ..utils import ensure_dir, get_logger, resolve_path

logger = get_logger(__name__)


CONTEXT_TAG_RULES = [
    # (regex, context_type, affected_themes)
    (r"CoWoS|advanced packaging|packaging", "cowos_packaging", ["advanced_packaging", "facility_cleanroom"]),
    (r"2nm|N2|nanosheet|leading[-\s]edge", "leading_edge_logic", ["facility_cleanroom", "semi_equipment", "inspection"]),
    (r"Arizona|Japan|Germany|overseas|kumamoto|Dresden", "overseas_fab", ["facility_cleanroom"]),
    (r"mature|legacy|28nm|22nm|specialty", "mature_node", ["gases_chemicals", "indirect"]),
    (r"facility|cleanroom|construction|fab[-\s]build", "facility_expansion", ["facility_cleanroom"]),
    (r"equipment|tool|EUV|lithography", "equipment_pull_in", ["semi_equipment"]),
]


def _classify_event(row: pd.Series) -> list[dict]:
    text = " ".join(
        str(row.get(c, "")) for c in ["technology_driver", "source_title", "analyst_note"]
    )
    out: list[dict] = []
    matched = False
    for pattern, ctx_type, themes in CONTEXT_TAG_RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            matched = True
            out.append({"context_type": ctx_type, "affected_themes": themes})
    if not matched:
        out.append({"context_type": "general_capex_signal", "affected_themes": ["facility_cleanroom"]})
    return out


def _context_score(direction: str, signal: str) -> float:
    """Bounded, asymmetric. Negative direction yields modest penalty."""
    base = {
        "capex_acceleration": 0.5,
        "capex_up": 0.4,
        "capex_neutral": 0.0,
        "capex_down": -0.3,
    }.get(signal, 0.0)
    if direction == "down":
        base = min(base, -0.2)
    return float(max(-0.5, min(0.5, base)))


def run(write: bool = True) -> pd.DataFrame:
    events = load_capex_events()
    if events.empty:
        logger.warning("No CAPEX events; capex_context will be empty.")
        return pd.DataFrame()

    rows: list[dict] = []
    for _, e in events.iterrows():
        signal = str(e.get("capex_signal", "")) or "capex_neutral"
        direction = str(e.get("revision_direction", "")) or "neutral"
        score = _context_score(direction, signal)
        for tag in _classify_event(e):
            rows.append(
                {
                    "event_date": e["event_date"],
                    "context_type": tag["context_type"],
                    "affected_themes": ";".join(tag["affected_themes"]),
                    "context_score": score,
                    "notes": f"{signal}/{direction}: {str(e.get('source_title',''))[:80]}",
                }
            )

    out = pd.DataFrame(rows).sort_values("event_date")
    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/capex_context.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(out))
    return out


def latest_context_per_theme(df: pd.DataFrame, lookback_days: int = 180) -> pd.DataFrame:
    """Aggregate context_score per theme using only events within lookback."""
    if df.empty:
        return pd.DataFrame(columns=["theme", "capex_context_score"])
    df = df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"])
    cutoff = df["event_date"].max() - pd.Timedelta(days=lookback_days)
    df = df[df["event_date"] >= cutoff]
    rows: list[dict] = []
    for _, r in df.iterrows():
        for theme in str(r["affected_themes"]).split(";"):
            theme = theme.strip()
            if not theme:
                continue
            rows.append({"theme": theme, "score": float(r["context_score"])})
    if not rows:
        return pd.DataFrame(columns=["theme", "capex_context_score"])
    agg = pd.DataFrame(rows).groupby("theme", as_index=False)["score"].sum()
    agg = agg.rename(columns={"score": "capex_context_score"})
    # Cap per-theme to ±0.5
    agg["capex_context_score"] = agg["capex_context_score"].clip(-0.5, 0.5)
    return agg
