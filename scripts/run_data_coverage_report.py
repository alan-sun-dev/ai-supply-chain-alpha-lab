#!/usr/bin/env python
"""Phase B3 — per-ticker per-factor coverage report.

    .venv/bin/python scripts/run_data_coverage_report.py
    .venv/bin/python scripts/run_data_coverage_report.py --output-dir data/output --tag pre_b3
"""
from __future__ import annotations

import argparse
import sys

from capex_alpha import data_quality as dq
from capex_alpha.utils import ensure_dir, resolve_path, get_logger

logger = get_logger("capex_alpha")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FinMind data coverage report")
    p.add_argument("--output-dir", type=str, default="data/output")
    p.add_argument("--tag", type=str, default=None,
                   help="Optional tag appended to output filename (e.g. 'pre_b3')")
    p.add_argument("--tier2-min-obs", type=int, default=24,
                   help="Minimum obs threshold for tier2_complete flag")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = dq.coverage_report(tier2_min_obs=args.tier2_min_obs)
    summary = dq.coverage_summary(report)

    ensure_dir(args.output_dir)
    name = "data_coverage_report" + (f"_{args.tag}" if args.tag else "") + ".csv"
    path = resolve_path(f"{args.output_dir}/{name}")
    report.to_csv(path, index=False)
    logger.info("Wrote %s (%d rows)", path, len(report))

    print()
    print("=" * 72)
    print("DATA COVERAGE SUMMARY")
    print("=" * 72)
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k:30s}: {v:.3f}")
        else:
            print(f"  {k:30s}: {v}")
    print()
    # Tickers with any missing tier-2
    incomplete = report[~report["tier2_complete"]].copy()
    if not incomplete.empty:
        print(f"INCOMPLETE TIER-2 ({len(incomplete)} tickers):")
        for _, r in incomplete.iterrows():
            missing = []
            if r["revenue_n"] < args.tier2_min_obs:
                missing.append(f"revenue={r['revenue_n']}")
            if r["flow_n"] < args.tier2_min_obs:
                missing.append(f"flow={r['flow_n']}")
            if r["valuation_n"] < args.tier2_min_obs:
                missing.append(f"val={r['valuation_n']}")
            print(f"  {r['ticker']:12s} {r['theme']:25s} → {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
