"""Fetch daily PER / PBR / dividend yield via FinMind ``TaiwanStockPER``.

Same pattern as fetch_monthly_revenue.py and fetch_institutional_flow.py:
read universe → call FinMind per-ticker → merge against existing CSV.

Output schema (`data/manual/valuation.csv`):
    ticker, date, per, pbr, dividend_yield

Used by ``scoring_model`` to add valuation-extreme signals (cheap PE /
stretched PE / stretched PB) to the decision score.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capex_alpha.data_loader import load_universe  # noqa: E402
from capex_alpha.utils import (  # noqa: E402
    get_logger,
    load_data_sources_config,
    resolve_path,
)

logger = get_logger("fetch_valuation")

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
DATASET = "TaiwanStockPER"

OUTPUT_COLS = ["ticker", "date", "per", "pbr", "dividend_yield"]


def _bare_ticker(ticker: str) -> str:
    return ticker.split(".")[0].strip()


def _fetch_one(bare: str, start: str, end: str, token: str | None, timeout: int) -> pd.DataFrame:
    import requests

    params = {"dataset": DATASET, "data_id": bare, "start_date": start, "end_date": end}
    if token:
        params["token"] = token
    try:
        resp = requests.get(FINMIND_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        rows = resp.json().get("data") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("FinMind PER fetch failed for %s: %s", bare, exc)
        return pd.DataFrame()
    if not rows:
        logger.warning("No FinMind PER data for %s in [%s, %s]", bare, start, end)
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _normalise(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["per"] = pd.to_numeric(df.get("PER"), errors="coerce")
    df["pbr"] = pd.to_numeric(df.get("PBR"), errors="coerce")
    df["dividend_yield"] = pd.to_numeric(df.get("dividend_yield"), errors="coerce")
    df["ticker"] = ticker
    df = df.dropna(subset=["per", "pbr"], how="all")
    return df[OUTPUT_COLS]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--token", default=None)
    parser.add_argument("--timeout", default=20, type=int)
    args = parser.parse_args()

    cfg = load_data_sources_config()["sources"].get("finmind", {})
    token = args.token or cfg.get("token")

    universe = load_universe()
    if universe.empty:
        logger.error("Universe is empty.")
        return 1

    out_path = resolve_path("data/manual/valuation.csv")
    existing = pd.DataFrame(columns=OUTPUT_COLS)
    if out_path.exists():
        try:
            existing = pd.read_csv(out_path, dtype={"ticker": str})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read existing CSV (%s).", exc)

    chunks: list[pd.DataFrame] = []
    for _, row in universe.iterrows():
        ticker = row["ticker"]
        bare = _bare_ticker(ticker)
        if not bare:
            continue
        logger.info("Fetching %s (%s)…", ticker, bare)
        raw = _fetch_one(bare, args.start, args.end, token, args.timeout)
        norm = _normalise(raw, ticker)
        if not norm.empty:
            chunks.append(norm)
            logger.info("  → %s rows", len(norm))

    if not chunks and existing.empty:
        logger.warning("No data fetched and no existing rows; nothing written.")
        return 1

    fresh = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=OUTPUT_COLS)
    merged = pd.concat([existing, fresh], ignore_index=True)
    merged = (
        merged.dropna(subset=["ticker", "date"])
        .drop_duplicates(subset=["ticker", "date"], keep="last")
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    logger.info("Wrote %s rows → %s", len(merged), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
