"""Fetch TSMC / semiconductor capex news via the GDELT 2.0 Doc API.

GDELT free tier limits one request per ~5s. This script:
1. Issues a small set of TSMC-anchored AND queries (one per theme) so each
   call returns a tractable number of articles and avoids 429s.
2. Throttles to 5.5s and exponentially backs off on 429.
3. Tags each article with the theme bucket(s) it matched and writes
   `data/manual/news_events.csv` deduped on URL.

Usage:
    python scripts/fetch_news_events.py
    python scripts/fetch_news_events.py --start 2025-06-01 --end 2026-05-01
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capex_alpha.utils import get_logger, resolve_path  # noqa: E402

logger = get_logger("fetch_news_events")

GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"

# One AND-query per theme. Each item is the GDELT query string. All queries are
# anchored with "TSMC" to avoid the broad-query 429s the previous version hit.
THEME_QUERIES: dict[str, str] = {
    "capex":              "TSMC capex",
    "advanced_packaging": "TSMC CoWoS",
    "n2_a16":             "TSMC 2nm",
    "n3":                 "TSMC 3nm",
    "overseas_fab":       "TSMC Arizona",
    "japan_fab":          "TSMC Kumamoto",
    "germany_fab":        "TSMC Dresden",
}

# Loose keyword list (used only to tag articles by theme post-fetch).
THEME_TAG_KEYWORDS: dict[str, list[str]] = {
    "capex":              ["capex", "capital expenditure", "capital budget"],
    "advanced_packaging": ["CoWoS", "advanced packaging", "InFO", "SoIC"],
    "n2_a16":             ["2nm", "N2 process", "A16", "1.6nm"],
    "n3":                 ["3nm", "N3 process"],
    "overseas_fab":       ["Arizona", "fab expansion"],
    "japan_fab":          ["Kumamoto", "Japan"],
    "germany_fab":        ["Dresden", "Germany"],
}

OUTPUT_COLS = [
    "url",
    "title",
    "seendate",
    "domain",
    "language",
    "country",
    "themes_matched",
]


def _yyyymmddhhmmss(d: pd.Timestamp) -> str:
    return d.strftime("%Y%m%d%H%M%S")


def _fetch_chunk(
    query: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    timeout: int,
    max_retries: int = 4,
) -> list[dict]:
    """Fetch a single chunk; on 429 backs off exponentially up to ``max_retries``."""
    import requests

    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": "250",
        "sort": "DateAsc",
        "startdatetime": _yyyymmddhhmmss(start),
        "enddatetime": _yyyymmddhhmmss(end),
    }
    delay = 6.0
    for attempt in range(max_retries):
        try:
            resp = requests.get(GDELT_DOC, params=params, timeout=timeout)
            if resp.status_code == 429:
                logger.warning(
                    "  429 on '%s' %s → %s, sleeping %.0fs (attempt %s/%s)",
                    query, start.date(), end.date(), delay, attempt + 1, max_retries,
                )
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("articles") or []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "  GDELT chunk '%s' %s → %s failed (attempt %s/%s): %s",
                query, start.date(), end.date(), attempt + 1, max_retries, exc,
            )
            time.sleep(delay)
            delay *= 2
    return []


def _tag_themes(text: str) -> list[str]:
    """Return the theme buckets whose keywords appear in ``text``."""
    lower = (text or "").lower()
    hits: list[str] = []
    for theme, kws in THEME_TAG_KEYWORDS.items():
        if any(k.lower() in lower for k in kws):
            hits.append(theme)
    return hits


def _normalise(articles: list[dict]) -> pd.DataFrame:
    if not articles:
        return pd.DataFrame(columns=OUTPUT_COLS)
    df = pd.DataFrame(articles)
    rename = {"sourcecountry": "country"}
    df = df.rename(columns=rename)
    if "seendate" in df.columns:
        df["seendate"] = pd.to_datetime(df["seendate"], errors="coerce")
    df["themes_matched"] = df["title"].fillna("").apply(_tag_themes).apply(";".join)
    for col in OUTPUT_COLS:
        if col not in df.columns:
            df[col] = ""
    return df[OUTPUT_COLS]


def main() -> int:
    # GDELT free DOC API only retains ~1 year of history reliably; default
    # to the last 11 months so naive runs do not silently fall off the edge.
    default_start = (pd.Timestamp.today() - timedelta(days=330)).strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=default_start)
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--chunk-days", type=int, default=30)
    parser.add_argument(
        "--throttle", type=float, default=5.5,
        help="GDELT free tier: 1 req per 5s. Stay above 5 to avoid 429s.",
    )
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)
    if end <= start:
        logger.error("--end must be after --start")
        return 1

    all_articles: list[dict] = []
    for theme, query in THEME_QUERIES.items():
        cursor = start
        logger.info("=== theme=%s query=%r ===", theme, query)
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=args.chunk_days), end)
            logger.info("Fetching %s %s → %s", theme, cursor.date(), chunk_end.date())
            sys.stdout.flush()
            chunk = _fetch_chunk(query, cursor, chunk_end, args.timeout)
            logger.info("  → %s articles", len(chunk))
            sys.stdout.flush()
            all_articles.extend(chunk)
            cursor = chunk_end
            time.sleep(args.throttle)

    df = _normalise(all_articles)
    if df.empty:
        logger.warning("No articles returned.")
        return 0

    out_path = resolve_path("data/manual/news_events.csv")
    if out_path.exists():
        try:
            existing = pd.read_csv(out_path)
            df = pd.concat([existing, df], ignore_index=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read existing news CSV (%s).", exc)

    df = (
        df.dropna(subset=["url"])
        .drop_duplicates(subset=["url"], keep="last")
        .sort_values("seendate")
        .reset_index(drop=True)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    logger.info("Wrote %s articles → %s", len(df), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
