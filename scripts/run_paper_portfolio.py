#!/usr/bin/env python
"""Paper Portfolio MVP CLI — shadow tracking only, no real execution.

Examples
--------
    # First-time setup: replay all walk-forward history into paper portfolio
    .venv/bin/python scripts/run_paper_portfolio.py --backfill

    # Monthly operational rebalance (uses current alpha_ranking.csv)
    .venv/bin/python scripts/run_paper_portfolio.py --rebalance \
        --date 2026-04-30 --notes "May rebalance, normal cycle"

    # Re-render the markdown report from current state
    .venv/bin/python scripts/run_paper_portfolio.py --report
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from capex_alpha import paper_portfolio as pp
from capex_alpha.utils import get_logger, resolve_path

logger = get_logger("capex_alpha")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Paper Portfolio MVP")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backfill", action="store_true",
                      help="Replay walk_forward_v2_results.csv as paper portfolio history")
    mode.add_argument("--rebalance", action="store_true",
                      help="Append one new rebalance using current alpha_ranking.csv")
    mode.add_argument("--report", action="store_true",
                      help="Re-render markdown report from current state")
    p.add_argument("--date", type=str, default=None,
                   help="Rebalance date for --rebalance (default: today)")
    p.add_argument("--notes", type=str, default="",
                   help="Free-form notes appended to the rebalance row")
    p.add_argument("--results", type=str,
                   default="data/output/walk_forward_v2_results.csv",
                   help="Walk-forward results CSV (used by --backfill)")
    p.add_argument("--ranking", type=str,
                   default="data/output/alpha_ranking.csv",
                   help="Alpha ranking CSV (used by --rebalance)")
    p.add_argument("--risk-flags", type=str,
                   default="data/output/risk_flags.csv")
    p.add_argument("--output-dir", type=str, default=pp.DEFAULT_PAPER_DIR)
    p.add_argument("--report-path", type=str, default=pp.DEFAULT_REPORT_PATH)
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--max-per-theme", type=int, default=2)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.backfill:
        results_p = resolve_path(args.results)
        if not results_p.exists():
            print(f"ERROR: walk-forward results not found at {results_p}", file=sys.stderr)
            return 1
        wf = pd.read_csv(results_p, parse_dates=["rebalance_date"])
        risk_p = resolve_path(args.risk_flags)
        risk_df = pd.read_csv(risk_p) if risk_p.exists() else None

        state = pp.backfill_from_walk_forward(
            walk_forward_df=wf,
            risk_flags_df=risk_df,
            top_n=args.top_n,
            max_per_theme=args.max_per_theme,
            output_dir=args.output_dir,
            write=True,
        )
        text = pp.render_report(state, output_path=args.report_path)

    elif args.rebalance:
        date = pd.Timestamp(args.date) if args.date else pd.Timestamp.today().normalize()
        state = pp.run_one_rebalance(
            rebalance_date=date,
            ranking_csv=args.ranking,
            risk_flags_csv=args.risk_flags,
            output_dir=args.output_dir,
            top_n=args.top_n,
            max_per_theme=args.max_per_theme,
            notes=args.notes,
            write=True,
        )
        text = pp.render_report(state, output_path=args.report_path)

    elif args.report:
        state = pp.load_state(args.output_dir)
        text = pp.render_report(state, output_path=args.report_path)

    # Console summary
    state = pp.load_state(args.output_dir)
    print()
    print("=" * 80)
    print("PAPER PORTFOLIO STATE")
    print("=" * 80)
    print(f"Rebalances tracked:   {state.n_rebalances}")
    if state.latest_rebalance_date is not None:
        print(f"Latest rebalance:     {state.latest_rebalance_date.strftime('%Y-%m-%d')}")
        latest = state.log.iloc[-1]
        print(f"Paper NAV (gross):    {float(latest['nav_paper']):.4f}")
        print(f"Paper NAV @ 25 bps:   {float(latest['nav_paper_25bps']):.4f}")
        print(f"Paper NAV @ 50 bps:   {float(latest['nav_paper_50bps']):.4f}")
        print(f"Benchmark NAV:        {float(latest['nav_benchmark']):.4f}")
        print(f"Drawdown (paper):     {float(latest['drawdown_paper'])*100:.2f}%")
    print()
    print(f"Files written:")
    out_dir = resolve_path(args.output_dir)
    for fname in ("portfolio.csv", "target_weights.csv", "rebalance_log.csv"):
        path = out_dir / fname
        if path.exists():
            print(f"  {path}  ({path.stat().st_size} bytes)")
    print(f"  {resolve_path(args.report_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
