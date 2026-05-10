#!/usr/bin/env python
"""Phase C — run the cross-universe backtest comparison + charts + report."""
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
from capex_alpha.validation import universe_validation as uv  # noqa: E402,F401

logger = get_logger("capex_alpha")


# ---------------------------------------------------------------------------
# Charts

def chart_nav(nav: pd.DataFrame, output_path: Path, cost_focus: float = 25.0) -> None:
    """NAV over time per universe at a single cost scenario."""
    fig, ax = plt.subplots(figsize=(11, 6))
    sub = nav[nav["cost_bps"] == cost_focus].copy()
    if sub.empty:
        return
    plotted_bench = False
    for u, g in sub.groupby("universe_name"):
        g = g.sort_values("date")
        if not plotted_bench:
            ax.plot(g["date"], g["benchmark_nav"], label="0050.TW",
                    linestyle="--", color="black", alpha=0.6, linewidth=1.5)
            plotted_bench = True
        ax.plot(g["date"], g["net_nav"], label=u, linewidth=1.5)
    ax.set_yscale("log")
    ax.set_ylabel("Net NAV (log)")
    ax.set_xlabel("Rebalance date")
    ax.set_title(f"Universe expansion — top-5 NAV at {int(cost_focus)} bps cost")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    logger.info("Wrote %s", output_path)


def chart_drawdown(nav: pd.DataFrame, output_path: Path, cost_focus: float = 25.0) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    sub = nav[nav["cost_bps"] == cost_focus].copy()
    if sub.empty:
        return
    for u, g in sub.groupby("universe_name"):
        g = g.sort_values("date").set_index("date")
        nav_series = (1.0 + g["net_return"].fillna(0.0)).cumprod()
        dd = (nav_series / nav_series.cummax() - 1.0) * 100
        ax.plot(dd.index, dd.values, label=u, linewidth=1.5)
    ax.set_ylabel("Drawdown (%)")
    ax.set_xlabel("Rebalance date")
    ax.set_title(f"Universe expansion — drawdown at {int(cost_focus)} bps cost")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    logger.info("Wrote %s", output_path)


def chart_theme_exposure(theme: pd.DataFrame, output_path: Path) -> None:
    """Stacked area plot of theme weights for the largest universe variant."""
    if theme.empty:
        return
    target_name = "expanded_liquid_60" if "expanded_liquid_60" in set(theme["universe_name"]) else theme["universe_name"].iloc[0]
    sub = theme[theme["universe_name"] == target_name].copy()
    if sub.empty:
        return
    pivot = sub.pivot_table(index="date", columns="theme", values="weight", aggfunc="sum").fillna(0.0).sort_index()
    fig, ax = plt.subplots(figsize=(12, 5.5))
    pivot.plot.area(ax=ax, alpha=0.85)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Theme weight in top-5")
    ax.set_xlabel("Rebalance date")
    ax.set_title(f"Theme exposure over time — {target_name}")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=9, frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    logger.info("Wrote %s", output_path)


# ---------------------------------------------------------------------------
# Report

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


def render_report(panel: dict) -> str:
    summary = panel["summary"]
    labels  = panel["labels"]
    theme   = panel["theme"]

    L: list[str] = []
    L.append("# Phase C — Universe Expansion (PoC)")

    if not summary.empty:
        n_dates = panel["nav"]["date"].nunique() if not panel["nav"].empty else "—"
        L.append(f"_Backtest: 2020-06-30 → 2026-04-30, {n_dates} rebalances. Top-5 EW monthly._\n")

    # 1. Executive summary
    L.append("## 1. Executive Summary")
    if summary.empty:
        L.append("_No results._\n")
    else:
        baseline = summary[(summary["universe_name"] == "original") & (summary["cost_bps"] == 25)]
        l40      = summary[(summary["universe_name"] == "expanded_liquid_40") & (summary["cost_bps"] == 25)]
        l60      = summary[(summary["universe_name"] == "expanded_liquid_60") & (summary["cost_bps"] == 25)]

        if not baseline.empty and not l60.empty:
            b = baseline.iloc[0]; l = l60.iloc[0]
            L.append(f"- **At 25 bps cost, original universe ({int(b['num_stocks'])} names)**: "
                     f"CAGR `{_pct(b['cagr'])}`, Sharpe `{_fmt(b['sharpe'])}`, max DD `{_pct(b['max_drawdown'])}`.")
            L.append(f"- **At 25 bps cost, expanded_liquid_60 ({int(l['num_stocks'])} names)**: "
                     f"CAGR `{_pct(l['cagr'])}`, Sharpe `{_fmt(l['sharpe'])}`, max DD `{_pct(l['max_drawdown'])}`.")
            L.append(f"- ΔSharpe: `{_fmt(l['sharpe'] - b['sharpe'])}`, "
                     f"ΔMax DD: `{_pct(l['max_drawdown'] - b['max_drawdown'])}`, "
                     f"ΔCAGR: `{_pct(l['cagr'] - b['cagr'])}`.")
        if not l40.empty:
            l = l40.iloc[0]
            L.append(f"- **expanded_liquid_40**: CAGR `{_pct(l['cagr'])}`, Sharpe `{_fmt(l['sharpe'])}`, "
                     f"max DD `{_pct(l['max_drawdown'])}`, "
                     f"unique holdings `{int(l['unique_holdings_count'])}`.")
    L.append("")

    # 2. Why
    L.append("## 2. Why Universe Expansion")
    L.append("- A2 baseline runs on 22 ranked names.  Top-5 = 23% concentration → max DD -31% vs benchmark -29%.")
    L.append("- B1 confirmed transaction cost is not the bottleneck (break-even ~588 bps).  "
             "The remaining identified risk is concentration, addressable only by widening the universe.")
    L.append("- Phase C tests whether widening to 40/60 names (a) preserves Sharpe / alpha, "
             "(b) reduces max DD, (c) reduces single-theme exposure.\n")

    # 3. Candidate universe
    L.append("## 3. Candidate Universe")
    L.append("- 78 candidates across 13 themes (6 original + 7 new: optical_communication, thermal, "
             "memory_hbm, passive_components, pcb_substrate, power_grid_energy, leo_satellite, ai_server_assembly).")
    L.append("- Source: `data/manual/beneficiary_universe_phase_c_candidates.csv`. Manual research-grade list, "
             "no claim to completeness.\n")

    # 4. Liquidity filter
    L.append("## 4. Liquidity Filter")
    L.append("- ADV proxy = mean(close × volume) over last 60 trading days.")
    L.append("- Tier A (ADV ≥ NTD 100M): 72 names.  Tier B (30M ≤ ADV < 100M): 5.  Tier C: 1.  Tier X (no data): 0.")
    L.append("- Filter applied: `data_available=True` AND `missing_ratio < 10%` AND `ADV ≥ 30M TWD`.  "
             "Issuer 2330.TW always kept.\n")

    # 5. Backtest setup
    L.append("## 5. Backtest Setup")
    L.append("- A2 baseline weights (`rev=0.30`, `flw=0.10`, `min_alpha=2.5`, others unchanged).")
    L.append("- For each universe variant: rebuild AI factor index, recompute residual alpha, "
             "rerun PIT-correct walk-forward, apply B1 transaction-cost machinery.")
    L.append("- **Important**: FinMind data (revenue / inst flow / valuation) is not backfilled for new tickers "
             "(deferred to Phase B2/B3).  Those factors are 0 for new names; ranking falls back to `residual_alpha` "
             "(dominant signal per A1/A2 ablation).\n")

    # 6. Performance comparison
    L.append("## 6. Performance Comparison")
    if not summary.empty:
        L.append("| Universe | N | cost | CAGR | Sharpe | max DD | Hit | Turnover | "
                 "Final NAV | Net α | Top-5 conc. | Max θ exp | Uniq | Strong (n / hit) | Watch (n / hit) |")
        L.append("|:--|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in summary.sort_values(["universe_name", "cost_bps"]).iterrows():
            L.append(
                f"| {r['universe_name']} | {int(r['num_stocks'])} | {int(r['cost_bps'])} | "
                f"{_pct(r['cagr'])} | {_fmt(r['sharpe'])} | {_pct(r['max_drawdown'])} | "
                f"{_pct(r['monthly_hit_rate'])} | {_pct(r['avg_monthly_turnover'])} | "
                f"{_fmt(r['final_nav'])} | {_pct(r['net_alpha_vs_benchmark'])} | "
                f"{_pct(r['top5_concentration'])} | {_pct(r['max_theme_exposure'])} | "
                f"{int(r['unique_holdings_count'])} | "
                f"{int(r['strong_count'])} / {_pct(r['strong_hit_rate'])} | "
                f"{int(r['watchlist_count'])} / {_pct(r['watchlist_hit_rate'])} |"
            )
    L.append("")

    # 7. Cost impact
    L.append("## 7. Transaction Cost Impact")
    L.append("Each universe is shown at 25 / 50 / 100 bps in §6.  Larger universes have similar turnover "
             "(top-5 EW rebalance dynamics), so cost drag scales similarly across variants.\n")

    # 8. Concentration
    L.append("## 8. Concentration Analysis")
    L.append("- Original: top-5 / 22 = 22.7% of universe.  Expanded_liquid_60: top-5 / 60 = 8.3%.")
    L.append("- Lower top-5 / universe ratio is what we wanted; whether it actually shows up in "
             "max-DD reduction depends on whether new tickers diversify away from existing AI-theme beta. See §6.\n")

    # 9. Theme exposure
    L.append("## 9. Theme Exposure Analysis")
    if not theme.empty:
        # Per-universe max single-theme weight
        L.append("| Universe | Max single-theme weight | Themes appearing in top-5 |")
        L.append("|:--|---:|---:|")
        for u, g in theme.groupby("universe_name"):
            max_w = g["weight"].max()
            n_themes = g["theme"].nunique()
            L.append(f"| {u} | {_pct(max_w)} | {n_themes} |")
        L.append("")
        L.append("If `max_theme_exposure` exceeds 60% on a sustained basis, a theme cap (e.g. single theme ≤ 40%) "
                 "would be the right next-step risk control — see §12.\n")

    # 10. Label predictive power
    L.append("## 10. Label Predictive Power")
    if not labels.empty:
        L.append("| Universe | Zone | n_obs | n_uniq | hit_rate | mean fwd_1m | avg α | avg conf |")
        L.append("|:--|:--|---:|---:|---:|---:|---:|---:|")
        for _, r in labels.sort_values(["universe_name", "decision_zone"]).iterrows():
            L.append(
                f"| {r['universe_name']} | {r['decision_zone']} | {int(r['n_obs'])} | "
                f"{int(r['n_unique_tickers'])} | {_pct(r['hit_rate'])} | "
                f"{_pct(r['mean_forward_1m_return'])} | {_fmt(r['avg_alpha_score'])} | "
                f"{_fmt(r['avg_confidence_score'])} |"
            )
    L.append("")

    # 11. Diagnosis
    L.append("## 11. Failure / Success Diagnosis")
    if not summary.empty:
        baseline = summary[(summary["universe_name"] == "original") & (summary["cost_bps"] == 25)]
        l60      = summary[(summary["universe_name"] == "expanded_liquid_60") & (summary["cost_bps"] == 25)]
        if not baseline.empty and not l60.empty:
            b, l = baseline.iloc[0], l60.iloc[0]
            sharpe_drop = b["sharpe"] - l["sharpe"]
            dd_change = l["max_drawdown"] - b["max_drawdown"]
            success = (sharpe_drop <= 0.15) and (dd_change >= 0)
            if success:
                L.append("**Verdict: Phase C SUCCESS.** Sharpe drop ≤ 0.15 AND max DD improved or unchanged.")
            else:
                reasons = []
                if sharpe_drop > 0.15:
                    reasons.append(f"Sharpe degraded by `{_fmt(sharpe_drop)}` (> 0.15 tolerance)")
                if dd_change < 0:
                    reasons.append(f"Max DD widened by `{_pct(-dd_change)}`")
                L.append(f"**Verdict: Phase C MIXED / FAIL.** Reasons: {'; '.join(reasons)}.")
            L.append("")
            L.append("Possible diagnoses:")
            L.append("- New tickers ranked highly but proved over-fit to AI bull tail end → check `expanded_liquid_60` "
                     "label hit rates in §10.")
            L.append("- FinMind-dependent factors zeroed for new names → revenue confirmation gate is weakened "
                     "for new theme tickers.  Mitigation = Phase B2/B3 backfill before re-evaluating.")
            L.append("- AI factor index now includes new themes → residual alpha for original tickers shifts; "
                     "compare original-universe results in this run vs A2 baseline to gauge the index drift.")
    L.append("")

    # 12. Recommendation
    L.append("## 12. Recommendation")
    if not summary.empty:
        baseline = summary[(summary["universe_name"] == "original") & (summary["cost_bps"] == 25)]
        l60      = summary[(summary["universe_name"] == "expanded_liquid_60") & (summary["cost_bps"] == 25)]
        l40      = summary[(summary["universe_name"] == "expanded_liquid_40") & (summary["cost_bps"] == 25)]
        if not baseline.empty and not l60.empty:
            b, l = baseline.iloc[0], l60.iloc[0]
            adopt = (b["sharpe"] - l["sharpe"]) <= 0.15 and l["max_drawdown"] > b["max_drawdown"]
            if adopt:
                L.append("- **Adopt expanded_liquid_60 as the new active baseline.** It satisfies the PoC success criteria.")
            elif not l40.empty:
                l = l40.iloc[0]
                if (b["sharpe"] - l["sharpe"]) <= 0.15:
                    L.append("- **Adopt expanded_liquid_40 instead** — better risk/reward trade-off than _60 for this data.")
                else:
                    L.append("- **Do NOT adopt expansion as-is.** Both _40 and _60 fail the success criteria. "
                             "Likely cause: lack of FinMind backfill for new tickers (Phase B2/B3 prerequisite).")
            else:
                L.append("- **Hold off on adoption** until expanded_liquid_40 result is in / FinMind backfill done.")
    L.append("")
    L.append("Theme cap recommendation: if max single-theme weight in §9 exceeds 60% sustained, "
             "introduce a `single_theme_cap = 0.40` in fusion ranking before adopting expanded universe live.\n")

    # 13. Next step
    L.append("## 13. Next Step")
    L.append("Conditional on §12 verdict:")
    L.append("- If expansion adopted → run Phase B2/B3 (FinMind backfill) so new-ticker scoring uses full feature set; "
             "then redo this PoC and decide on theme cap.")
    L.append("- If expansion not adopted → Phase B2/B3 first to give expansion a fair test.")
    L.append("- **Daily auto-scheduling: still NOT recommended** until expansion + B2/B3 reach a stable verdict.")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase C universe-expansion backtest")
    p.add_argument("--candidate-file", type=str,
                   default="data/manual/beneficiary_universe_phase_c_candidates.csv")
    p.add_argument("--output-universe", type=str,
                   default="data/manual/beneficiary_universe_expanded.csv")
    p.add_argument("--min-adv", type=float, default=30_000_000)
    p.add_argument("--costs", type=str, default="25,50,100")
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--start", type=str, default="2020-06-30")
    p.add_argument("--end", type=str, default=None)
    p.add_argument("--debug", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    costs = [float(c.strip()) for c in args.costs.split(",") if c.strip()]

    # Universe specs: name → CSV path (None = default config)
    specs = [
        ("original", None),
        ("expanded_liquid_40",   "data/manual/beneficiary_universe_expanded_liquid_40.csv"),
        ("expanded_liquid_60",   "data/manual/beneficiary_universe_expanded_liquid_60.csv"),
        ("expanded_all_available","data/manual/beneficiary_universe_expanded_all_available.csv"),
    ]
    # Drop any spec whose CSV is missing
    valid_specs = []
    for name, path in specs:
        if path is None or resolve_path(path).exists():
            valid_specs.append((name, path))
        else:
            logger.warning("Skipping %s: %s missing.  Run scripts/build_expanded_universe.py first.",
                           name, path)

    panel = uv.run_universe_panel(
        valid_specs,
        start=args.start, end=args.end,
        cost_scenarios_bps=costs,
        top_n=args.top_n,
    )
    uv.write_outputs(panel)

    # Charts
    charts_dir = ensure_dir("data/output/charts")
    chart_nav(panel["nav"], charts_dir / "universe_expansion_nav.png", cost_focus=costs[0])
    chart_drawdown(panel["nav"], charts_dir / "universe_expansion_drawdown.png", cost_focus=costs[0])
    chart_theme_exposure(panel["theme"], charts_dir / "universe_expansion_theme_exposure.png")

    # Report
    text = render_report(panel)
    ensure_dir("reports")
    Path(resolve_path("reports/phase_c_universe_expansion.md")).write_text(text, encoding="utf-8")
    logger.info("Wrote reports/phase_c_universe_expansion.md")

    # Console summary
    print()
    print("=" * 80)
    print("PHASE C — UNIVERSE EXPANSION RESULTS")
    print("=" * 80)
    if not panel["summary"].empty:
        cols = ["universe_name", "num_stocks", "cost_bps", "cagr", "sharpe",
                "max_drawdown", "monthly_hit_rate", "avg_monthly_turnover",
                "top5_concentration", "max_theme_exposure", "unique_holdings_count",
                "strong_count", "strong_hit_rate"]
        print(panel["summary"][cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
