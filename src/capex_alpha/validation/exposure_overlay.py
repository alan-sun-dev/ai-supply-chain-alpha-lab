"""Phase D1 — drawdown-control exposure overlay.

Wires the existing ``regime_filter`` recommendation (which until now was
informational only) into actual gross-exposure scaling on the backtest.

Logic per rebalance date t:
1. Compute strategy NAV through end-of-month t-1 (so far). Compute strategy DD
   = NAV(t-1) / max(NAV[0..t-1]) − 1.
2. Slice market price + AI aggregate NAV up to date t (PIT-correct).
3. Call ``regime_filter.classify`` to get the recommended gross_exposure.
4. **Override**: if `strategy_dd < -0.15`, force exposure = 0.30 (per user
   D1 spec, even if regime cascade would have allowed more).
5. Scale that month's portfolio return: `scaled_t = exposure × portfolio_t`
   (cash assumed 0% return — conservative).

Scope (per user mandate):
- No model / weight / scoring / gate changes
- Top-5 EW selection unchanged (uses theme cap from active YAML)
- Pure backtest layer

Reports:
- CAGR, Sharpe, Calmar, Max DD, monthly hit rate
- Months in DD, longest recovery, drawdown-period mean return
- Cash exposure timeline
- Turnover (base name rotation + exposure-change rotation)
- Net @ 25 / 50 bps cost
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data_loader import get_close_panel, load_universe
from ..quant import ai_factor_index as afi
from ..quant import regime_filter as rf
from ..utils import ensure_dir, get_logger, load_yaml, resolve_path
from . import portfolio_metrics as pm

logger = get_logger(__name__)


# ---------------------------------------------------------------------------

DD_OVERRIDE_THRESHOLD = -0.15
DD_OVERRIDE_EXPOSURE = 0.30


def _strategy_dd_so_far(nav: float, peak: float) -> float:
    if peak <= 0:
        return 0.0
    return float(nav / peak - 1.0)


def compute_exposure_path(
    portfolio_returns: pd.Series,
    market_price: pd.Series,
    ai_nav: pd.Series,
    regime_cfg: dict | None = None,
    dd_override_threshold: float = DD_OVERRIDE_THRESHOLD,
    dd_override_exposure: float = DD_OVERRIDE_EXPOSURE,
) -> pd.DataFrame:
    """Walk the portfolio month-by-month, applying exposure scaling.

    Returns a DataFrame indexed by rebalance date with columns:
    `regime_label`, `regime_exposure`, `dd_override_applied`,
    `applied_exposure`, `cash_weight`, `raw_return`, `scaled_return`,
    `nav_baseline`, `nav_scaled`, `peak_baseline`, `peak_scaled`,
    `strategy_dd_so_far_baseline`, `strategy_dd_so_far_scaled`.
    """
    rows: list[dict] = []
    nav_b = 1.0
    nav_s = 1.0
    peak_b = 1.0
    peak_s = 1.0

    for date in portfolio_returns.index:
        # PIT-correct slices
        mp_pit = market_price.loc[market_price.index <= date]
        ai_pit = ai_nav.loc[ai_nav.index <= date]
        if mp_pit.empty or ai_pit.empty:
            applied = 1.0
            label = "n/a"
            regime_exposure = 1.0
        else:
            # Strategy DD measured on the SCALED nav (the live one we're trading)
            strategy_dd = _strategy_dd_so_far(nav_s, peak_s)
            classification = rf.classify(
                market_price=mp_pit,
                ai_nav=ai_pit,
                revenue_confirmation=True,
                strategy_drawdown=strategy_dd,
            )
            label = classification.notes.split(";")[0].replace("regime=", "").strip()
            regime_exposure = float(classification.recommended_gross_exposure)
            applied = regime_exposure
            # Hard override: if strategy DD breached threshold, force defensive
            if strategy_dd <= dd_override_threshold:
                applied = min(applied, dd_override_exposure)

        raw = float(portfolio_returns.loc[date])
        scaled = float(applied * raw)

        # Update NAVs (record AFTER applying this month's return)
        nav_b *= (1.0 + raw)
        nav_s *= (1.0 + scaled)
        peak_b = max(peak_b, nav_b)
        peak_s = max(peak_s, nav_s)

        rows.append({
            "date":              date,
            "regime_label":      label,
            "regime_exposure":   regime_exposure,
            "dd_override_applied": applied != regime_exposure,
            "applied_exposure":  applied,
            "cash_weight":       1.0 - applied,
            "raw_return":        raw,
            "scaled_return":     scaled,
            "nav_baseline":      nav_b,
            "nav_scaled":        nav_s,
            "peak_baseline":     peak_b,
            "peak_scaled":       peak_s,
            "strategy_dd_baseline": _strategy_dd_so_far(nav_b, peak_b),
            "strategy_dd_scaled":   _strategy_dd_so_far(nav_s, peak_s),
        })

    return pd.DataFrame(rows).set_index("date")


# ---------------------------------------------------------------------------
# Drawdown episode tracking

@dataclass
class DDEpisode:
    start: pd.Timestamp
    end: pd.Timestamp | None    # None if still ongoing
    duration_months: int        # peak → recovery
    max_dd: float


def drawdown_episodes(returns: pd.Series, dd_threshold: float = -0.001) -> list[DDEpisode]:
    """Identify peak-to-recovery DD episodes.

    An episode starts the first month NAV < cummax (peak), and ends the
    first month NAV ≥ that peak again. ``dd_threshold`` is the minimum
    fractional DD (negative) required to count as an episode — defaults
    to any DD greater than 0.1%.
    """
    if returns.empty:
        return []
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    episodes: list[DDEpisode] = []

    in_episode = False
    start: pd.Timestamp | None = None
    start_peak: float | None = None
    max_dd = 0.0

    for i, (date, val) in enumerate(nav.items()):
        running_peak = float(nav.iloc[:i + 1].max())
        dd = val / running_peak - 1.0

        if not in_episode:
            if dd <= dd_threshold:
                in_episode = True
                start = date
                start_peak = running_peak
                max_dd = dd
        else:
            max_dd = min(max_dd, dd)
            if val >= start_peak:
                # Recovered. Duration = months from start to recovery date.
                start_idx = nav.index.get_loc(start)
                end_idx = i
                episodes.append(DDEpisode(
                    start=pd.Timestamp(start),
                    end=pd.Timestamp(date),
                    duration_months=int(end_idx - start_idx),
                    max_dd=float(max_dd),
                ))
                in_episode = False
                start, start_peak, max_dd = None, None, 0.0

    if in_episode:
        episodes.append(DDEpisode(
            start=pd.Timestamp(start),
            end=None,
            duration_months=int(nav.index.get_loc(nav.index[-1]) - nav.index.get_loc(start)),
            max_dd=float(max_dd),
        ))
    return episodes


# ---------------------------------------------------------------------------
# Metrics computation

def _calmar(cagr: float, max_dd: float) -> float:
    if abs(max_dd) < 1e-9:
        return float("nan")
    return float(cagr / abs(max_dd))


def _months_in_drawdown(returns: pd.Series) -> int:
    if returns.empty:
        return 0
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    return int((nav < nav.cummax()).sum())


def _dd_period_mean_return(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    in_dd = nav < nav.cummax()
    sub = returns[in_dd]
    return float(sub.mean()) if not sub.empty else float("nan")


def metrics_table(returns: pd.Series, label: str) -> dict:
    if returns.empty:
        return {"label": label}
    cagr = pm.cagr(returns)
    sharpe = pm.sharpe(returns)
    max_dd = pm.max_drawdown(returns)
    calmar = _calmar(cagr, max_dd)
    eps = drawdown_episodes(returns)
    longest_recovery = max((e.duration_months for e in eps if e.end is not None),
                           default=0)
    ongoing = [e for e in eps if e.end is None]
    return {
        "label":                  label,
        "n_months":               int(len(returns)),
        "cagr":                   cagr,
        "sharpe_ann":             sharpe,
        "max_dd":                 max_dd,
        "calmar":                 calmar,
        "monthly_hit_rate":       pm.monthly_hit_rate(returns),
        "mean_monthly":           float(returns.mean()),
        "worst_month":            float(returns.min()),
        "best_month":             float(returns.max()),
        "months_in_drawdown":     _months_in_drawdown(returns),
        "dd_period_mean_return":  _dd_period_mean_return(returns),
        "n_dd_episodes":          int(len(eps)),
        "longest_recovery_mo":    int(longest_recovery),
        "ongoing_dd":             "yes" if ongoing else "no",
        "total_return":           float((1.0 + returns.fillna(0.0)).prod() - 1.0),
    }


# ---------------------------------------------------------------------------
# Turnover including exposure changes

def turnover_split(
    holdings: dict[pd.Timestamp, list[str]],
    exposure_path: pd.Series,
) -> dict:
    """Decompose monthly turnover into:
    - base_turnover = fraction of NAMES that rotated (Step-1 metric)
    - exposure_turnover = |Δ exposure| (rotates the gross exposure level)
    - total = base × exposure + exposure_turnover  (rough — cash ↔ holdings)
    """
    dates = sorted(holdings.keys())
    if len(dates) < 2:
        return {"base_mean": float("nan"), "expo_mean": float("nan"),
                "total_mean": float("nan"), "base_ann": float("nan"),
                "total_ann": float("nan")}
    base, expo = [], []
    for prev, curr in zip(dates[:-1], dates[1:]):
        prev_set, curr_set = set(holdings[prev]), set(holdings[curr])
        if not curr_set:
            continue
        base.append(len(curr_set - prev_set) / len(curr_set))
        e_prev = float(exposure_path.loc[prev]) if prev in exposure_path.index else 1.0
        e_curr = float(exposure_path.loc[curr]) if curr in exposure_path.index else 1.0
        expo.append(abs(e_curr - e_prev))
    total = [b * (e_curr or 1.0) + d for b, d, e_curr in zip(base, expo, [exposure_path.loc[d] if d in exposure_path.index else 1.0 for d in dates[1:]])]
    return {
        "base_mean":  float(np.mean(base)) if base else float("nan"),
        "expo_mean":  float(np.mean(expo)) if expo else float("nan"),
        "total_mean": float(np.mean(total)) if total else float("nan"),
        "base_ann":   float(np.mean(base) * 12) if base else float("nan"),
        "total_ann":  float(np.mean(total) * 12) if total else float("nan"),
    }


# ---------------------------------------------------------------------------
# Cost-adjusted

def cost_adjust(
    returns: pd.Series, monthly_one_way_turnover: pd.Series, cost_bps: float
) -> pd.Series:
    """Apply per-month cost = turnover × cost_bps / 10000."""
    if returns.empty:
        return returns
    cost = monthly_one_way_turnover.reindex(returns.index).fillna(0.0) * (cost_bps / 10000.0)
    return returns - cost


# ---------------------------------------------------------------------------
# Orchestrator

def run(
    results_csv: str = "data/output/walk_forward_v2_results.csv",
    benchmark_csv: str = "data/output/walk_forward_v2_benchmark.csv",
    output_dir: str = "data/output",
) -> dict:
    """End-to-end Phase D1 backtest. Returns dict of frames + writes CSVs."""
    results = pd.read_csv(resolve_path(results_csv), parse_dates=["rebalance_date"])

    universe = load_universe()
    theme_map = universe.set_index("ticker")["theme"].to_dict()
    cap_cfg = pm.load_theme_cap_config()
    cap_kwargs = pm.theme_cap_kwargs(theme_map) if cap_cfg["enable_theme_cap"] else {
        "theme_map": None, "max_per_theme": None
    }

    portfolio = pm.topn_returns(results, alpha_col="alpha_score", n=cap_cfg["top_n"], **cap_kwargs)
    holdings = pm.topn_holdings(results, alpha_col="alpha_score", n=cap_cfg["top_n"], **cap_kwargs)

    # Build PIT inputs for regime classification
    market_price = get_close_panel(["0050.TW"])["0050.TW"].dropna()
    ai_index_df = afi.run(write=False)
    ai_nav = afi.latest_aggregate_nav(ai_index_df).dropna()

    # Compute exposure-scaled path
    expo_path = compute_exposure_path(portfolio, market_price, ai_nav)
    raw_returns = expo_path["raw_return"]
    scaled_returns = expo_path["scaled_return"]

    # Metrics
    baseline_metrics = metrics_table(raw_returns, "baseline (no overlay)")
    scaled_metrics = metrics_table(scaled_returns, "D1 exposure-scaled")

    # Turnover
    base_turn = turnover_split(holdings, expo_path["applied_exposure"])

    # Per-month per-ticker base turnover series for cost adjustment
    dates = sorted(holdings.keys())
    base_turnover_monthly = pd.Series(
        [1.0] + [
            len(set(holdings[d2]) - set(holdings[d1])) / len(holdings[d2])
            for d1, d2 in zip(dates[:-1], dates[1:])
        ],
        index=pd.DatetimeIndex(dates),
    )
    expo_change_monthly = expo_path["applied_exposure"].diff().abs().fillna(0.0).reindex(dates).fillna(0.0)
    # For scaled portfolio, total monthly turnover ≈ base × exposure + |Δ exposure|
    scaled_turnover_monthly = base_turnover_monthly * expo_path["applied_exposure"].reindex(dates) + expo_change_monthly

    cost_adjusted = {}
    for cost in (25.0, 50.0):
        net_baseline = cost_adjust(raw_returns, base_turnover_monthly, cost)
        net_scaled = cost_adjust(scaled_returns, scaled_turnover_monthly, cost)
        cost_adjusted[f"baseline_{int(cost)}"] = metrics_table(net_baseline, f"baseline net @ {int(cost)} bps")
        cost_adjusted[f"scaled_{int(cost)}"] = metrics_table(net_scaled, f"D1 net @ {int(cost)} bps")

    # Output CSVs
    ensure_dir(output_dir)
    summary_rows = [baseline_metrics, scaled_metrics] + list(cost_adjusted.values())
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(resolve_path(f"{output_dir}/phase_d1_summary.csv"), index=False)

    expo_path.to_csv(resolve_path(f"{output_dir}/phase_d1_exposure_path.csv"))

    base_episodes = drawdown_episodes(raw_returns)
    scaled_episodes = drawdown_episodes(scaled_returns)
    eps_rows = []
    for label, eps in [("baseline", base_episodes), ("D1_scaled", scaled_episodes)]:
        for e in eps:
            eps_rows.append({
                "variant": label,
                "start": e.start, "end": e.end,
                "duration_months": e.duration_months,
                "max_dd": e.max_dd,
                "ongoing": e.end is None,
            })
    pd.DataFrame(eps_rows).to_csv(
        resolve_path(f"{output_dir}/phase_d1_dd_episodes.csv"), index=False
    )

    # Regime exposure timeline summary
    regime_summary = expo_path.groupby("regime_label").agg(
        n_months=("applied_exposure", "size"),
        avg_exposure=("applied_exposure", "mean"),
        avg_raw_return=("raw_return", "mean"),
        avg_scaled_return=("scaled_return", "mean"),
        dd_overrides=("dd_override_applied", "sum"),
    ).reset_index()
    regime_summary.to_csv(
        resolve_path(f"{output_dir}/phase_d1_regime_summary.csv"), index=False
    )

    logger.info("Wrote 4 Phase D1 CSVs to %s/", output_dir)

    return {
        "summary": summary_df,
        "exposure_path": expo_path,
        "regime_summary": regime_summary,
        "turnover_split": base_turn,
        "raw_returns": raw_returns,
        "scaled_returns": scaled_returns,
        "base_episodes": base_episodes,
        "scaled_episodes": scaled_episodes,
    }
