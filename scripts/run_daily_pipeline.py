#!/usr/bin/env python
"""CLI entrypoint for the v2 daily pipeline.

Examples
--------
    .venv/bin/python scripts/run_daily_pipeline.py
    .venv/bin/python scripts/run_daily_pipeline.py --skip-fetch --top-n 20 --debug
"""
from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from capex_alpha.automation.run_daily_pipeline import run_pipeline
from capex_alpha.utils import get_logger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="v2 daily pipeline")
    p.add_argument("--skip-fetch", action="store_true", help="Skip yfinance refresh (uses cache).")
    p.add_argument("--date", type=str, default=None, help="As-of date (YYYY-MM-DD).")
    p.add_argument("--top-n", type=int, default=20, help="Top-N to display in report.")
    p.add_argument("--debug", action="store_true", help="Verbose logging.")
    p.add_argument("--no-write", action="store_true", help="Do not write outputs.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger = get_logger("capex_alpha")
    if args.debug:
        logger.setLevel(logging.DEBUG)

    as_of = pd.Timestamp(args.date) if args.date else None
    res = run_pipeline(write=not args.no_write, skip_fetch=args.skip_fetch, as_of=as_of)

    print()
    print("=" * 72)
    print(f"DAILY PIPELINE COMPLETE")
    print("=" * 72)
    if not res.ranking.empty:
        print(f"Universe size:     {len(res.ranking)}")
        print(f"Strong Candidates: {(res.ranking['decision_zone']=='Strong Candidate').sum()}")
        print(f"Watchlist:         {(res.ranking['decision_zone']=='Watchlist').sum()}")
        print(f"Narrative Watch:   {(res.ranking['decision_zone']=='Narrative Watch').sum()}")
        print(f"Avoid:             {(res.ranking['decision_zone'].isin(['Avoid','Avoid Chasing'])).sum()}")
        print()
        print(f"Top {min(args.top_n, len(res.ranking))} by alpha_score:")
        cols = ["rank", "ticker", "company_name", "theme", "alpha_score", "confidence_score", "decision_zone"]
        print(res.ranking[cols].head(args.top_n).to_string(index=False))
    if res.payload:
        print()
        regime = res.payload.get("market_regime", {})
        print(f"Regime: {regime.get('market_regime','?')} / AI {regime.get('ai_regime','?')} / risk {regime.get('risk_level','?')}")
        print(f"Recommended gross exposure: {regime.get('recommended_gross_exposure','?')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
