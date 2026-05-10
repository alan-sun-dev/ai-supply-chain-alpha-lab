#!/usr/bin/env python
"""Out-of-regime stress test CLI."""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from capex_alpha.utils import get_logger
from capex_alpha.validation import regime_stress as rs

logger = get_logger("capex_alpha")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Out-of-regime stress test (analysis only)")
    p.add_argument("--results", default="data/output/walk_forward_v2_results.csv")
    p.add_argument("--benchmark", default="data/output/walk_forward_v2_benchmark.csv")
    p.add_argument("--ai-index", default="data/output/ai_factor_index.csv")
    p.add_argument("--output-dir", default="data/output")
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--max-per-theme", type=int, default=2)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out = rs.run(
        results_csv=args.results,
        benchmark_csv=args.benchmark,
        ai_index_csv=args.ai_index,
        output_dir=args.output_dir,
        max_per_theme=args.max_per_theme,
        top_n=args.top_n,
    )

    print()
    print("=" * 95)
    print("REGIME STRESS — CALENDAR WINDOWS")
    print("=" * 95)
    cal = out["calendar"].copy()
    cal_display = cal[[
        "name", "n_months", "cagr", "sharpe", "max_dd",
        "monthly_hit_rate", "total_return",
        "benchmark_total", "ai_index_total",
        "excess_vs_benchmark_total", "excess_vs_ai_total",
        "avg_one_way_turnover",
    ]]
    print(cal_display.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=" * 95)
    print("EVENT-CONDITIONAL REGIMES")
    print("=" * 95)
    print(out["event"].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=" * 95)
    print("WORST 5 MONTHS")
    print("=" * 95)
    print(out["worst"][["month", "port_return", "benchmark_return", "vs_benchmark", "themes"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=" * 95)
    print("BEST 5 MONTHS")
    print("=" * 95)
    print(out["best"][["month", "port_return", "benchmark_return", "vs_benchmark", "themes"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=" * 95)
    print("RISK_PENALTY EFFECT BY REGIME")
    print("=" * 95)
    rp = out["risk_penalty_effect"]
    print(rp[["regime", "n_months",
              "with_risk_cagr", "no_risk_cagr",
              "with_risk_sharpe", "no_risk_sharpe",
              "with_risk_max_dd", "no_risk_max_dd",
              "dd_improvement_pts", "cagr_cost_pts"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=" * 95)
    print("RESIDUAL_ALPHA-ONLY BY REGIME (does residual α work outside AI mania?)")
    print("=" * 95)
    print(out["residual_alpha_only"]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
