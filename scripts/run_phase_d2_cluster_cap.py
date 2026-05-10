#!/usr/bin/env python
"""Phase D2 — AI-infrastructure cluster cap CLI."""
from __future__ import annotations

import argparse
import sys

import numpy as np

from capex_alpha.utils import get_logger
from capex_alpha.validation import cluster_cap as cc

logger = get_logger("capex_alpha")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase D2 cluster cap (analysis only)")
    p.add_argument("--results", default="data/output/walk_forward_v2_results.csv")
    p.add_argument("--ai-index", default="data/output/ai_factor_index.csv")
    p.add_argument("--output-dir", default="data/output")
    p.add_argument("--caps", default="0.50,0.60,0.70",
                   help="Comma-separated cap fractions to test")
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--max-per-theme", type=int, default=2)
    p.add_argument("--momentum-threshold", type=float, default=0.05,
                   help="AI index forward return threshold to define 'momentum month'")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cap_pcts = [float(c.strip()) for c in args.caps.split(",")]
    out = cc.run(
        results_csv=args.results,
        ai_index_csv=args.ai_index,
        output_dir=args.output_dir,
        cap_pcts=cap_pcts,
        top_n=args.top_n,
        max_per_theme=args.max_per_theme,
        momentum_threshold=args.momentum_threshold,
    )

    print()
    print("=" * 100)
    print("PHASE D2 — AI-INFRASTRUCTURE CLUSTER CAP (analysis only)")
    print("=" * 100)
    print(f"Cluster themes: {sorted(cc.CLUSTER_THEMES_DEFAULT)}")
    print()

    summary = out["summary"]
    cols = ["label", "n_months", "cagr", "sharpe_ann", "calmar", "max_dd",
            "monthly_hit_rate", "worst_month", "months_in_drawdown",
            "longest_recovery_mo", "n_dd_episodes", "total_return"]
    print("=== METRICS BY VARIANT ===")
    print(summary[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=== CLUSTER EXPOSURE PATH (avg per variant) ===")
    expo = out["cluster_exposure"]
    if not expo.empty:
        agg = expo.groupby("variant").agg(
            mean_cluster_weight=("cluster_weight", "mean"),
            max_cluster_weight=("cluster_weight", "max"),
            n_months_at_max=("cluster_weight", lambda s: int((s == s.max()).sum())),
        ).reset_index()
        print(agg.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=== UPSIDE SACRIFICE DURING AI MOMENTUM MONTHS ===")
    print(f"AI momentum threshold: AI index fwd return > {args.momentum_threshold:.0%}")
    sac = out["upside_sacrifice"]
    if not sac.empty:
        cols_sac = ["variant", "n_months", "baseline_mean", "capped_mean",
                    "sacrifice_per_month", "sacrifice_total_pct"]
        print(sac[cols_sac].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=== WORST 5 MONTHS BY VARIANT ===")
    worst = out["worst_months"]
    if not worst.empty:
        cols_w = ["variant", "month", "port_return", "cluster_share", "themes"]
        print(worst[cols_w].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
