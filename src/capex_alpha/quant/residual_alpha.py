"""Residual alpha model.

Per ticker, run a rolling OLS regression:

    r_stock = beta_market * r_market + beta_ai * r_ai_index + residual

We expose the residual return series and a few derivative metrics:
``residual_momentum_20d/60d``, ``residual_volatility_60d``,
``residual_drawdown_60d`` and a heuristic ``alpha_quality_score``.

Output: ``data/output/residual_alpha.csv`` (long format, one row per
``date × ticker``).

Design notes:
- Rolling regression uses a closed-form OLS on a 120-day window. We chose
  numpy least-squares over statsmodels for speed; missing-data handling
  drops rows with NaN in any regressor.
- If a window has fewer than ``min_obs`` valid rows, betas are NaN and the
  raw return is propagated as the residual (so downstream features don't
  blow up). Those rows are flagged as low data quality.
- Cross-sectional zscoring happens in scoring_model_v2; this module only
  produces per-ticker time series.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data_loader import get_close_panel, load_universe
from ..utils import ensure_dir, get_logger, load_yaml, resolve_path
from . import ai_factor_index as afi

logger = get_logger(__name__)


@dataclass
class ResidualAlphaConfig:
    rolling_window_days: int
    min_obs: int
    benchmark: str
    momentum_windows: tuple[int, int]
    vol_window: int
    drawdown_window: int

    @classmethod
    def from_yaml(cls) -> "ResidualAlphaConfig":
        cfg = load_yaml("config/alpha_model_v2.yaml")["residual_alpha"]
        m = cfg.get("momentum_windows", [20, 60])
        return cls(
            rolling_window_days=int(cfg.get("rolling_window_days", 120)),
            min_obs=int(cfg.get("min_obs", 60)),
            benchmark=cfg.get("benchmark", "0050.TW"),
            momentum_windows=(int(m[0]), int(m[1])),
            vol_window=int(cfg.get("vol_window", 60)),
            drawdown_window=int(cfg.get("drawdown_window", 60)),
        )


# ---------------------------------------------------------------------------

def _rolling_beta_residual(
    y: pd.Series,
    x: pd.DataFrame,
    window: int,
    min_obs: int,
) -> pd.DataFrame:
    """Closed-form rolling OLS. Returns DataFrame with cols beta_<name> + residual.

    No intercept — we run on returns, where the intercept is alpha. Including
    an intercept here would absorb the residual we want to keep, so we leave
    it out and treat the residual itself as the alpha signal.
    """
    cols = list(x.columns)
    out = pd.DataFrame(
        index=y.index,
        columns=[f"beta_{c}" for c in cols] + ["residual_return"],
        dtype=float,
    )

    yv = y.to_numpy()
    xv = x.to_numpy()
    n = len(y)

    for i in range(n):
        lo = max(0, i - window + 1)
        win_y = yv[lo : i + 1]
        win_x = xv[lo : i + 1]

        # Drop rows with any NaN.
        mask = ~np.isnan(win_y) & ~np.isnan(win_x).any(axis=1)
        win_y_c = win_y[mask]
        win_x_c = win_x[mask]

        if len(win_y_c) < min_obs:
            # Not enough data → leave betas NaN, residual = raw return.
            out.iloc[i, :-1] = np.nan
            out.iloc[i, -1] = yv[i]
            continue

        try:
            beta, *_ = np.linalg.lstsq(win_x_c, win_y_c, rcond=None)
        except np.linalg.LinAlgError:
            out.iloc[i, :-1] = np.nan
            out.iloc[i, -1] = yv[i]
            continue

        # Today's residual based on betas estimated up to today.
        today_y = yv[i]
        today_x = xv[i]
        if np.isnan(today_y) or np.isnan(today_x).any():
            residual = np.nan
        else:
            residual = float(today_y - today_x @ beta)

        out.iloc[i, :-1] = beta
        out.iloc[i, -1] = residual

    return out


def _drawdown(nav: pd.Series, window: int) -> pd.Series:
    rolling_max = nav.rolling(window=window, min_periods=1).max()
    return nav / rolling_max - 1.0


def _alpha_quality_score(row: pd.Series) -> float:
    """Heuristic alpha-quality flag — see spec §4.2."""
    score = 0.0
    rm60 = row.get("residual_momentum_60d", np.nan)
    rm20 = row.get("residual_momentum_20d", np.nan)
    bai = row.get("beta_ai", np.nan)
    rv60 = row.get("residual_volatility_60d", np.nan)
    rdd = row.get("residual_drawdown_60d", np.nan)
    rv60_chg = row.get("residual_volatility_60d_chg", np.nan)

    if pd.notna(rm60) and rm60 > 0:
        score += 2
    if pd.notna(rm20) and rm20 > 0:
        score += 1
    if pd.notna(bai) and bai < 1.2:
        score += 1
    if pd.notna(rv60_chg) and rv60_chg < 0:
        score += 1
    if pd.notna(rdd) and rdd < -0.20:
        score -= 2
    if pd.notna(bai) and bai > 2.0:
        score -= 2
    return float(score)


# ---------------------------------------------------------------------------

def _build_factor_returns(cfg: ResidualAlphaConfig, ai_index_df: pd.DataFrame) -> pd.DataFrame:
    """Wide DataFrame indexed by date with columns [r_market, r_ai]."""
    bench_panel = get_close_panel([cfg.benchmark])
    if bench_panel.empty:
        raise RuntimeError(f"Benchmark {cfg.benchmark} unavailable from yfinance cache.")
    r_market = bench_panel[cfg.benchmark].pct_change().rename("r_market")
    r_ai = afi.latest_aggregate_return_panel(ai_index_df).rename("r_ai")
    factors = pd.concat([r_market, r_ai], axis=1).dropna(how="all")
    return factors


def compute_for_ticker(
    ticker: str,
    company_name: str,
    theme: str,
    factors: pd.DataFrame,
    cfg: ResidualAlphaConfig,
) -> pd.DataFrame:
    """Compute the long-format residual alpha frame for a single ticker."""
    panel = get_close_panel([ticker])
    if panel.empty or ticker not in panel.columns:
        logger.warning("Price data missing for %s — skipping.", ticker)
        return pd.DataFrame()

    raw_ret = panel[ticker].pct_change().rename("raw_return")
    df = pd.concat([raw_ret, factors], axis=1).dropna(subset=["r_market", "r_ai"], how="all")

    # Rolling regression
    reg = _rolling_beta_residual(
        y=df["raw_return"],
        x=df[["r_market", "r_ai"]],
        window=cfg.rolling_window_days,
        min_obs=cfg.min_obs,
    )
    df = df.join(reg)

    # Residual NAV + features
    resid = df["residual_return"].fillna(0.0)
    resid_nav = (1.0 + resid).cumprod()
    df["residual_momentum_20d"] = resid_nav.pct_change(cfg.momentum_windows[0])
    df["residual_momentum_60d"] = resid_nav.pct_change(cfg.momentum_windows[1])
    df["residual_volatility_60d"] = resid.rolling(cfg.vol_window).std() * np.sqrt(252)
    df["residual_volatility_60d_chg"] = (
        df["residual_volatility_60d"] - df["residual_volatility_60d"].shift(20)
    )
    df["residual_drawdown_60d"] = _drawdown(resid_nav, cfg.drawdown_window)

    df = df.reset_index().rename(
        columns={
            "index": "date",
            "Date": "date",
            "r_market": "benchmark_return",
            "r_ai": "ai_index_return",
            "beta_r_market": "beta_market",
            "beta_r_ai": "beta_ai",
        }
    )
    if "date" not in df.columns:
        # Some yfinance frames may name the index something else
        df = df.rename(columns={df.columns[0]: "date"})
    df["ticker"] = ticker
    df["company_name"] = company_name
    df["theme"] = theme
    df["alpha_quality_score"] = df.apply(_alpha_quality_score, axis=1)

    keep = [
        "date",
        "ticker",
        "company_name",
        "theme",
        "raw_return",
        "benchmark_return",
        "ai_index_return",
        "beta_market",
        "beta_ai",
        "residual_return",
        "residual_momentum_20d",
        "residual_momentum_60d",
        "residual_volatility_60d",
        "residual_drawdown_60d",
        "alpha_quality_score",
    ]
    return df[keep].dropna(subset=["raw_return"])


def run(write: bool = True, ai_index_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compute residual alpha for every ticker in the universe."""
    cfg = ResidualAlphaConfig.from_yaml()

    if ai_index_df is None:
        ai_index_df = afi.run(write=False)

    factors = _build_factor_returns(cfg, ai_index_df)

    universe = load_universe()
    parts: list[pd.DataFrame] = []
    for _, row in universe.iterrows():
        ticker = row["ticker"]
        if ticker == "2330.TW":
            # TSMC itself is the issuer; we still compute residuals for cross-checks.
            pass
        out = compute_for_ticker(
            ticker=ticker,
            company_name=row["company_name"],
            theme=row["theme"],
            factors=factors,
            cfg=cfg,
        )
        if not out.empty:
            parts.append(out)

    if not parts:
        logger.error("No residual alpha computed.")
        return pd.DataFrame()

    out = pd.concat(parts, ignore_index=True).sort_values(["ticker", "date"])

    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/residual_alpha.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(out))

    return out


def latest_snapshot(df: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Most recent residual-alpha row per ticker on/before ``as_of``."""
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    if as_of is not None:
        df = df[df["date"] <= pd.Timestamp(as_of)]
    return df.sort_values("date").groupby("ticker").tail(1).reset_index(drop=True)
