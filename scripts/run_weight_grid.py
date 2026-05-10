#!/usr/bin/env python
"""Phase A2 — weight grid search on top of A1 walk-forward results.

Examples
--------
    .venv/bin/python scripts/run_weight_grid.py
    .venv/bin/python scripts/run_weight_grid.py --top-n 5 --k 10
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from capex_alpha.utils import ensure_dir, resolve_path, get_logger
from capex_alpha.validation import weight_grid as wg

logger = get_logger("capex_alpha")


def _fmt(x, dec=3):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    return f"{float(x):.{dec}f}"


def _pct(x):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{float(x) * 100:.1f}%"


def _render_report(grid: pd.DataFrame, baseline: pd.DataFrame, top: pd.DataFrame) -> str:
    L: list[str] = []
    L.append("# Phase A2 — Weight Grid Search Results")
    L.append(f"_Cells: {len(grid)}.  Train ≤ 2023-12-29 (43 months).  Test ≥ 2024-01-31 (28 months).  "
             f"Robustness filter: test_sharpe ≥ {wg.ROBUSTNESS_THRESHOLD:.0%} × train_sharpe.  "
             f"Strong filter: ≥ {wg.MIN_STRONG_OBS} obs._\n")

    n_robust = int(grid["passes_robust"].sum())
    n_all = int(grid["passes_all"].sum())
    L.append(f"- Cells passing robustness filter: **{n_robust}** / {len(grid)}  ({n_robust/len(grid):.1%})")
    L.append(f"- Cells passing both filters:      **{n_all}** / {len(grid)}  ({n_all/len(grid):.1%})\n")

    # ---- Baseline (A1) row
    L.append("## A1 baseline (recomputed from grid)")
    if baseline.empty:
        L.append("_A1 row not found in grid._")
    else:
        b = baseline.iloc[0]
        L.append(f"- Weights: ra={b['ra_w']:.2f}, rev={b['rev_w']:.2f}, flw={b['flw_w']:.2f}, "
                 f"risk×={b['risk_mult']:.2f}, min_alpha={b['min_alpha']:.1f}")
        L.append(f"- Train: Sharpe `{_fmt(b['train_sharpe'])}`, "
                 f"max DD `{_pct(b['train_max_dd'])}`, total `{_pct(b['train_total'])}`")
        L.append(f"- Test:  Sharpe `{_fmt(b['test_sharpe'])}`, "
                 f"max DD `{_pct(b['test_max_dd'])}`, total `{_pct(b['test_total'])}`")
        L.append(f"- Robust ratio: `{_fmt(b['robust_ratio'])}`")
        L.append(f"- Strong: n=`{int(b['strong_n_full'])}`, unique=`{int(b['strong_unique'])}`, "
                 f"hit=`{_pct(b['strong_hit'])}`, mean=`{_pct(b['strong_mean'])}`")
    L.append("")

    # ---- Top-K combos
    L.append("## Top combos (passing all filters, ranked by train Sharpe)")
    if top.empty:
        L.append("_No combos passed all filters._\n")
    else:
        L.append("| Rank | ra_w | rev_w | flw_w | risk× | min_α | "
                 "train Sharpe | train DD | train Total | test Sharpe | test DD | test Total | "
                 "robust | Strong n / unique / hit |")
        L.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:--|")
        for i, (_, r) in enumerate(top.iterrows(), 1):
            L.append(
                f"| {i} | {r['ra_w']:.2f} | {r['rev_w']:.2f} | {r['flw_w']:.2f} | "
                f"{r['risk_mult']:.2f} | {r['min_alpha']:.1f} | "
                f"{_fmt(r['train_sharpe'])} | {_pct(r['train_max_dd'])} | {_pct(r['train_total'])} | "
                f"{_fmt(r['test_sharpe'])} | {_pct(r['test_max_dd'])} | {_pct(r['test_total'])} | "
                f"{_fmt(r['robust_ratio'])} | {int(r['strong_n_full'])} / {int(r['strong_unique'])} / "
                f"{_pct(r['strong_hit'])} |"
            )
        L.append("")

    # ---- Sensitivity per dimension
    L.append("## Sensitivity per dimension (median of robust-passing cells)")
    survivors = grid[grid["passes_robust"]]
    if not survivors.empty:
        for dim in ["ra_w", "rev_w", "flw_w", "risk_mult", "min_alpha"]:
            agg = survivors.groupby(dim).agg(
                cells=("train_sharpe", "size"),
                train_sharpe_med=("train_sharpe", "median"),
                test_sharpe_med=("test_sharpe", "median"),
                test_total_med=("test_total", "median"),
                test_dd_med=("test_max_dd", "median"),
            ).round(3)
            L.append(f"\n**By `{dim}`:**\n")
            L.append("| value | cells | train Sharpe (med) | test Sharpe (med) | test total (med) | test DD (med) |")
            L.append("|---:|---:|---:|---:|---:|---:|")
            for v, row in agg.iterrows():
                L.append(f"| {v} | {int(row['cells'])} | {_fmt(row['train_sharpe_med'])} | "
                         f"{_fmt(row['test_sharpe_med'])} | {_pct(row['test_total_med'])} | "
                         f"{_pct(row['test_dd_med'])} |")
    L.append("")

    # ---- Recommendation
    L.append("## Recommendation")
    if not top.empty:
        best = top.iloc[0]
        L.append(f"Best combo by train Sharpe (also passes both filters):")
        L.append(f"```yaml")
        L.append(f"tier_weights:")
        L.append(f"  residual_alpha_score:        {best['ra_w']:.2f}")
        L.append(f"  revenue_confirmation_score:  {best['rev_w']:.2f}")
        L.append(f"  sector_relative_score:       0.00   # Phase A1: removed")
        L.append(f"  institutional_flow_score:    {best['flw_w']:.2f}")
        L.append(f"  narrative_score:             0.00   # Phase A1: removed")
        L.append(f"  capex_context_score:         0.05")
        L.append(f"# risk_penalty multiplier (apply in scoring): {best['risk_mult']:.2f}")
        L.append(f"# decision_zones[Strong].min_alpha:           {best['min_alpha']:.1f}")
        L.append(f"```")
        L.append("")
        L.append(f"- Train: Sharpe `{_fmt(best['train_sharpe'])}` / DD `{_pct(best['train_max_dd'])}` / total `{_pct(best['train_total'])}`")
        L.append(f"- Test:  Sharpe `{_fmt(best['test_sharpe'])}` / DD `{_pct(best['test_max_dd'])}` / total `{_pct(best['test_total'])}`")
        L.append(f"- Robust ratio: `{_fmt(best['robust_ratio'])}` (>= {wg.ROBUSTNESS_THRESHOLD})")
        L.append(f"- Strong Candidate: n=`{int(best['strong_n_full'])}`, unique=`{int(best['strong_unique'])}`, "
                 f"hit=`{_pct(best['strong_hit'])}`")
    else:
        L.append("**No combo passed both robustness and Strong-sample filters.** Inspect sensitivity tables above and consider:")
        L.append("- Relaxing Strong sample minimum")
        L.append("- Widening grid bounds on the dimension with the strongest signal")
    return "\n".join(L)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase A2 weight grid search")
    p.add_argument("--top-n", type=int, default=5, help="Top-N portfolio size")
    p.add_argument("--k", type=int, default=10, help="Number of top combos to report")
    p.add_argument("--results", type=str, default="data/output/walk_forward_v2_results.csv",
                   help="Path to walk_forward_v2_results.csv from A1 run")
    p.add_argument("--no-write", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    path = resolve_path(args.results)
    if not path.exists():
        print(f"ERROR: results file not found: {path}", file=sys.stderr)
        print("Run scripts/run_walk_forward_v2.py first (under A1 weights).", file=sys.stderr)
        return 1

    logger.info("Loading %s", path)
    df = pd.read_csv(path, parse_dates=["rebalance_date"])
    logger.info("Loaded %d rows, %d unique rebalance dates",
                len(df), df["rebalance_date"].nunique())

    grid = wg.run_grid(df, top_n=args.top_n)
    if not args.no_write:
        wg.write(grid)

    baseline = wg.baseline_a1_row(grid)
    top = wg.top_combos(grid, k=args.k)

    text = _render_report(grid, baseline, top)
    if not args.no_write:
        ensure_dir("reports")
        report_path = resolve_path("reports/phase_a2_grid_results.md")
        report_path.write_text(text, encoding="utf-8")
        logger.info("Wrote %s", report_path)

    # Console summary
    print()
    print("=" * 80)
    print(f"PHASE A2 WEIGHT GRID — {len(grid)} cells")
    print("=" * 80)
    print()
    if not baseline.empty:
        b = baseline.iloc[0]
        print(f"A1 baseline      : train_S={b['train_sharpe']:.3f}  test_S={b['test_sharpe']:.3f}  "
              f"test_total={b['test_total']:.1%}  test_DD={b['test_max_dd']:.1%}  robust={b['robust_ratio']:.2f}")
    print()
    n_robust = int(grid["passes_robust"].sum())
    n_strong = int(grid["passes_strong"].sum())
    n_all = int(grid["passes_all"].sum())
    print(f"Cells passing robustness filter (test ≥ 80% × train Sharpe): {n_robust}/{len(grid)}")
    print(f"Cells passing Strong sample filter (n ≥ {wg.MIN_STRONG_OBS}):              {n_strong}/{len(grid)}")
    print(f"Cells passing BOTH:                                       {n_all}/{len(grid)}")
    print()
    print(f"TOP {min(args.k, len(top))} COMBOS (ranked by train Sharpe, all filters pass)")
    print("-" * 80)
    if not top.empty:
        cols = ["ra_w", "rev_w", "flw_w", "risk_mult", "min_alpha",
                "train_sharpe", "test_sharpe", "robust_ratio",
                "test_total", "test_max_dd",
                "strong_n_full", "strong_unique", "strong_hit"]
        print(top[cols].to_string(index=False))
    else:
        print("(none — see report)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
