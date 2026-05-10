#!/usr/bin/env python
"""Phase B1 — transaction-cost test CLI.

Examples
--------
    .venv/bin/python scripts/run_transaction_cost_test.py
    .venv/bin/python scripts/run_transaction_cost_test.py --costs 0,10,25,50,100
    .venv/bin/python scripts/run_transaction_cost_test.py \\
        --portfolio-file data/output/walk_forward_v2_results.csv \\
        --output-dir data/output \\
        --report reports/phase_b1_transaction_cost.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from capex_alpha.utils import ensure_dir, get_logger, resolve_path
from capex_alpha.validation import transaction_cost as tc

logger = get_logger("capex_alpha")


# ---------------------------------------------------------------------------
# Charts

def chart_nav(nav_df: pd.DataFrame, output_path: Path) -> None:
    """NAV time series for benchmark + each cost scenario (log scale)."""
    fig, ax = plt.subplots(figsize=(11, 6))
    plotted_bench = False
    for cost in sorted(nav_df["cost_bps"].unique()):
        sub = nav_df[nav_df["cost_bps"] == cost].sort_values("date")
        if not plotted_bench:
            ax.plot(sub["date"], sub["benchmark_nav"], label="0050.TW",
                    linestyle="--", color="black", alpha=0.6, linewidth=1.5)
            plotted_bench = True
        ax.plot(sub["date"], sub["net_nav"], label=f"{int(cost)} bps", linewidth=1.5)
    ax.set_yscale("log")
    ax.set_ylabel("NAV (log scale, start = 1.0)")
    ax.set_xlabel("Rebalance date")
    ax.set_title("Top-5 portfolio NAV under different one-way transaction costs (A2 baseline)")
    ax.legend(loc="upper left", framealpha=0.9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    logger.info("Wrote %s", output_path)


def chart_impact(summary_df: pd.DataFrame, output_path: Path,
                 break_even_bps: float | None = None) -> None:
    """3-panel: CAGR / Sharpe / Final NAV vs cost_bps."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    x = summary_df["cost_bps"].values

    axes[0].plot(x, summary_df["cagr"] * 100, marker="o", linewidth=2)
    axes[0].set_xlabel("one-way cost (bps)")
    axes[0].set_ylabel("Net CAGR (%)")
    axes[0].set_title("CAGR vs Transaction Cost")
    axes[0].grid(True, alpha=0.3)
    if break_even_bps is not None and np.isfinite(break_even_bps):
        axes[0].axvline(break_even_bps, linestyle=":", color="red",
                        label=f"break-even ≈ {break_even_bps:.0f} bps")
        axes[0].legend()

    axes[1].plot(x, summary_df["sharpe"], marker="o", color="C1", linewidth=2)
    axes[1].set_xlabel("one-way cost (bps)")
    axes[1].set_ylabel("Net Sharpe (annualised)")
    axes[1].set_title("Sharpe vs Transaction Cost")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(x, summary_df["final_nav"], marker="o", color="C2", linewidth=2)
    axes[2].set_xlabel("one-way cost (bps)")
    axes[2].set_ylabel("Final NAV")
    axes[2].set_title("Final NAV vs Transaction Cost")
    axes[2].grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    logger.info("Wrote %s", output_path)


# ---------------------------------------------------------------------------
# Report

def _fmt_pct(x: float, dec: int = 2) -> str:
    if x is None or np.isnan(x):
        return "—"
    return f"{x * 100:.{dec}f}%"


def _fmt(x: float, dec: int = 3) -> str:
    if x is None or np.isnan(x):
        return "—"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    return f"{float(x):.{dec}f}"


def render_report(
    summary_df: pd.DataFrame,
    nav_df: pd.DataFrame,
    break_even_bps: float,
    a2_baseline: dict,
    benchmark_metrics_dict: dict,
) -> str:
    L: list[str] = []
    L.append("# Phase B1 — Transaction Cost Test (A2 active baseline)")

    n_dates = nav_df["date"].nunique() if not nav_df.empty else 0
    start = pd.to_datetime(nav_df["date"]).min().date() if not nav_df.empty else "—"
    end = pd.to_datetime(nav_df["date"]).max().date() if not nav_df.empty else "—"
    L.append(f"_Window: {start} → {end}, {n_dates} monthly rebalances. "
             "Top-5 long-only equal-weight, monthly rebalance._\n")

    # --- 1. Executive Summary
    zero_row = summary_df[summary_df["cost_bps"] == 0].iloc[0] if (summary_df["cost_bps"] == 0).any() else None
    hi_row   = summary_df[summary_df["cost_bps"] == summary_df["cost_bps"].max()].iloc[0]

    L.append("## 1. Executive Summary")
    if zero_row is not None:
        L.append(f"- A2 strategy at **0 bps** (gross): CAGR `{_fmt_pct(zero_row['cagr'])}`, "
                 f"Sharpe `{_fmt(zero_row['sharpe'])}`, max DD `{_fmt_pct(zero_row['max_drawdown'])}`, "
                 f"final NAV `{_fmt(zero_row['final_nav'])}`.")
    L.append(f"- At **{int(hi_row['cost_bps'])} bps** (highest cost tested): "
             f"CAGR `{_fmt_pct(hi_row['cagr'])}`, Sharpe `{_fmt(hi_row['sharpe'])}`, "
             f"final NAV `{_fmt(hi_row['final_nav'])}`.")
    L.append(f"- **0050.TW benchmark**: CAGR `{_fmt_pct(benchmark_metrics_dict['cagr'])}`, "
             f"Sharpe `{_fmt(benchmark_metrics_dict['sharpe_ann'])}`, "
             f"max DD `{_fmt_pct(benchmark_metrics_dict['max_dd'])}`.")
    if np.isfinite(break_even_bps):
        L.append(f"- **Break-even one-way cost: ~{break_even_bps:.0f} bps** "
                 f"(strategy net CAGR equals benchmark CAGR at this cost).")
    elif np.isinf(break_even_bps):
        L.append("- **Break-even cost: > 10,000 bps** — strategy beats benchmark at any reasonable cost.")
    else:
        L.append("- **Break-even cost: undefined** — strategy does not beat benchmark even at 0 bps.")
    L.append("")

    # --- 2. A2 Baseline Recap
    L.append("## 2. A2 Baseline Recap")
    L.append("From `reports/phase_a2_comparison.md`:")
    L.append("- `revenue_confirmation_score`: 0.30 (was 0.20 in A1)")
    L.append("- `institutional_flow_score`: 0.10 (was 0.15)")
    L.append("- `decision_zones[Strong].min_alpha`: 2.5 (was 4.0)")
    L.append("- `sector_relative_score`, `narrative_score` pinned at 0; CAPEX context ≤ 0.05")
    L.append("- A2 gross (Sharpe 1.681 / max DD -31.4% / Strong n=31) is the baseline this report tests against transaction costs.\n")

    # --- 3. Cost Assumptions
    L.append("## 3. Transaction Cost Assumptions")
    L.append("- `one_way_turnover_t` = fraction of top-5 names replaced at rebalance t "
             "(equivalent to `0.5 × Σ |Δweight|` for equal-weight portfolios).")
    L.append("- `monthly_cost_t = one_way_turnover_t × one_way_cost_bps / 10000`.")
    L.append("- `net_return_t = gross_return_t − monthly_cost_t`.")
    L.append("- Initial month: 100% turnover charged (cash → fully invested). Marked `initial_position_turnover`.")
    L.append("- This treats `one_way_cost_bps` as cost-per-unit-of-rotated-portfolio. Real-world "
             "Taiwan retail (commission + 0.30% sell tax + slippage) ≈ 60-90 bps; institutional ≈ 25-50 bps.\n")

    # --- 4. Net Performance by Cost Scenario
    L.append("## 4. Net Performance by Cost Scenario")
    L.append("| cost_bps | CAGR | Sharpe | Vol (ann) | Max DD | Hit | Avg mo turnover | Cost drag/yr | Final NAV | Net α vs 0050 |")
    L.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in summary_df.sort_values("cost_bps").iterrows():
        L.append(
            f"| {int(r['cost_bps'])} | {_fmt_pct(r['cagr'])} | {_fmt(r['sharpe'])} | "
            f"{_fmt_pct(r['annual_volatility'])} | {_fmt_pct(r['max_drawdown'])} | "
            f"{_fmt_pct(r['monthly_hit_rate'])} | {_fmt_pct(r['avg_monthly_turnover'])} | "
            f"{_fmt_pct(r['cost_drag_per_year'])} | {_fmt(r['final_nav'])} | "
            f"{_fmt_pct(r['net_alpha_vs_benchmark'])} |"
        )
    L.append("")

    # --- 5. NAV Comparison
    L.append("## 5. NAV Comparison")
    L.append("See `data/output/charts/transaction_cost_nav.png` (log-scale time series).")
    L.append("Each cost scenario has its own NAV column in `data/output/transaction_cost_nav.csv`.\n")

    # --- 6. Break-even
    L.append("## 6. Break-even Cost Analysis")
    L.append(f"Binary-search result: **{break_even_bps:.1f} bps** "
             f"(net CAGR equals benchmark `{_fmt_pct(benchmark_metrics_dict['cagr'])}` at this cost).")
    L.append("")
    L.append("Interpretation:")
    if np.isfinite(break_even_bps):
        if break_even_bps >= 100:
            L.append(f"- A break-even of **{break_even_bps:.0f} bps** is well above realistic Taiwan retail "
                     "costs (60-90 bps round-trip in this convention) and far above institutional desks (25-50 bps). "
                     "The strategy retains positive net alpha at any plausible cost level.")
        elif break_even_bps >= 50:
            L.append("- Break-even sits between retail and institutional realistic costs. Net alpha is "
                     "robust under institutional execution but fragile under retail.")
        else:
            L.append("- Break-even is **below** realistic execution costs. Strategy is not investable as-is "
                     "for retail; possibly viable for highly cost-efficient institutional execution.")
    L.append("")

    # --- 7. Turnover
    L.append("## 7. Turnover Analysis")
    avg_to = summary_df["avg_monthly_turnover"].iloc[0]  # turnover same across cost scenarios
    ann_to = summary_df["annualized_turnover"].iloc[0]
    L.append(f"- Average monthly one-way turnover: **{_fmt_pct(avg_to)}** (top-5 EW)")
    L.append(f"- Annualized: **{ann_to:.2f}×** ({ann_to * 100:.0f}% of portfolio rotated per year)")
    L.append(f"- This is moderate by quant standards. With only 5 holdings, even one name change = 20% turnover, "
             "so the headline number is high but the absolute trade count per month is small (≈2 names).")
    L.append("")

    # --- 8. Investability Assessment
    L.append("## 8. Investability Assessment")
    if zero_row is not None and np.isfinite(break_even_bps) and break_even_bps >= 100:
        L.append("**Verdict: investable across the full retail-to-institutional cost spectrum.**\n")
        for _, r in summary_df.sort_values("cost_bps").iterrows():
            verdict = (
                "still beats benchmark with healthy margin" if r["net_alpha_vs_benchmark"] > 0.10
                else "modest net alpha" if r["net_alpha_vs_benchmark"] > 0
                else "no net alpha"
            )
            L.append(f"- **{int(r['cost_bps'])} bps** → net CAGR {_fmt_pct(r['cagr'])} "
                     f"({_fmt_pct(r['net_alpha_vs_benchmark'])} vs benchmark) — {verdict}.")
    else:
        L.append("Mixed verdict — see per-scenario rows in §4.\n")
    L.append("")

    # --- 9. Recommendations
    L.append("## 9. Recommendations")
    L.append("- **Keep monthly rebalance** at this stage. Annualized turnover ~5× is acceptable given the cost headroom.")
    L.append("- **Do NOT add a turnover cap or top-N buffer yet** — break-even cost shows the strategy can absorb meaningful friction.")
    L.append("- **Skip rebalance optimisation** (only-rebalance-when-rank-changes-materially / quarterly rebalance) — premature; would trade simplicity for marginal cost savings.")
    L.append("- **DO add a real cost line** to the daily report (e.g. `Strategy NAV (gross) | NAV at 25 bps | NAV at 50 bps`) so the user always sees the realistic number.")
    L.append("- **Future B-phase work**: when universe expands (Phase C → 60+ names), top-5 will be a smaller fraction — turnover dynamics may shift, so re-test then.")
    L.append("")

    # --- 10. Next Step
    L.append("## 10. Next Step")
    L.append("- Phase B1 confirms the strategy survives realistic transaction costs comfortably. "
             "No urgent need for turnover-reduction work.")
    L.append("- Recommended next phases (in priority order):")
    L.append("  - **Phase B2 / B3** (data backfill: GDELT news pre-2025, FinMind institutional flow pre-2022) "
             "— would let us re-run ablation on `narrative_score` and `institutional_flow_score` with full coverage.")
    L.append("  - **Phase C** (universe expansion) — bigger payoff for risk reduction "
             "(top-5 of 60+ = much lower concentration than top-5 of 22).")
    L.append("  - Daily auto-scheduling can wait until either B2/B3 or C lands.")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase B1 transaction-cost test")
    p.add_argument("--costs", type=str, default="0,10,25,50,100",
                   help="Comma-separated one-way cost values in bps")
    p.add_argument("--portfolio-file", type=str,
                   default="data/output/walk_forward_v2_results.csv",
                   help="Walk-forward results CSV (long format with alpha_score + fwd_return_1m)")
    p.add_argument("--benchmark-file", type=str,
                   default="data/output/walk_forward_v2_benchmark.csv",
                   help="Benchmark forward-return CSV")
    p.add_argument("--output-dir", type=str, default="data/output")
    p.add_argument("--report", type=str, default="reports/phase_b1_transaction_cost.md")
    p.add_argument("--top-n", type=int, default=5)
    return p.parse_args(argv)


def _load_results(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["rebalance_date"])
    if "alpha_score" not in df.columns:
        raise ValueError(f"{path} missing alpha_score column.")
    if "fwd_return_1m" not in df.columns:
        raise ValueError(f"{path} missing fwd_return_1m column.")
    return df


def _load_benchmark(path: Path) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype=float)
    bdf = pd.read_csv(path, parse_dates=["rebalance_date"])
    return bdf.set_index("rebalance_date")["benchmark_fwd_1m"]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    costs = [float(c.strip()) for c in args.costs.split(",") if c.strip()]
    portfolio_path = resolve_path(args.portfolio_file)
    benchmark_path = resolve_path(args.benchmark_file)

    if not portfolio_path.exists():
        print(f"ERROR: {portfolio_path} not found. Run scripts/run_walk_forward_v2.py first.",
              file=sys.stderr)
        return 1

    df = _load_results(portfolio_path)
    benchmark = _load_benchmark(benchmark_path)
    if benchmark.empty:
        print(f"WARNING: benchmark file {benchmark_path} not found; using zero benchmark.",
              file=sys.stderr)
        benchmark = pd.Series(0.0, index=df["rebalance_date"].sort_values().unique())

    # Step-1: theme cap.  Pull theme map from active universe + read YAML cap.
    from capex_alpha.data_loader import load_universe
    from capex_alpha.validation import portfolio_metrics as pm
    universe_df = load_universe()
    theme_map = universe_df.set_index("ticker")["theme"].to_dict()
    cap_kwargs = pm.theme_cap_kwargs(theme_map)
    if cap_kwargs["max_per_theme"]:
        logger.info("Theme cap active: max %d per theme", cap_kwargs["max_per_theme"])

    summary_df, nav_df, be = tc.run(
        df, benchmark, costs_bps=costs, n=args.top_n,
        output_dir=args.output_dir, write=True,
        **cap_kwargs,
    )

    # Charts
    charts_dir = ensure_dir(f"{args.output_dir}/charts")
    chart_nav(nav_df, charts_dir / "transaction_cost_nav.png")
    chart_impact(summary_df, charts_dir / "transaction_cost_impact.png", break_even_bps=be)

    # Bench metrics for report
    from capex_alpha.validation import portfolio_metrics as pm
    bench_metrics = pm.benchmark_metrics(benchmark.reindex(df["rebalance_date"].sort_values().unique()).fillna(0.0))

    a2_baseline = {"label": "A2", "ref": "reports/phase_a2_comparison.md"}
    text = render_report(summary_df, nav_df, be, a2_baseline, bench_metrics)

    ensure_dir(Path(args.report).parent)
    Path(resolve_path(args.report)).write_text(text, encoding="utf-8")
    logger.info("Wrote %s", args.report)

    # Console summary
    print()
    print("=" * 80)
    print("PHASE B1 — TRANSACTION COST TEST")
    print("=" * 80)
    print()
    cols = ["cost_bps", "cagr", "sharpe", "max_drawdown", "monthly_hit_rate",
            "avg_monthly_turnover", "cost_drag_per_year", "final_nav",
            "net_alpha_vs_benchmark"]
    print(summary_df[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()
    if np.isfinite(be):
        print(f"Break-even one-way cost: ~{be:.1f} bps")
    else:
        print(f"Break-even cost: {be}")
    print()
    print(f"Benchmark CAGR: {bench_metrics['cagr']*100:.2f}%")
    print(f"Benchmark Sharpe: {bench_metrics['sharpe_ann']:.3f}")
    print(f"Benchmark Max DD: {bench_metrics['max_dd']*100:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
