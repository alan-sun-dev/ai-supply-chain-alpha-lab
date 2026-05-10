"""News → narrative signal aggregator.

Consumes ``data/manual/news_events.csv`` (current GDELT dump) and produces
``data/output/narrative_signals.csv`` — one row per (date, ticker) with
news counts, dominant tags, and a bounded narrative score.

Counts are de-duplicated by ``(title_normalized, day)`` to suppress wire
republications (one story syndicated across 30 sites should not be 30
signals). Multi-source confirmation increases ``narrative_confidence``.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date

import numpy as np
import pandas as pd

from ..data_loader import load_universe
from ..utils import ensure_dir, get_logger, load_yaml, resolve_path

logger = get_logger(__name__)


# ---------------------------------------------------------------------------

def _load_news_events() -> pd.DataFrame:
    path = resolve_path("data/manual/news_events.csv")
    if not path.exists():
        logger.warning("news_events.csv missing — narrative engine will return empty.")
        return pd.DataFrame(
            columns=["url", "title", "seendate", "domain", "language", "country", "themes_matched"]
        )
    df = pd.read_csv(path)
    df["seendate"] = pd.to_datetime(df["seendate"], errors="coerce", utc=True).dt.tz_convert(None)
    df = df.dropna(subset=["seendate"])
    df["title"] = df["title"].fillna("").astype(str)
    df["domain"] = df["domain"].fillna("").astype(str)
    df["themes_matched"] = df["themes_matched"].fillna("").astype(str)
    return df


def _normalize_title(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _tag_signal_polarity(title: str, kw_cfg: dict) -> tuple[int, int, list[str]]:
    """Return (positive_count, negative_count, matched_phrases)."""
    title_lower = title.lower()
    pos = 0
    neg = 0
    matched: list[str] = []
    for phrase in kw_cfg["signal_types"]["positive"]:
        if phrase.lower() in title_lower:
            pos += 1
            matched.append(f"+{phrase}")
    for phrase in kw_cfg["signal_types"]["negative"]:
        if phrase.lower() in title_lower:
            neg += 1
            matched.append(f"-{phrase}")
    return pos, neg, matched


def _tag_themes(title: str, themes_matched: str, kw_cfg: dict) -> list[str]:
    tags: set[str] = set()
    if themes_matched:
        for tag in re.split(r"[;,|]", themes_matched):
            tag = tag.strip()
            if tag:
                tags.add(tag)
    title_lower = title.lower()
    for theme, body in kw_cfg["themes"].items():
        for kw in body["keywords"]:
            if kw.lower() in title_lower:
                tags.add(theme)
                break
    return sorted(tags)


# ---------------------------------------------------------------------------

def _attribute_to_tickers(
    universe: pd.DataFrame, tags: list[str], theme_map: dict[str, list[str]]
) -> list[str]:
    """Map narrative tags → universe tickers via theme_mapping.yaml.

    Plus: direct match on company_name substring (in case the headline names
    a Taiwan supplier).
    """
    matched_themes: set[str] = set()
    for tag in tags:
        for theme in theme_map.get(tag, []):
            matched_themes.add(theme)
    if not matched_themes:
        return []
    return universe.loc[universe["theme"].isin(matched_themes), "ticker"].tolist()


# ---------------------------------------------------------------------------

def run(write: bool = True, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Aggregate news into per-ticker narrative signals."""
    kw_cfg = load_yaml("config/narrative_keywords.yaml")
    theme_map = load_yaml("config/theme_mapping.yaml")["tag_to_themes"]
    universe = load_universe()
    universe = universe[universe["ticker"] != "2330.TW"]

    raw = _load_news_events()
    if raw.empty:
        return pd.DataFrame()

    raw["title_norm"] = raw["title"].map(_normalize_title)
    raw["day"] = raw["seendate"].dt.normalize()
    if as_of is not None:
        raw = raw[raw["day"] <= pd.Timestamp(as_of)]

    # De-dup wire syndication: same normalized title within same day = 1 event,
    # but track distinct domains to feed the multi-source bonus.
    grouped = (
        raw.groupby(["day", "title_norm"], as_index=False)
        .agg(
            title=("title", "first"),
            themes_matched=("themes_matched", lambda s: ";".join(sorted(set(";".join(s).split(";")) - {""}))),
            source_count=("domain", lambda s: s.nunique()),
        )
    )

    # Per-event tags + polarity
    polarity_rows = []
    for _, e in grouped.iterrows():
        pos, neg, matched_phrases = _tag_signal_polarity(e["title"], kw_cfg)
        tags = _tag_themes(e["title"], e["themes_matched"], kw_cfg)
        tickers = _attribute_to_tickers(universe, tags, theme_map)
        for ticker in tickers:
            polarity_rows.append(
                {
                    "day": e["day"],
                    "ticker": ticker,
                    "tags": ";".join(tags),
                    "positive_signal_count": pos,
                    "negative_signal_count": neg,
                    "source_count": int(e["source_count"]),
                }
            )

    if not polarity_rows:
        return pd.DataFrame()

    events = pd.DataFrame(polarity_rows)

    # Aggregate windows: 1d / 7d / 30d
    out_rows: list[dict] = []
    end_date = events["day"].max() if as_of is None else pd.Timestamp(as_of)
    universe_idx = universe.set_index("ticker")
    for ticker, sub in events.groupby("ticker"):
        last_1d = sub[sub["day"] >= end_date - pd.Timedelta(days=1)]
        last_7d = sub[sub["day"] >= end_date - pd.Timedelta(days=7)]
        last_30d = sub[sub["day"] >= end_date - pd.Timedelta(days=30)]

        # Tag dominance
        tag_counter: Counter = Counter()
        for tags_str in last_30d["tags"]:
            for t in tags_str.split(";"):
                if t:
                    tag_counter[t] += 1
        dominant_tags = ";".join([t for t, _ in tag_counter.most_common(3)])

        pos_30 = int(last_30d["positive_signal_count"].sum())
        neg_30 = int(last_30d["negative_signal_count"].sum())
        n_sources_30 = int(last_30d["source_count"].sum())

        # Score: capped between -5 and +5
        score = 0.0
        if pos_30 > 0:
            score += min(2.0, pos_30 * 0.5)
        if neg_30 > 0:
            score -= min(2.0, neg_30 * 0.5)
        if len(last_7d) > 0:
            score += min(1.0, len(last_7d) * 0.25)  # recency boost
        if pos_30 > 0 and last_30d["source_count"].max() >= 3:
            score += 1.0  # multi-source confirmation
        # Penalty: hype with single source only
        if pos_30 > 0 and last_30d["source_count"].max() <= 1:
            score -= 0.5
        score = float(np.clip(score, -5.0, 5.0))

        confidence = 0.0
        if last_30d["source_count"].max() >= 3:
            confidence += 1.5
        if len(last_30d) >= 3:
            confidence += 1.0
        if pos_30 > 0 and neg_30 > 0:
            confidence -= 0.5  # mixed signal
        confidence = float(np.clip(confidence, 0.0, 5.0))

        out_rows.append(
            {
                "date": end_date,
                "ticker": ticker,
                "company_name": universe_idx.loc[ticker, "company_name"] if ticker in universe_idx.index else "",
                "theme": universe_idx.loc[ticker, "theme"] if ticker in universe_idx.index else "",
                "news_count_1d": len(last_1d),
                "news_count_7d": len(last_7d),
                "news_count_30d": len(last_30d),
                "positive_signal_count": pos_30,
                "negative_signal_count": neg_30,
                "dominant_tags": dominant_tags,
                "narrative_score": score,
                "narrative_confidence": confidence,
                "source_count": n_sources_30,
            }
        )

    out = pd.DataFrame(out_rows)
    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/narrative_signals.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(out))

    return out
