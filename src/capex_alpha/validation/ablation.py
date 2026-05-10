"""Ablation + simple long-only portfolio simulation off the walk-forward frame.

Given the per-(date, ticker) tier scores we recorded, we can rebuild
``alpha_score`` under any subset of components. No need to re-run scoring.

Variants
--------
- ``full``               : all tiers
- ``no_narrative``       : zero out narrative_score
- ``no_risk_penalty``    : drop the risk_penalty subtraction
- ``no_revenue``         : zero out revenue_confirmation_score
- ``no_sector_relative`` : zero out sector_relative_score
- ``no_flow``            : zero out institutional_flow_score
- ``residual_alpha_only``: keep only residual_alpha_score
- ``narrative_only``     : keep only narrative_score (weak-baseline check)
- ``random``             : random ranks (sanity baseline)

For each variant we report:
- Spearman rank correlation (alpha_score, fwd_return_1m), pooled
- Top-quintile mean fwd return, bottom-quintile mean, spread
- Long-only top-N portfolio: mean fwd, ann Sharpe, max DD
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

from ..utils import ensure_dir, get_logger, resolve_path

logger = get_logger(__name__)


# Components that always sum to alpha_score (with risk_penalty subtracted)
ADDITIVE = [
    "residual_alpha_score",
    "revenue_confirmation_score",
    "sector_relative_score",
    "institutional_flow_score",
    "narrative_score",
    "capex_context_score",
]


# ---------------------------------------------------------------------------

def _rebuild(df: pd.DataFrame, drop: list[str] | None = None,
             keep_only: list[str] | None = None,
             keep_risk_penalty: bool = True) -> pd.Series:
    """Rebuild alpha_score from recorded components."""
    drop = set(drop or [])
    if keep_only is not None:
        keep = set(keep_only)
        cols = [c for c in ADDITIVE if c in keep]
    else:
        cols = [c for c in ADDITIVE if c not in drop]
    score = df[cols].sum(axis=1) if cols else pd.Series(0.0, index=df.index)
    if keep_risk_penalty:
        score = score - df["risk_penalty"]
    return score


def _variant_scores(df: pd.DataFrame, seed: int = 42) -> dict[str, pd.Series]:
    rng = np.random.default_rng(seed)
    return {
        "full": _rebuild(df),
        "no_narrative": _rebuild(df, drop=["narrative_score"]),
        "no_risk_penalty": _rebuild(df, keep_risk_penalty=False),
        "no_revenue": _rebuild(df, drop=["revenue_confirmation_score"]),
        "no_sector_relative": _rebuild(df, drop=["sector_relative_score"]),
        "no_flow": _rebuild(df, drop=["institutional_flow_score"]),
        "no_residual_alpha": _rebuild(df, drop=["residual_alpha_score"]),
        "residual_alpha_only": _rebuild(df, keep_only=["residual_alpha_score"]),
        "narrative_only": _rebuild(df, keep_only=["narrative_score"], keep_risk_penalty=False),
        "random": pd.Series(rng.normal(0, 1, len(df)), index=df.index),
    }


# ---------------------------------------------------------------------------

@dataclass
class VariantStats:
    name: str
    n_obs: int
    spearman_rho: float
    spearman_p: float
    top_quintile_mean: float
    bottom_quintile_mean: float
    spread: float
    portfolio_mean_monthly: float
    portfolio_sharpe_ann: float
    portfolio_max_dd: float
    portfolio_total_return: float


def _spearman(score: pd.Series, fwd: pd.Series) -> tuple[float, float]:
    mask = score.notna() & fwd.notna()
    if mask.sum() < 5:
        return float("nan"), float("nan")
    rho, p = stats.spearmanr(score[mask], fwd[mask])
    return float(rho), float(p)


def _quintile_means(df: pd.DataFrame, score_col: str, fwd_col: str = "fwd_return_1m") -> tuple[float, float]:
    """Per-rebalance-date top vs bottom quintile mean. Then average over dates."""
    rows = []
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[score_col, fwd_col])
        if len(sub) < 5:
            continue
        sub = sub.sort_values(score_col, ascending=False)
        q = max(1, len(sub) // 5)
        top = sub.head(q)[fwd_col].mean()
        bot = sub.tail(q)[fwd_col].mean()
        rows.append({"top": top, "bot": bot})
    if not rows:
        return float("nan"), float("nan")
    out = pd.DataFrame(rows)
    return float(out["top"].mean()), float(out["bot"].mean())


def _topn_portfolio(
    df: pd.DataFrame, score_col: str, fwd_col: str = "fwd_return_1m", n: int = 5
) -> pd.Series:
    """Equal-weight top-N at each rebalance date → monthly portfolio return series."""
    rets = []
    dates = []
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[score_col, fwd_col])
        if len(sub) < n:
            continue
        top = sub.sort_values(score_col, ascending=False).head(n)
        rets.append(float(top[fwd_col].mean()))
        dates.append(t)
    return pd.Series(rets, index=dates, name=score_col)


def _topn_portfolio_zone_filtered(
    df: pd.DataFrame,
    score_col: str,
    exclude_zones: Iterable[str],
    fwd_col: str = "fwd_return_1m",
    n: int = 5,
) -> pd.Series:
    """Same as ``_topn_portfolio`` but drops rows whose ``decision_zone`` is in
    ``exclude_zones`` *before* ranking. Mirrors how the dashboard is actually
    used (a user skips Avoid + Avoid Chasing names rather than buying them).

    Months with fewer than ``n`` eligible rows are skipped.
    """
    excl = set(exclude_zones)
    rets = []
    dates = []
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[score_col, fwd_col])
        if "decision_zone" in sub.columns:
            sub = sub[~sub["decision_zone"].isin(excl)]
        if len(sub) < n:
            continue
        top = sub.sort_values(score_col, ascending=False).head(n)
        rets.append(float(top[fwd_col].mean()))
        dates.append(t)
    return pd.Series(rets, index=dates, name=score_col)


def _sharpe(returns: pd.Series, periods_per_year: int = 12) -> float:
    if returns.empty or returns.std(ddof=0) == 0:
        return float("nan")
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(periods_per_year))


def _max_dd(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    return float((nav / nav.cummax() - 1.0).min())


def _total_return(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    return float((1.0 + returns.fillna(0.0)).prod() - 1.0)


# ---------------------------------------------------------------------------

def run_ablation(
    df: pd.DataFrame,
    top_n: int = 5,
) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Compute stats per variant and return the per-variant portfolio nav series."""
    scores = _variant_scores(df)
    variant_dfs = {name: df.assign(**{f"score_{name}": s}) for name, s in scores.items()}

    stats_rows = []
    portfolios: dict[str, pd.Series] = {}
    for name, vdf in variant_dfs.items():
        score_col = f"score_{name}"
        rho, p = _spearman(vdf[score_col], vdf["fwd_return_1m"])
        top_q, bot_q = _quintile_means(vdf, score_col)
        port = _topn_portfolio(vdf, score_col, n=top_n)
        portfolios[name] = port
        stats_rows.append(
            VariantStats(
                name=name,
                n_obs=int(vdf.dropna(subset=[score_col, "fwd_return_1m"]).shape[0]),
                spearman_rho=rho,
                spearman_p=p,
                top_quintile_mean=top_q,
                bottom_quintile_mean=bot_q,
                spread=top_q - bot_q if (pd.notna(top_q) and pd.notna(bot_q)) else float("nan"),
                portfolio_mean_monthly=float(port.mean()) if not port.empty else float("nan"),
                portfolio_sharpe_ann=_sharpe(port),
                portfolio_max_dd=_max_dd(port),
                portfolio_total_return=_total_return(port),
            )
        )

    stats_df = pd.DataFrame([s.__dict__ for s in stats_rows])
    return stats_df, portfolios


def decision_zone_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Mean / median / hit-rate of fwd_return_1m grouped by decision_zone."""
    sub = df.dropna(subset=["fwd_return_1m"]).copy()
    if sub.empty:
        return pd.DataFrame()
    rows = []
    for zone, g in sub.groupby("decision_zone"):
        rows.append(
            {
                "decision_zone": zone,
                "n_obs": int(len(g)),
                "n_unique_tickers": int(g["ticker"].nunique()),
                "mean_fwd_1m": float(g["fwd_return_1m"].mean()),
                "median_fwd_1m": float(g["fwd_return_1m"].median()),
                "hit_rate": float((g["fwd_return_1m"] > 0).mean()),
                "std_fwd_1m": float(g["fwd_return_1m"].std()),
                "min_fwd_1m": float(g["fwd_return_1m"].min()),
                "max_fwd_1m": float(g["fwd_return_1m"].max()),
            }
        )
    out = pd.DataFrame(rows)
    # Sort by a sensible order
    order = ["Strong Candidate", "Watchlist", "Narrative Watch", "Neutral", "Avoid Chasing", "Avoid"]
    out["__sort"] = out["decision_zone"].map({z: i for i, z in enumerate(order)}).fillna(99)
    out = out.sort_values("__sort").drop(columns="__sort").reset_index(drop=True)
    return out


def alpha_decile_performance(df: pd.DataFrame, n_deciles: int = 5) -> pd.DataFrame:
    """Per-rebalance-date decile bucket of alpha_score → forward return."""
    sub = df.dropna(subset=["alpha_score", "fwd_return_1m"]).copy()
    if sub.empty:
        return pd.DataFrame()
    bucketed = []
    for t, g in sub.groupby("rebalance_date"):
        if len(g) < n_deciles:
            continue
        g = g.sort_values("alpha_score", ascending=False).reset_index(drop=True)
        # rank into n buckets
        g["bucket"] = pd.qcut(
            g["alpha_score"].rank(method="first", ascending=False),
            q=n_deciles,
            labels=[f"Q{i+1}" for i in range(n_deciles)],
        )
        bucketed.append(g)
    if not bucketed:
        return pd.DataFrame()
    pooled = pd.concat(bucketed, ignore_index=True)
    out = (
        pooled.groupby("bucket", observed=True)["fwd_return_1m"]
        .agg(["count", "mean", "median", lambda s: float((s > 0).mean())])
        .rename(columns={"<lambda_0>": "hit_rate"})
        .reset_index()
    )
    return out


def risk_penalty_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compare top-N portfolio with vs without risk penalty."""
    scores_with = _rebuild(df, keep_risk_penalty=True)
    scores_without = _rebuild(df, keep_risk_penalty=False)
    df = df.copy()
    df["score_with_risk"] = scores_with
    df["score_without_risk"] = scores_without

    port_with = _topn_portfolio(df, "score_with_risk")
    port_without = _topn_portfolio(df, "score_without_risk")

    return pd.DataFrame(
        [
            {
                "variant": "with_risk_penalty",
                "mean_monthly": float(port_with.mean()),
                "sharpe_ann": _sharpe(port_with),
                "max_dd": _max_dd(port_with),
                "total_return": _total_return(port_with),
            },
            {
                "variant": "without_risk_penalty",
                "mean_monthly": float(port_without.mean()),
                "sharpe_ann": _sharpe(port_without),
                "max_dd": _max_dd(port_without),
                "total_return": _total_return(port_without),
            },
        ]
    )


def narrative_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compare top-N portfolio with vs without narrative."""
    scores_with = _rebuild(df)
    scores_without = _rebuild(df, drop=["narrative_score"])
    df = df.copy()
    df["score_with_narr"] = scores_with
    df["score_without_narr"] = scores_without

    port_with = _topn_portfolio(df, "score_with_narr")
    port_without = _topn_portfolio(df, "score_without_narr")

    rows = [
        {
            "variant": "with_narrative",
            "mean_monthly": float(port_with.mean()),
            "sharpe_ann": _sharpe(port_with),
            "max_dd": _max_dd(port_with),
            "total_return": _total_return(port_with),
        },
        {
            "variant": "without_narrative",
            "mean_monthly": float(port_without.mean()),
            "sharpe_ann": _sharpe(port_without),
            "max_dd": _max_dd(port_without),
            "total_return": _total_return(port_without),
        },
    ]
    # Spearman of narrative_score itself vs forward return (does narrative independently rank?)
    rho, p = _spearman(df["narrative_score"], df["fwd_return_1m"])
    rows.append(
        {
            "variant": "narrative_score_alone_spearman",
            "mean_monthly": float("nan"),
            "sharpe_ann": float("nan"),
            "max_dd": float("nan"),
            "total_return": float(rho),  # repurpose total_return to carry rho
        }
    )
    out = pd.DataFrame(rows)
    out["__note"] = ""
    out.loc[out["variant"] == "narrative_score_alone_spearman", "__note"] = f"rho={rho:.3f}, p={p:.3f}"
    return out


def gate_attribution(
    df: pd.DataFrame,
    top_n: int = 5,
    exclude_zones: Iterable[str] = ("Avoid", "Avoid Chasing"),
) -> pd.DataFrame:
    """Compare top-N portfolio with vs without the decision-zone filter.

    The unfiltered variant matches what the `full` ablation reports. The
    filtered variant mirrors dashboard usage — pick top-N alpha among names
    not flagged Avoid / Avoid Chasing. The delta is what the gate calibration
    actually buys.
    """
    df = df.copy()
    if "alpha_score" not in df.columns:
        df["alpha_score"] = _rebuild(df)

    port_unfiltered = _topn_portfolio(df, "alpha_score", n=top_n)
    port_filtered = _topn_portfolio_zone_filtered(
        df, "alpha_score", exclude_zones=exclude_zones, n=top_n
    )
    # Apples-to-apples: same months as the filtered variant, but with the
    # unfiltered top-5. Isolates the filter's effect from coverage drag.
    port_aligned = port_unfiltered.loc[
        port_unfiltered.index.intersection(port_filtered.index)
    ]

    excluded_label = " + ".join(exclude_zones)
    rows = [
        {
            "variant": "top5_by_alpha",
            "n_months": int(len(port_unfiltered)),
            "mean_monthly": float(port_unfiltered.mean()) if not port_unfiltered.empty else float("nan"),
            "sharpe_ann": _sharpe(port_unfiltered),
            "max_dd": _max_dd(port_unfiltered),
            "total_return": _total_return(port_unfiltered),
            "__note": "no zone filter",
        },
        {
            "variant": "top5_zone_filtered",
            "n_months": int(len(port_filtered)),
            "mean_monthly": float(port_filtered.mean()) if not port_filtered.empty else float("nan"),
            "sharpe_ann": _sharpe(port_filtered),
            "max_dd": _max_dd(port_filtered),
            "total_return": _total_return(port_filtered),
            "__note": f"excludes: {excluded_label}",
        },
        {
            "variant": "top5_by_alpha_aligned",
            "n_months": int(len(port_aligned)),
            "mean_monthly": float(port_aligned.mean()) if not port_aligned.empty else float("nan"),
            "sharpe_ann": _sharpe(port_aligned),
            "max_dd": _max_dd(port_aligned),
            "total_return": _total_return(port_aligned),
            "__note": "no zone filter, same months as filtered",
        },
    ]
    return pd.DataFrame(rows)


def benchmark_stats(benchmark_returns: pd.Series) -> dict:
    if benchmark_returns.empty:
        return {}
    return {
        "mean_monthly": float(benchmark_returns.mean()),
        "sharpe_ann": _sharpe(benchmark_returns),
        "max_dd": _max_dd(benchmark_returns),
        "total_return": _total_return(benchmark_returns),
    }


# ---------------------------------------------------------------------------

def write_outputs(
    results_df: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
) -> dict[str, pd.DataFrame]:
    """Write all aggregate frames under data/output/."""
    ensure_dir("data/output")
    ablation_stats, portfolios = run_ablation(results_df, top_n=5)
    zone_perf = decision_zone_performance(results_df)
    decile_perf = alpha_decile_performance(results_df, n_deciles=5)
    risk_attr = risk_penalty_attribution(results_df)
    narr_attr = narrative_attribution(results_df)
    gate_attr = gate_attribution(results_df, top_n=5)

    ablation_stats.to_csv(resolve_path("data/output/walk_forward_v2_ablation.csv"), index=False)
    zone_perf.to_csv(resolve_path("data/output/walk_forward_v2_decision_zone.csv"), index=False)
    decile_perf.to_csv(resolve_path("data/output/walk_forward_v2_decile.csv"), index=False)
    risk_attr.to_csv(resolve_path("data/output/walk_forward_v2_risk_attribution.csv"), index=False)
    narr_attr.to_csv(resolve_path("data/output/walk_forward_v2_narrative_attribution.csv"), index=False)
    gate_attr.to_csv(resolve_path("data/output/walk_forward_v2_gate_attribution.csv"), index=False)

    bench_summary = benchmark_stats(benchmark_returns) if benchmark_returns is not None else {}
    if bench_summary:
        pd.DataFrame([bench_summary]).to_csv(
            resolve_path("data/output/walk_forward_v2_benchmark_stats.csv"), index=False
        )

    return {
        "ablation": ablation_stats,
        "zone_perf": zone_perf,
        "decile_perf": decile_perf,
        "risk_attr": risk_attr,
        "narrative_attr": narr_attr,
        "gate_attr": gate_attr,
        "benchmark": pd.DataFrame([bench_summary]) if bench_summary else pd.DataFrame(),
        "portfolios": portfolios,
    }
