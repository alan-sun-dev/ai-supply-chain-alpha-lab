#!/usr/bin/env python
"""Run v2 walk-forward validation + ablation + report.

Examples
--------
    .venv/bin/python scripts/run_walk_forward_v2.py
    .venv/bin/python scripts/run_walk_forward_v2.py --start 2022-01-31 --end 2026-04-30
    .venv/bin/python scripts/run_walk_forward_v2.py --top-n 5 --debug
"""
from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from capex_alpha.utils import get_logger
from capex_alpha.validation import ablation as ab
from capex_alpha.validation import validation_report as vr
from capex_alpha.validation import walk_forward_v2 as wf


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="v2 walk-forward validation")
    p.add_argument("--start", type=str, default="2020-06-30")
    p.add_argument("--end", type=str, default=None)
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--no-write", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger = get_logger("capex_alpha")
    if args.debug:
        logger.setLevel(logging.DEBUG)

    res = wf.run(start=args.start, end=args.end, write=not args.no_write, progress=True)
    results = res["results"]
    benchmark = res.get("benchmark", pd.Series(dtype=float))

    if results.empty:
        print("No results produced.")
        return 1

    outputs = ab.write_outputs(results, benchmark_returns=benchmark)
    bench_stats = ab.benchmark_stats(benchmark)

    text = vr.render(
        results=results,
        ablation=outputs["ablation"],
        zone_perf=outputs["zone_perf"],
        decile_perf=outputs["decile_perf"],
        risk_attr=outputs["risk_attr"],
        narrative_attr=outputs["narrative_attr"],
        gate_attr=outputs["gate_attr"],
        benchmark_stats=bench_stats,
    )

    if not args.no_write:
        vr.write_report(text)

    # Console summary
    print()
    print("=" * 78)
    print(f"WALK-FORWARD v2 VALIDATION  ({args.start} → {results['rebalance_date'].max().date()})")
    print("=" * 78)
    print()
    print("DECISION ZONE PERFORMANCE")
    print("-" * 78)
    print(outputs["zone_perf"].to_string(index=False))
    print()
    print("ABLATION (top-5 portfolio)")
    print("-" * 78)
    cols = ["name", "spearman_rho", "spearman_p", "spread", "portfolio_sharpe_ann",
            "portfolio_max_dd", "portfolio_total_return"]
    print(outputs["ablation"][cols].to_string(index=False))
    print()
    print("RISK PENALTY ATTRIBUTION")
    print("-" * 78)
    print(outputs["risk_attr"].to_string(index=False))
    print()
    print("NARRATIVE ATTRIBUTION")
    print("-" * 78)
    print(outputs["narrative_attr"].to_string(index=False))
    print()
    print("GATE ATTRIBUTION (top-5 with vs without zone filter)")
    print("-" * 78)
    print(outputs["gate_attr"].to_string(index=False))
    if bench_stats:
        print()
        print(f"Benchmark 0050.TW: total_return={bench_stats['total_return']:.1%}, "
              f"Sharpe={bench_stats['sharpe_ann']:.2f}, max_dd={bench_stats['max_dd']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
