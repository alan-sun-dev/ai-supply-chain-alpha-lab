#!/usr/bin/env python
"""A2-rerun on post-B3 data.

Same weight_grid module as Phase A2, but:
- Widened GRID (rev=0 and flw=0 now searchable)
- Adds zone-bucket hit rates, turnover, 25-bps net CAGR per cell
- Applies Step-1 theme cap during top-N selection

Does NOT change any YAML — output is data only, for manual review.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from capex_alpha.data_loader import load_universe
from capex_alpha.utils import ensure_dir, get_logger, resolve_path
from capex_alpha.validation import portfolio_metrics as pm
from capex_alpha.validation import weight_grid as wg

logger = get_logger("capex_alpha")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A2-rerun on post-B3 data")
    p.add_argument("--results", type=str, default="data/output/walk_forward_v2_results.csv")
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--k", type=int, default=15)
    p.add_argument("--no-write", action="store_true")
    return p.parse_args(argv)


def _fmt(x, dec=3):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    return f"{float(x):.{dec}f}"


def _pct(x, dec=1):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{float(x) * 100:.{dec}f}%"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    path = resolve_path(args.results)
    if not path.exists():
        print(f"ERROR: {path} not found.", file=sys.stderr)
        return 1
    df = pd.read_csv(path, parse_dates=["rebalance_date"])
    logger.info("Loaded %d rows, %d unique rebalance dates",
                len(df), df["rebalance_date"].nunique())

    # Pull theme map from active universe (= expanded_liquid_60)
    universe = load_universe()
    theme_map = universe.set_index("ticker")["theme"].to_dict()
    cap = pm.load_theme_cap_config()
    logger.info("Active universe: %d tickers; theme cap=%s, max_per_theme=%d",
                len(universe), cap["enable_theme_cap"], cap["max_per_theme"])

    grid = wg.run_grid(
        df,
        top_n=args.top_n,
        theme_map=theme_map if cap["enable_theme_cap"] else None,
        max_per_theme=cap["max_per_theme"] if cap["enable_theme_cap"] else None,
    )
    if not args.no_write:
        ensure_dir("data/output")
        grid.to_csv(resolve_path("data/output/a2_rerun_grid_results.csv"), index=False)
        logger.info("Wrote a2_rerun_grid_results.csv (%d cells)", len(grid))

    # ----- summaries -----
    n_cells = len(grid)
    n_robust = int(grid["passes_robust"].sum())
    n_strong = int(grid["passes_strong"].sum())
    n_all = int(grid["passes_all"].sum())

    # current active baseline row
    baseline = grid[(grid["ra_w"] == 0.35) & (grid["rev_w"] == 0.30) &
                    (grid["flw_w"] == 0.10) & (grid["risk_mult"] == 1.0) &
                    (grid["min_alpha"] == 2.5)]
    # residual_alpha_only (ra=0.50, rev=0, flw=0, risk×=1.0)
    ra_only = grid[(grid["rev_w"] == 0.0) & (grid["flw_w"] == 0.0) &
                   (grid["risk_mult"] == 1.0) & (grid["min_alpha"] == 2.5)]
    no_rev = grid[(grid["rev_w"] == 0.0) & (grid["risk_mult"] == 1.0) &
                  (grid["min_alpha"] == 2.5)]

    # Top combos by train Sharpe (filtered)
    top_train = grid[grid["passes_all"]].sort_values("train_sharpe", ascending=False).head(args.k)
    # Top combos by test Sharpe
    top_test = grid[grid["passes_all"]].sort_values("test_sharpe", ascending=False).head(args.k)
    # Top combos by net 25-bps CAGR
    top_net = grid[grid["passes_all"]].sort_values("net_cagr_25bps", ascending=False).head(args.k)
    # Robust + simple: passes all, then prefer simpler (more zero weights), then test_sharpe
    robust_simple = grid[grid["passes_all"]].copy()
    robust_simple = robust_simple.sort_values(
        ["n_zero_weights", "test_sharpe"], ascending=[False, False]
    ).head(args.k)

    # Console
    print()
    print("=" * 80)
    print(f"A2-RERUN ON POST-B3 DATA — {n_cells} cells")
    print("=" * 80)
    print(f"Cells passing robustness  (test ≥ 80% × train): {n_robust:5d}/{n_cells} ({n_robust/n_cells:.0%})")
    print(f"Cells passing Strong-sample (n ≥ 15):           {n_strong:5d}/{n_cells} ({n_strong/n_cells:.0%})")
    print(f"Cells passing both filters:                     {n_all:5d}/{n_cells} ({n_all/n_cells:.0%})")
    print()

    cols_brief = ["ra_w", "rev_w", "flw_w", "risk_mult", "min_alpha",
                  "train_sharpe", "test_sharpe", "robust_ratio",
                  "full_sharpe", "full_max_dd",
                  "annualised_turnover", "net_cagr_25bps",
                  "strong_n_full", "strong_hit",
                  "watch_n_full", "watch_hit_full"]

    print("CURRENT ACTIVE BASELINE")
    print("-" * 80)
    if not baseline.empty:
        print(baseline[cols_brief].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()

    print(f"TOP {min(args.k, len(top_train))} BY TRAIN SHARPE (passes both filters)")
    print("-" * 80)
    print(top_train[cols_brief].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()

    print(f"TOP {min(args.k, len(top_test))} BY TEST SHARPE")
    print("-" * 80)
    print(top_test[cols_brief].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()

    print(f"TOP {min(args.k, len(top_net))} BY NET CAGR @ 25 BPS")
    print("-" * 80)
    print(top_net[cols_brief].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()

    print(f"SIMPLEST ROBUST COMBOS (most zero weights, then test_sharpe)")
    print("-" * 80)
    print(robust_simple[cols_brief].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
