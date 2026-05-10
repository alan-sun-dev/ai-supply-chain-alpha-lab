"""Extended portfolio metrics — turnover, monthly hit rate, CAGR.

Built off the long-format ``walk_forward_v2_results.csv`` so we can compare
A1 vs A2 (and any future variant) without re-running scoring.

Step-1 (2026-05-03) added optional theme-cap support to ``topn_holdings`` /
``topn_returns``: pass a ``theme_map`` (ticker → theme) and ``max_per_theme``
to enforce a per-theme cap on the equal-weight top-N portfolio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import load_yaml


def load_theme_cap_config() -> dict:
    """Read scoring_v2.portfolio_construction from alpha_model_v2.yaml.

    Returns a dict with keys ``top_n``, ``max_per_theme``, ``enable_theme_cap``.
    Falls back to defaults (cap disabled) when the section is missing.
    """
    try:
        cfg = load_yaml("config/alpha_model_v2.yaml")
        pc = cfg.get("scoring_v2", {}).get("portfolio_construction", {}) or {}
    except Exception:
        pc = {}
    return {
        "top_n":            int(pc.get("top_n", 5)),
        "max_per_theme":    int(pc.get("max_per_theme", 5)),  # default = no cap
        "enable_theme_cap": bool(pc.get("enable_theme_cap", False)),
    }


def theme_cap_kwargs(theme_map: dict | None) -> dict:
    """Convenience: produce {theme_map, max_per_theme} kwargs from YAML cfg."""
    cfg = load_theme_cap_config()
    if not cfg["enable_theme_cap"] or theme_map is None:
        return {"theme_map": None, "max_per_theme": None}
    return {"theme_map": theme_map, "max_per_theme": cfg["max_per_theme"]}


def _greedy_top_n_with_cap(sub: pd.DataFrame, alpha_col: str, n: int,
                           theme_map: dict | None, max_per_theme: int | None) -> list[str]:
    """Greedy top-N respecting per-theme cap (if both args provided)."""
    sub = sub.sort_values(alpha_col, ascending=False)
    if theme_map is None or max_per_theme is None or max_per_theme >= n:
        return sub.head(n)["ticker"].tolist()

    picks: list[str] = []
    theme_count: dict[str, int] = {}
    for _, r in sub.iterrows():
        theme = theme_map.get(r["ticker"], "unknown")
        if theme_count.get(theme, 0) >= max_per_theme:
            continue
        picks.append(r["ticker"])
        theme_count[theme] = theme_count.get(theme, 0) + 1
        if len(picks) >= n:
            break
    return picks


def topn_holdings(df: pd.DataFrame, alpha_col: str = "alpha_score", n: int = 5,
                  theme_map: dict | None = None,
                  max_per_theme: int | None = None) -> dict[pd.Timestamp, list[str]]:
    """Return {rebalance_date: [top-N tickers]} ordered by alpha_col.

    If ``theme_map`` and ``max_per_theme`` are both provided, applies a
    per-theme cap during selection (Step-1 portfolio construction layer):
    no more than ``max_per_theme`` names from the same theme.
    """
    out: dict[pd.Timestamp, list[str]] = {}
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[alpha_col])
        if len(sub) < n:
            continue
        picks = _greedy_top_n_with_cap(sub, alpha_col, n, theme_map, max_per_theme)
        if len(picks) >= n:
            out[pd.Timestamp(t)] = picks
    return out


def topn_returns(df: pd.DataFrame, alpha_col: str = "alpha_score",
                 fwd_col: str = "fwd_return_1m", n: int = 5,
                 theme_map: dict | None = None,
                 max_per_theme: int | None = None) -> pd.Series:
    """Equal-weight top-N at each rebalance → monthly portfolio return series."""
    rets, dates = [], []
    for t, sub in df.groupby("rebalance_date"):
        sub = sub.dropna(subset=[alpha_col, fwd_col])
        if len(sub) < n:
            continue
        picks = _greedy_top_n_with_cap(sub, alpha_col, n, theme_map, max_per_theme)
        if len(picks) < n:
            continue
        top = sub[sub["ticker"].isin(picks)]
        rets.append(float(top[fwd_col].mean()))
        dates.append(pd.Timestamp(t))
    return pd.Series(rets, index=pd.DatetimeIndex(dates), name=alpha_col)


# ---------------------------------------------------------------------------

def turnover(holdings: dict[pd.Timestamp, list[str]]) -> dict[str, float]:
    """One-way monthly turnover for an equal-weight top-N strategy.

    Per rebalance: ``len(new \\ old) / N`` — fraction of slots replaced.
    Returns mean and median across rebalances; first month skipped.
    """
    dates = sorted(holdings.keys())
    if len(dates) < 2:
        return {"mean_one_way": float("nan"), "median_one_way": float("nan"),
                "annualized": float("nan"), "n_rebalances": 0}

    changes: list[float] = []
    for prev, curr in zip(dates[:-1], dates[1:]):
        prev_set, curr_set = set(holdings[prev]), set(holdings[curr])
        if not curr_set:
            continue
        changes.append(len(curr_set - prev_set) / len(curr_set))
    if not changes:
        return {"mean_one_way": float("nan"), "median_one_way": float("nan"),
                "annualized": float("nan"), "n_rebalances": 0}
    arr = np.asarray(changes, dtype=float)
    return {
        "mean_one_way":   float(arr.mean()),
        "median_one_way": float(np.median(arr)),
        "annualized":     float(arr.mean() * 12.0),  # monthly rebalance
        "n_rebalances":   int(len(arr)),
    }


# ---------------------------------------------------------------------------

def cagr(returns: pd.Series, periods_per_year: int = 12) -> float:
    if returns.empty:
        return float("nan")
    n = len(returns)
    nav = float((1.0 + returns.fillna(0.0)).prod())
    years = n / periods_per_year
    if years <= 0:
        return float("nan")
    return float(nav ** (1.0 / years) - 1.0)


def max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    return float((nav / nav.cummax() - 1.0).min())


def sharpe(returns: pd.Series, periods_per_year: int = 12) -> float:
    if returns.empty or returns.std(ddof=0) == 0:
        return float("nan")
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(periods_per_year))


def monthly_hit_rate(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    return float((returns > 0).mean())


# ---------------------------------------------------------------------------

def full_metrics(df: pd.DataFrame, alpha_col: str = "alpha_score",
                 fwd_col: str = "fwd_return_1m", n: int = 5,
                 theme_map: dict | None = None,
                 max_per_theme: int | None = None) -> dict:
    """One-shot: portfolio Sharpe / DD / CAGR / hit + turnover."""
    rets = topn_returns(df, alpha_col=alpha_col, fwd_col=fwd_col, n=n,
                        theme_map=theme_map, max_per_theme=max_per_theme)
    hold = topn_holdings(df, alpha_col=alpha_col, n=n,
                         theme_map=theme_map, max_per_theme=max_per_theme)
    to = turnover(hold)
    nav = (1.0 + rets.fillna(0.0)).cumprod()
    return {
        "n_months":          int(len(rets)),
        "total_return":      float(nav.iloc[-1] - 1.0) if len(nav) else 0.0,
        "cagr":              cagr(rets),
        "sharpe_ann":        sharpe(rets),
        "max_dd":            max_drawdown(rets),
        "mean_monthly":      float(rets.mean()) if len(rets) else float("nan"),
        "median_monthly":    float(rets.median()) if len(rets) else float("nan"),
        "monthly_hit_rate":  monthly_hit_rate(rets),
        "turnover_one_way_mean":   to["mean_one_way"],
        "turnover_one_way_median": to["median_one_way"],
        "turnover_annualized":     to["annualized"],
    }


def benchmark_metrics(returns: pd.Series) -> dict:
    """Same shape as full_metrics, for the benchmark return series."""
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    return {
        "n_months":          int(len(returns)),
        "total_return":      float(nav.iloc[-1] - 1.0) if len(nav) else 0.0,
        "cagr":              cagr(returns),
        "sharpe_ann":        sharpe(returns),
        "max_dd":            max_drawdown(returns),
        "mean_monthly":      float(returns.mean()) if len(returns) else float("nan"),
        "median_monthly":    float(returns.median()) if len(returns) else float("nan"),
        "monthly_hit_rate":  monthly_hit_rate(returns),
        "turnover_one_way_mean":   float("nan"),
        "turnover_one_way_median": float("nan"),
        "turnover_annualized":     float("nan"),
    }
