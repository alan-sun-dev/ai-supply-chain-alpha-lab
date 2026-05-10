"""Factor Model v2 — long-format factor frame for cross-sectional ranking.

Each row is a (date, ticker, factor_name) cell with raw value, z-score
across the universe on that date, configured weight, and the resulting
``factor_contribution = factor_zscore * factor_weight``.

We deliberately do NOT use raw price momentum as a primary factor. The
``residual_momentum_*`` factors come from ``residual_alpha.py``, which has
already stripped market and AI-theme beta.

All helpers accept ``as_of`` so the same code path works in walk-forward.
Point-in-time treatment:

- Monthly revenue: only records with ``year_month + 45 days <= as_of``
  (台股 monthly revenue reporting deadline is the 10th of the next month;
  45 days is a conservative buffer).
- Institutional flow: ``date <= as_of`` (reported same day after close).
- Valuation: ``date <= as_of``.
- Prices: ``date <= as_of``.
- Residual alpha: handled by ``residual_alpha.latest_snapshot(df, as_of=...)``.
- AI factor index: filter by ``date <= as_of``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data_loader import (
    get_close_panel,
    load_institutional_flow,
    load_monthly_revenue,
    load_universe,
    load_valuation,
)
from ..utils import ensure_dir, get_logger, load_yaml, resolve_path
from . import residual_alpha as ra

logger = get_logger(__name__)


FACTOR_COLUMNS = [
    "residual_momentum_60d",
    "residual_momentum_20d",
    "revenue_acceleration",
    "sector_relative_strength",
    "institutional_flow_score",
    "valuation_risk_score",
    "volatility_contraction",
    "drawdown_recovery",
    "theme_strength",
    "capex_context_score",
]

# Conservative lag for 台股月營收 reporting (deadline = 10th of next month)
REVENUE_REPORTING_LAG_DAYS = 45


# ---------------------------------------------------------------------------

def _zscore_cross_section(s: pd.Series) -> pd.Series:
    """Per-date cross-sectional z-score; ignores NaNs."""
    if s.empty:
        return s
    valid = s.dropna()
    if len(valid) < 3:
        return pd.Series(0.0, index=s.index)
    mu = valid.mean()
    sd = valid.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return pd.Series(0.0, index=s.index)
    return ((s - mu) / sd).fillna(0.0).clip(-3, 3)


def _filter_to_as_of(df: pd.DataFrame, date_col: str, as_of: pd.Timestamp | None) -> pd.DataFrame:
    if as_of is None or df.empty:
        return df
    return df[df[date_col] <= pd.Timestamp(as_of)]


# ---------------------------------------------------------------------------

def _revenue_acceleration(
    rev: pd.DataFrame, universe: pd.DataFrame, as_of: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Latest revenue acceleration per ticker (PIT-safe)."""
    if rev.empty:
        return pd.DataFrame(columns=["ticker", "revenue_acceleration"])

    rev = rev.dropna(subset=["yoy_pct"]).copy()
    rev["year_month"] = pd.to_datetime(rev["year_month"])
    if as_of is not None:
        cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=REVENUE_REPORTING_LAG_DAYS)
        rev = rev[rev["year_month"] <= cutoff]
    rev = rev.sort_values(["ticker", "year_month"])

    rows = []
    for ticker, sub in rev.groupby("ticker"):
        if len(sub) < 6:
            rows.append({"ticker": ticker, "revenue_acceleration": np.nan})
            continue
        latest = sub["yoy_pct"].iloc[-3:].mean()
        prior = sub["yoy_pct"].iloc[-6:-3].mean()
        rows.append({"ticker": ticker, "revenue_acceleration": latest - prior})
    return pd.DataFrame(rows)


def _institutional_flow_score(
    flow: pd.DataFrame, lookback_days: int = 30, as_of: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Sum of foreign + trust net over the last ``lookback_days`` (PIT-safe)."""
    if flow.empty:
        return pd.DataFrame(columns=["ticker", "institutional_flow_score"])

    flow = flow.copy()
    flow["date"] = pd.to_datetime(flow["date"])
    if as_of is not None:
        flow = flow[flow["date"] <= pd.Timestamp(as_of)]
    if flow.empty:
        return pd.DataFrame(columns=["ticker", "institutional_flow_score"])
    end_date = flow["date"].max()
    start_date = end_date - pd.Timedelta(days=lookback_days * 2)
    flow = flow[flow["date"] >= start_date]

    rows = []
    for ticker, sub in flow.groupby("ticker"):
        sub = sub.sort_values("date").tail(lookback_days)
        net = float(sub["foreign_net"].sum() + sub.get("trust_net", pd.Series([0])).sum())
        rows.append({"ticker": ticker, "institutional_flow_score": net})
    return pd.DataFrame(rows)


def _valuation_risk_score(val: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Higher = more expensive. Used as a *penalty* factor (negative weight)."""
    if val.empty:
        return pd.DataFrame(columns=["ticker", "valuation_risk_score"])
    val = val.copy()
    val["date"] = pd.to_datetime(val["date"])
    if as_of is not None:
        val = val[val["date"] <= pd.Timestamp(as_of)]
    if val.empty:
        return pd.DataFrame(columns=["ticker", "valuation_risk_score"])
    latest = val.sort_values("date").groupby("ticker").tail(1)
    out = latest[["ticker", "per", "pbr"]].copy()
    out["valuation_risk_score"] = (
        out["per"].fillna(out["per"].median()).clip(lower=0).rank(pct=True) * 0.7
        + out["pbr"].fillna(out["pbr"].median()).clip(lower=0).rank(pct=True) * 0.3
    )
    return out[["ticker", "valuation_risk_score"]]


def _sector_relative_strength(
    price_panel: pd.DataFrame, universe: pd.DataFrame, as_of: pd.Timestamp | None = None
) -> pd.DataFrame:
    """20-day return minus theme-mean 20-day return."""
    if price_panel.empty:
        return pd.DataFrame(columns=["ticker", "sector_relative_strength"])

    panel = price_panel
    if as_of is not None:
        panel = price_panel.loc[:pd.Timestamp(as_of)]
    if panel.empty:
        return pd.DataFrame(columns=["ticker", "sector_relative_strength"])

    rets_20d = panel.pct_change(20).iloc[-1]
    universe_idx = universe.set_index("ticker")
    rows = []
    for ticker, ret in rets_20d.items():
        if ticker not in universe_idx.index or pd.isna(ret):
            rows.append({"ticker": ticker, "sector_relative_strength": np.nan})
            continue
        theme = universe_idx.loc[ticker, "theme"]
        peers = universe_idx[universe_idx["theme"] == theme].index.tolist()
        peer_rets = rets_20d.reindex(peers).dropna()
        peer_mean = peer_rets.mean() if len(peer_rets) else np.nan
        rows.append(
            {
                "ticker": ticker,
                "sector_relative_strength": (ret - peer_mean) if pd.notna(peer_mean) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _volatility_contraction_and_drawdown_recovery(
    residual_df: pd.DataFrame, as_of: pd.Timestamp | None = None
) -> pd.DataFrame:
    if residual_df.empty:
        return pd.DataFrame(columns=["ticker", "volatility_contraction", "drawdown_recovery"])

    snap = ra.latest_snapshot(residual_df, as_of=as_of)
    snap["volatility_contraction"] = -snap["residual_volatility_60d"].fillna(0.0)
    snap["drawdown_recovery"] = -snap["residual_drawdown_60d"].fillna(0.0)
    return snap[["ticker", "volatility_contraction", "drawdown_recovery"]]


def _theme_strength(
    ai_index_df: pd.DataFrame, universe: pd.DataFrame, as_of: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Theme momentum proxy from the AI factor index frame (PIT-safe)."""
    if ai_index_df.empty:
        return pd.DataFrame(columns=["ticker", "theme_strength"])

    df = ai_index_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    if as_of is not None:
        df = df[df["date"] <= pd.Timestamp(as_of)]
    if df.empty:
        return pd.DataFrame(columns=["ticker", "theme_strength"])

    latest = df.sort_values("date").groupby("theme").tail(1).set_index("theme")
    rows = []
    for _, r in universe.iterrows():
        theme = r["theme"]
        ts = latest.loc[theme, "theme_momentum_60d"] if theme in latest.index else np.nan
        rows.append({"ticker": r["ticker"], "theme_strength": ts})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------

def run(
    write: bool = True,
    residual_df: pd.DataFrame | None = None,
    ai_index_df: pd.DataFrame | None = None,
    as_of: pd.Timestamp | None = None,
    price_panel: pd.DataFrame | None = None,
    monthly_revenue: pd.DataFrame | None = None,
    institutional_flow: pd.DataFrame | None = None,
    valuation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the long-format factor frame as of the given date.

    Pre-loaded inputs may be passed in to avoid repeated I/O during
    walk-forward; otherwise they are loaded on demand.
    """
    cfg = load_yaml("config/alpha_model_v2.yaml")["scoring_v2"]
    factor_weights: dict[str, float] = cfg["factor_weights"]

    universe = load_universe()
    universe = universe[universe["ticker"] != "2330.TW"]

    if residual_df is None:
        residual_df = ra.run(write=False, ai_index_df=ai_index_df)
    if ai_index_df is None:
        from . import ai_factor_index as afi
        ai_index_df = afi.run(write=False)
    if monthly_revenue is None:
        monthly_revenue = load_monthly_revenue()
    if institutional_flow is None:
        institutional_flow = load_institutional_flow()
    if valuation is None:
        valuation = load_valuation()
    if price_panel is None:
        price_panel = get_close_panel(universe["ticker"].tolist())

    snap = ra.latest_snapshot(residual_df, as_of=as_of)
    snap_idx = snap.set_index("ticker")

    raw_frames: dict[str, pd.DataFrame] = {}
    raw_frames["residual_momentum_60d"] = snap[["ticker"]].assign(
        residual_momentum_60d=snap["residual_momentum_60d"].values
    )
    raw_frames["residual_momentum_20d"] = snap[["ticker"]].assign(
        residual_momentum_20d=snap["residual_momentum_20d"].values
    )
    raw_frames["revenue_acceleration"] = _revenue_acceleration(monthly_revenue, universe, as_of=as_of)
    raw_frames["institutional_flow_score"] = _institutional_flow_score(institutional_flow, as_of=as_of)
    raw_frames["valuation_risk_score"] = _valuation_risk_score(valuation, as_of=as_of)
    raw_frames["sector_relative_strength"] = _sector_relative_strength(price_panel, universe, as_of=as_of)
    vc_dr = _volatility_contraction_and_drawdown_recovery(residual_df, as_of=as_of)
    raw_frames["volatility_contraction"] = vc_dr[["ticker", "volatility_contraction"]]
    raw_frames["drawdown_recovery"] = vc_dr[["ticker", "drawdown_recovery"]]
    raw_frames["theme_strength"] = _theme_strength(ai_index_df, universe, as_of=as_of)

    raw_frames["capex_context_score"] = pd.DataFrame(
        {"ticker": universe["ticker"].tolist(), "capex_context_score": 0.0}
    )

    if not snap.empty:
        eval_date = pd.to_datetime(snap["date"].max())
    else:
        eval_date = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.today().normalize()

    rows: list[dict] = []
    for factor, df in raw_frames.items():
        if df.empty:
            continue
        merged = universe[["ticker"]].merge(df, on="ticker", how="left")
        z = _zscore_cross_section(merged[factor])
        weight = factor_weights.get(factor, 0.0)
        for ticker, val, zv in zip(merged["ticker"], merged[factor], z):
            rows.append(
                {
                    "date": eval_date,
                    "ticker": ticker,
                    "factor_name": factor,
                    "factor_value": float(val) if pd.notna(val) else np.nan,
                    "factor_zscore": float(zv) if pd.notna(zv) else 0.0,
                    "factor_weight": float(weight),
                    "factor_contribution": (float(zv) if pd.notna(zv) else 0.0) * float(weight),
                }
            )

    out = pd.DataFrame(rows)
    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/factor_model_v2.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(out))

    return out
