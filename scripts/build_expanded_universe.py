#!/usr/bin/env python
"""Phase C — fetch candidate prices, run liquidity filter, build expanded CSVs."""
from __future__ import annotations

import argparse
import sys

from capex_alpha.universe_expansion import (
    CANDIDATE_PATH_DEFAULT,
    DEFAULT_MIN_ADV_TWD,
    DEFAULT_MAX_MISSING_PCT,
    EXPANDED_PATH_DEFAULT,
    build_expanded_universes,
    liquidity_check,
    load_candidates,
)
from capex_alpha.utils import get_logger

logger = get_logger("capex_alpha")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build expanded universe + liquidity report")
    p.add_argument("--candidate-file", type=str, default=CANDIDATE_PATH_DEFAULT)
    p.add_argument("--output-universe", type=str, default=EXPANDED_PATH_DEFAULT)
    p.add_argument("--min-adv", type=float, default=DEFAULT_MIN_ADV_TWD,
                   help="Minimum average daily traded value in TWD (default 30M)")
    p.add_argument("--max-missing", type=float, default=DEFAULT_MAX_MISSING_PCT,
                   help="Max missing-data ratio (default 0.10)")
    p.add_argument("--keep-required", type=str, default="2330.TW",
                   help="Comma-separated tickers that always pass (default issuer 2330.TW)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates = load_candidates(args.candidate_file)
    logger.info("Loaded %d candidates after dedup.", len(candidates))

    liquidity = liquidity_check(candidates)
    logger.info("Liquidity check: %d data-available, %d data-missing",
                int(liquidity["data_available"].sum()),
                int((~liquidity["data_available"]).sum()))

    keep_req = [t.strip() for t in args.keep_required.split(",") if t.strip()]
    universes = build_expanded_universes(
        candidates, liquidity,
        output_path=args.output_universe,
        min_adv=args.min_adv,
        max_missing=args.max_missing,
        keep_required=keep_req,
    )

    print()
    print("=" * 72)
    print("PHASE C — EXPANDED UNIVERSE BUILT")
    print("=" * 72)
    print(f"Candidate count:                {len(candidates)}")
    print(f"Data-available:                 {int(liquidity['data_available'].sum())}")
    print(f"Tier A (ADV ≥ 100M):            {int((liquidity['liquidity_tier']=='A').sum())}")
    print(f"Tier B (30M ≤ ADV < 100M):      {int((liquidity['liquidity_tier']=='B').sum())}")
    print(f"Tier C (ADV < 30M):             {int((liquidity['liquidity_tier']=='C').sum())}")
    print(f"Tier X (no data):               {int((liquidity['liquidity_tier']=='X').sum())}")
    print()
    for name, df in universes.items():
        print(f"  {name:30s} : {len(df):3d} tickers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
