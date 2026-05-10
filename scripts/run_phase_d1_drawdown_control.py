#!/usr/bin/env python
"""Phase D1 — Drawdown Control MVP CLI.

Connects existing regime_filter recommendation into actual gross-exposure
scaling. Compares baseline vs exposure-scaled across CAGR / Sharpe /
Calmar / DD metrics + turnover + 25/50 bps cost.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

from capex_alpha.utils import get_logger
from capex_alpha.validation import exposure_overlay as ov

logger = get_logger("capex_alpha")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase D1 drawdown-control overlay")
    p.add_argument("--results", default="data/output/walk_forward_v2_results.csv")
    p.add_argument("--benchmark", default="data/output/walk_forward_v2_benchmark.csv")
    p.add_argument("--output-dir", default="data/output")
    return p.parse_args(argv)


def _fmt(x, dec=3):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    return f"{float(x):.{dec}f}"


def _pct(x, dec=2):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{float(x) * 100:.{dec}f}%"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out = ov.run(
        results_csv=args.results,
        benchmark_csv=args.benchmark,
        output_dir=args.output_dir,
    )

    print()
    print("=" * 80)
    print("PHASE D1 — DRAWDOWN CONTROL MVP (analysis only — no model changes)")
    print("=" * 80)

    summary = out["summary"]
    cols = ["label", "n_months", "cagr", "sharpe_ann", "calmar", "max_dd",
            "monthly_hit_rate", "worst_month", "months_in_drawdown",
            "longest_recovery_mo", "n_dd_episodes", "total_return"]
    print()
    print(summary[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("REGIME / EXPOSURE TIMELINE SUMMARY")
    print("-" * 80)
    rs = out["regime_summary"]
    print(rs.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("TURNOVER DECOMPOSITION (D1 scaled portfolio)")
    print("-" * 80)
    t = out["turnover_split"]
    print(f"  base name rotation (mean):   {_pct(t['base_mean'])}")
    print(f"  exposure change (mean):      {_pct(t['expo_mean'])}")
    print(f"  total monthly (mean):        {_pct(t['total_mean'])}")
    print(f"  base annualised:             {_fmt(t['base_ann'])}×")
    print(f"  total annualised:            {_fmt(t['total_ann'])}×")

    print()
    print("EXPOSURE PATH HEAD/TAIL (sanity check)")
    print("-" * 80)
    ep = out["exposure_path"][["regime_label", "regime_exposure",
                                "dd_override_applied", "applied_exposure",
                                "cash_weight", "raw_return", "scaled_return",
                                "strategy_dd_scaled"]]
    print("First 6 months:")
    print(ep.head(6).to_string(float_format=lambda x: f"{x:.4f}"))
    print("Last 6 months:")
    print(ep.tail(6).to_string(float_format=lambda x: f"{x:.4f}"))

    print()
    print(f"D1 DD EPISODES (peak → recovery)")
    print("-" * 80)
    print(f"Baseline episodes:     {len(out['base_episodes'])}")
    for e in out["base_episodes"]:
        end_str = e.end.strftime("%Y-%m") if e.end else "ongoing"
        print(f"  {e.start.strftime('%Y-%m')} → {end_str}: "
              f"{e.duration_months}m, max DD {e.max_dd:.2%}")
    print(f"D1-scaled episodes:    {len(out['scaled_episodes'])}")
    for e in out["scaled_episodes"]:
        end_str = e.end.strftime("%Y-%m") if e.end else "ongoing"
        print(f"  {e.start.strftime('%Y-%m')} → {end_str}: "
              f"{e.duration_months}m, max DD {e.max_dd:.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
