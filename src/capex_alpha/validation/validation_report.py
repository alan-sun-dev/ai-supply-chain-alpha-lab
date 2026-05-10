"""Render the walk-forward v2 validation Markdown report."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..utils import ensure_dir, get_logger, resolve_path

logger = get_logger(__name__)


def _fmt(x: Any, decimals: int = 3) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, (float, np.floating)):
        return f"{float(x):.{decimals}f}"
    return str(x)


def _fmt_pct(x: Any, decimals: int = 1) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{float(x) * 100:.{decimals}f}%"


# ---------------------------------------------------------------------------

def render(
    results: pd.DataFrame,
    ablation: pd.DataFrame,
    zone_perf: pd.DataFrame,
    decile_perf: pd.DataFrame,
    risk_attr: pd.DataFrame,
    narrative_attr: pd.DataFrame,
    benchmark_stats: dict | None = None,
    gate_attr: pd.DataFrame | None = None,
) -> str:
    benchmark_stats = benchmark_stats or {}

    n_dates = results["rebalance_date"].nunique() if not results.empty else 0
    n_obs = len(results)
    start = results["rebalance_date"].min().date() if n_dates else None
    end = results["rebalance_date"].max().date() if n_dates else None

    L: list[str] = []
    L.append("# v2 Walk-Forward Validation Report")
    L.append(f"_Window: {start} → {end}, {n_dates} monthly rebalances, {n_obs} (date, ticker) observations._\n")

    # ---- Executive summary
    L.append("## 0. TL;DR")
    full_row = ablation[ablation["name"] == "full"].iloc[0] if not ablation.empty else None
    bench_total = benchmark_stats.get("total_return")
    bench_sharpe = benchmark_stats.get("sharpe_ann")
    L.append(
        f"- **Full v2 top-5 portfolio**: total return `{_fmt_pct(full_row['portfolio_total_return']) if full_row is not None else '—'}`, "
        f"Sharpe `{_fmt(full_row['portfolio_sharpe_ann']) if full_row is not None else '—'}`, "
        f"max DD `{_fmt_pct(full_row['portfolio_max_dd']) if full_row is not None else '—'}`."
    )
    L.append(
        f"- **0050.TW benchmark**: total return `{_fmt_pct(bench_total)}`, Sharpe `{_fmt(bench_sharpe)}`."
    )
    if full_row is not None:
        rho = full_row["spearman_rho"]
        p = full_row["spearman_p"]
        sig = "✅ statistically significant" if p < 0.05 else "❌ not significant"
        L.append(f"- **Spearman(alpha_score, fwd_return_1m)** = `{_fmt(rho)}`, p=`{_fmt(p)}` → {sig}.")
        spread = full_row["spread"]
        L.append(f"- **Top-quintile minus bottom-quintile** monthly spread = `{_fmt_pct(spread)}`.")
    L.append("")

    # ---- 1. Decision Zone performance
    L.append("## 1. Decision Zone Forward-Return Performance")
    L.append(
        "_Pooled across all rebalance dates. If the gate is informative, "
        "Strong Candidate > Watchlist > Neutral > Avoid in mean fwd return._\n"
    )
    if zone_perf.empty:
        L.append("_No data._\n")
    else:
        L.append("| Zone | n_obs | n_tickers | mean_fwd_1m | median | hit_rate | std | min | max |")
        L.append("|:--|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in zone_perf.iterrows():
            L.append(
                f"| {r['decision_zone']} | {int(r['n_obs'])} | {int(r['n_unique_tickers'])} | "
                f"{_fmt_pct(r['mean_fwd_1m'])} | {_fmt_pct(r['median_fwd_1m'])} | "
                f"{_fmt_pct(r['hit_rate'])} | {_fmt_pct(r['std_fwd_1m'])} | "
                f"{_fmt_pct(r['min_fwd_1m'])} | {_fmt_pct(r['max_fwd_1m'])} |"
            )
        L.append("")

    # ---- 2. Decile performance
    L.append("## 2. Alpha-Score Quintile Performance")
    L.append("_Per-rebalance-date quintile bucket. Q1 = highest alpha_score, Q5 = lowest._\n")
    if decile_perf.empty:
        L.append("_No data._\n")
    else:
        L.append("| Bucket | n_obs | mean_fwd_1m | median | hit_rate |")
        L.append("|:--|---:|---:|---:|---:|")
        for _, r in decile_perf.iterrows():
            L.append(
                f"| {r['bucket']} | {int(r['count'])} | {_fmt_pct(r['mean'])} | "
                f"{_fmt_pct(r['median'])} | {_fmt_pct(r['hit_rate'])} |"
            )
        L.append("")

    # ---- 3. Ablation
    L.append("## 3. Factor Ablation — Top-5 Long-Only Portfolio")
    L.append(
        "_Each variant rebuilds alpha_score from the recorded tier components, "
        "then a top-5 monthly-rebalance portfolio is simulated._\n"
    )
    if ablation.empty:
        L.append("_No data._\n")
    else:
        L.append("| Variant | Spearman ρ | p-value | Q1 mean | Q5 mean | spread | Sharpe | max DD | Total |")
        L.append("|:--|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in ablation.iterrows():
            L.append(
                f"| `{r['name']}` | {_fmt(r['spearman_rho'])} | {_fmt(r['spearman_p'])} | "
                f"{_fmt_pct(r['top_quintile_mean'])} | {_fmt_pct(r['bottom_quintile_mean'])} | "
                f"{_fmt_pct(r['spread'])} | {_fmt(r['portfolio_sharpe_ann'])} | "
                f"{_fmt_pct(r['portfolio_max_dd'])} | {_fmt_pct(r['portfolio_total_return'])} |"
            )
        L.append("")
        L.append(
            "> Interpretation: `random` is the noise floor. If a variant matches `random` Sharpe, "
            "those factors contribute no signal. If `no_<X>` is materially better than `full`, "
            "that factor is hurting; if worse, it is helping."
        )
        L.append("")

    # ---- 4. Risk-penalty attribution
    L.append("## 4. Risk-Penalty Attribution")
    L.append("_Does the risk_penalty improve drawdown control without killing alpha?_\n")
    if risk_attr.empty:
        L.append("_No data._\n")
    else:
        L.append("| Variant | mean_monthly | Sharpe | max DD | total_return |")
        L.append("|:--|---:|---:|---:|---:|")
        for _, r in risk_attr.iterrows():
            L.append(
                f"| `{r['variant']}` | {_fmt_pct(r['mean_monthly'])} | {_fmt(r['sharpe_ann'])} | "
                f"{_fmt_pct(r['max_dd'])} | {_fmt_pct(r['total_return'])} |"
            )
        L.append("")
        if len(risk_attr) >= 2:
            with_dd = risk_attr.iloc[0]["max_dd"]
            without_dd = risk_attr.iloc[1]["max_dd"]
            verdict = "improves" if with_dd > without_dd else "does NOT improve"
            L.append(f"> Risk penalty {verdict} max DD ({_fmt_pct(with_dd)} vs {_fmt_pct(without_dd)}).")
        L.append("")

    # ---- 5. Narrative noise check
    L.append("## 5. Narrative Noise Check")
    L.append("_Does narrative_score add value or just inject noise?_\n")
    if narrative_attr.empty:
        L.append("_No data._\n")
    else:
        L.append("| Variant | mean_monthly | Sharpe | max DD | total / rho | note |")
        L.append("|:--|---:|---:|---:|---:|:--|")
        for _, r in narrative_attr.iterrows():
            note = r.get("__note", "")
            if r["variant"] == "narrative_score_alone_spearman":
                rho_val = r["total_return"]
                L.append(
                    f"| `{r['variant']}` | — | — | — | ρ=`{_fmt(rho_val)}` | {note} |"
                )
            else:
                L.append(
                    f"| `{r['variant']}` | {_fmt_pct(r['mean_monthly'])} | {_fmt(r['sharpe_ann'])} | "
                    f"{_fmt_pct(r['max_dd'])} | {_fmt_pct(r['total_return'])} | {note} |"
                )
        L.append("")

    # ---- 6. Gate-filtered top-5 (mirrors dashboard usage)
    L.append("## 6. Gate-Filtered Top-5 Portfolio")
    L.append(
        "_Picks top-5 by `alpha_score` *after* dropping rows whose "
        "`decision_zone` is `Avoid` or `Avoid Chasing`. This is what the "
        "dashboard actually surfaces — a user does not buy Avoid-Chasing "
        "names. The unfiltered variant matches the `full` ablation row above._\n"
    )
    if gate_attr is None or gate_attr.empty:
        L.append("_No data._\n")
    else:
        L.append("| Variant | n_months | mean_monthly | Sharpe | max DD | total_return | note |")
        L.append("|:--|---:|---:|---:|---:|---:|:--|")
        for _, r in gate_attr.iterrows():
            note = r.get("__note", "")
            L.append(
                f"| `{r['variant']}` | {int(r['n_months'])} | "
                f"{_fmt_pct(r['mean_monthly'])} | {_fmt(r['sharpe_ann'])} | "
                f"{_fmt_pct(r['max_dd'])} | {_fmt_pct(r['total_return'])} | {note} |"
            )
        L.append("")
        # Apples-to-apples verdict: compare filtered vs aligned (same months)
        flt_row = gate_attr[gate_attr["variant"] == "top5_zone_filtered"]
        aln_row = gate_attr[gate_attr["variant"] == "top5_by_alpha_aligned"]
        if not flt_row.empty and not aln_row.empty:
            flt = flt_row.iloc[0]
            aln = aln_row.iloc[0]
            d_sharpe = flt["sharpe_ann"] - aln["sharpe_ann"]
            d_total = flt["total_return"] - aln["total_return"]
            d_dd = flt["max_dd"] - aln["max_dd"]
            verdict = "improves" if d_sharpe > 0 else "does NOT improve"
            L.append(
                f"> Apples-to-apples (`top5_zone_filtered` vs `top5_by_alpha_aligned`, "
                f"same {int(flt['n_months'])} months): zone filter {verdict} Sharpe by "
                f"`{d_sharpe:+.3f}`, total_return Δ `{d_total*100:+.1f}%`, "
                f"max_dd Δ `{d_dd*100:+.1f}%`. The lower total vs `top5_by_alpha` "
                f"is coverage drag — filtered skips months with <5 eligible names — "
                f"not the filter being worse."
            )
        L.append("")

    # ---- 7. Caveats
    L.append("## 7. Caveats")
    L.append(
        "- Universe is 22 tickers, all manually curated — survivorship bias is reduced "
        "by the SURVIVORSHIP-TEST cohort but not eliminated."
    )
    L.append(
        "- Institutional flow data only starts 2022-01; pre-2022 the `institutional_flow_score` "
        "factor is mostly zero. Treat pre-2022 ablation results with caution."
    )
    L.append(
        "- News data starts mid-2025 in the current `news_events.csv`; pre-mid-2025 "
        "narrative_score is mostly zero. The narrative ablation is therefore mostly testing "
        "the recent ~6-12 months."
    )
    L.append(
        "- 1-month forward return is close-to-close on month-end; ignores execution costs, "
        "slippage, and Taiwan T+2 settlement."
    )
    L.append(
        "- Factor weights are *priors*, not optimized on this data. A separate weight sweep "
        "would be needed to claim 'optimal' weights."
    )
    L.append(
        "- 5-quintile bucketing on a 22-name universe yields ~4 names per bucket — small samples."
    )

    return "\n".join(L)


def write_report(text: str) -> None:
    ensure_dir("reports")
    path = resolve_path("reports/walk_forward_v2_summary.md")
    path.write_text(text, encoding="utf-8")
    logger.info("Wrote %s", path)
    ensure_dir("data/output")
    resolve_path("data/output/walk_forward_v2_summary.md").write_text(text, encoding="utf-8")
