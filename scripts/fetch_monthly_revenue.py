"""Fetch monthly revenue for the universe via the FinMind public API.

FinMind's free tier exposes ``TaiwanStockMonthRevenue`` without authentication
for a generous request quota. This script:

1. Reads `data/manual/beneficiary_universe.csv`
2. Strips Taiwan suffixes (.TW / .TWO) to get the bare ticker
3. Calls FinMind for each ticker over the configured date range
4. Merges into `data/manual/monthly_revenue.csv` (preserving any pre-existing
   manual rows) and de-duplicates on (ticker, year_month)
5. Logs failures but never crashes the pipeline

Usage:

    python scripts/fetch_monthly_revenue.py
    python scripts/fetch_monthly_revenue.py --start 2020-01-01 --end 2026-04-30
    python scripts/fetch_monthly_revenue.py --token <your_finmind_token>

A token is optional but recommended for production use; sign up free at
https://finmindtrade.com.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capex_alpha.data_loader import load_universe  # noqa: E402
from capex_alpha.utils import get_logger, resolve_path  # noqa: E402

logger = get_logger("fetch_monthly_revenue")

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
DATASET = "TaiwanStockMonthRevenue"

OUTPUT_COLS = [
    "ticker",
    "company_name",
    "year_month",
    "revenue",
    "yoy_pct",
    "mom_pct",
    "source_url",
    "notes",
]


def _bare_ticker(ticker: str) -> str:
    """Strip exchange suffix for FinMind (e.g. 2404.TW → 2404, 3131.TWO → 3131)."""
    return ticker.split(".")[0].strip()


def _fetch_one(
    bare: str,
    start: str,
    end: str,
    token: str | None,
    timeout: int,
) -> pd.DataFrame:
    """Hit FinMind for a single ticker; return empty frame on failure."""
    import requests  # local import so the module stays importable without requests

    params = {
        "dataset": DATASET,
        "data_id": bare,
        "start_date": start,
        "end_date": end,
    }
    if token:
        params["token"] = token

    try:
        resp = requests.get(FINMIND_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001 - network errors, JSON errors etc
        logger.warning("FinMind fetch failed for %s: %s", bare, exc)
        return pd.DataFrame()

    rows = payload.get("data") or []
    if not rows:
        logger.warning("No FinMind data for %s in [%s, %s]", bare, start, end)
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # FinMind columns: date (YYYY-MM-DD, end-of-month), stock_id, country, revenue,
    # revenue_month, revenue_year, etc. We normalise:
    df["year_month"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m")
    return df


def _normalise(raw: pd.DataFrame, ticker: str, company_name: str) -> pd.DataFrame:
    """Project FinMind frame → our canonical schema and recompute YoY / MoM."""
    if raw.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    g = raw.sort_values("year_month").copy()
    g["revenue"] = pd.to_numeric(g["revenue"], errors="coerce")
    g = g.dropna(subset=["revenue"])
    if g.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    g["yoy_pct"] = g["revenue"].pct_change(12) * 100
    g["mom_pct"] = g["revenue"].pct_change(1) * 100
    g["ticker"] = ticker
    g["company_name"] = company_name
    g["source_url"] = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue"
    g["notes"] = "FinMind"
    return g[OUTPUT_COLS]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--token", default=None, help="FinMind API token (optional)")
    parser.add_argument("--timeout", default=20, type=int)
    args = parser.parse_args()

    universe = load_universe()
    if universe.empty:
        logger.error("Universe is empty.")
        return 1

    out_path = resolve_path("data/manual/monthly_revenue.csv")
    existing = pd.DataFrame(columns=OUTPUT_COLS)
    if out_path.exists():
        try:
            existing = pd.read_csv(out_path, dtype={"ticker": str})
            logger.info("Loaded %s existing rows from %s", len(existing), out_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read existing CSV (%s); ignoring.", exc)

    new_chunks: list[pd.DataFrame] = []
    for _, row in universe.iterrows():
        ticker = row["ticker"]
        bare = _bare_ticker(ticker)
        if not bare:
            continue
        logger.info("Fetching %s (%s)…", ticker, bare)
        raw = _fetch_one(bare, args.start, args.end, args.token, args.timeout)
        norm = _normalise(raw, ticker, row.get("company_name", ""))
        if not norm.empty:
            new_chunks.append(norm)
            logger.info("  → %s rows", len(norm))

    if not new_chunks and existing.empty:
        logger.warning("No data fetched and no existing rows — leaving CSV as-is.")
        return 1

    fresh = pd.concat(new_chunks, ignore_index=True) if new_chunks else pd.DataFrame(columns=OUTPUT_COLS)
    merged = pd.concat([existing, fresh], ignore_index=True)
    merged = (
        merged.dropna(subset=["ticker", "year_month"])
        .drop_duplicates(subset=["ticker", "year_month"], keep="last")
        .sort_values(["ticker", "year_month"])
        .reset_index(drop=True)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    logger.info("Wrote %s rows → %s", len(merged), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
