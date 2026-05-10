"""Fetch 三大法人 (foreign / investment trust / dealer) net flows via FinMind.

Hits FinMind's ``TaiwanStockInstitutionalInvestorsBuySell`` once per universe
ticker and pivots to wide form before persisting.

Output schema (`data/manual/institutional_flow.csv`):
    ticker, date, foreign_net, trust_net, dealer_net, total_net

Used by ``scoring_model.SignalContext.foreign_net_30d_positive`` to add a
"price action confirmed by foreign buying" signal to the decision score.
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

logger = get_logger("fetch_institutional_flow")

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
DATASET = "TaiwanStockInstitutionalInvestorsBuySell"

OUTPUT_COLS = [
    "ticker",
    "date",
    "foreign_buy",
    "foreign_sell",
    "foreign_net",
    "trust_net",
    "dealer_net",
    "total_net",
]

# FinMind name → bucket
_BUCKET = {
    "Foreign_Investor": "foreign",
    "Foreign_Dealer_Self": "foreign",
    "Investment_Trust": "trust",
    "Dealer_self": "dealer",
    "Dealer_Hedging": "dealer",
    "Dealer": "dealer",
}


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
        logger.warning("FinMind fetch failed for %s: %s", bare, exc)
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _pivot_to_wide(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Long-form FinMind rows → one row per (ticker, date)."""
    if raw.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)
    raw = raw.copy()
    raw["bucket"] = raw["name"].map(_BUCKET).fillna("other")
    raw["buy"] = pd.to_numeric(raw.get("buy"), errors="coerce").fillna(0)
    raw["sell"] = pd.to_numeric(raw.get("sell"), errors="coerce").fillna(0)
    raw["net"] = raw["buy"] - raw["sell"]
    raw["date"] = pd.to_datetime(raw["date"]).dt.strftime("%Y-%m-%d")

    foreign = raw[raw["bucket"] == "foreign"].groupby("date").agg(
        foreign_buy=("buy", "sum"),
        foreign_sell=("sell", "sum"),
        foreign_net=("net", "sum"),
    )
    trust = raw[raw["bucket"] == "trust"].groupby("date")["net"].sum().rename("trust_net")
    dealer = raw[raw["bucket"] == "dealer"].groupby("date")["net"].sum().rename("dealer_net")

    wide = foreign.join(trust, how="outer").join(dealer, how="outer").reset_index()
    for col in ["foreign_buy", "foreign_sell", "foreign_net", "trust_net", "dealer_net"]:
        if col not in wide.columns:
            wide[col] = 0
        wide[col] = wide[col].fillna(0)
    wide["total_net"] = wide["foreign_net"] + wide["trust_net"] + wide["dealer_net"]
    wide["ticker"] = ticker
    return wide[OUTPUT_COLS]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2022-01-01")
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

    out_path = resolve_path("data/manual/institutional_flow.csv")
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
        wide = _pivot_to_wide(raw, ticker)
        if not wide.empty:
            chunks.append(wide)
            logger.info("  → %s rows", len(wide))

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
