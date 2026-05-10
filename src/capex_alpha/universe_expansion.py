"""Phase C — universe expansion: candidate dedup + liquidity filter.

Pipeline
--------
1. Load candidate CSV (>~75 tickers across 13 themes).
2. Dedup on ticker; if a ticker appears with multiple themes the FIRST
   occurrence's primary theme wins.
3. Pull yfinance OHLCV for every candidate (graceful fallback for missing).
4. Compute liquidity stats per ticker:
   - avg_daily_value_60d  ≈ mean(close × volume) over last 60 trading days
   - avg_volume_60d       = mean(volume) over last 60
   - missing_data_ratio   = NaN closes / total over last 60
5. Apply filter — by default keep tickers with:
   - data available
   - missing_ratio < 10%
   - avg_daily_value_60d ≥ NTD 30M  (configurable)
6. Write filtered universe CSV usable by the rest of the v2 pipeline
   (same schema as ``data/manual/beneficiary_universe.csv``).

Output is consumed by ``validation.universe_validation`` for backtest
comparison across original / expanded_liquid_40 / expanded_liquid_60 /
expanded_all_available.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data_loader import download_prices
from .utils import ensure_dir, get_logger, resolve_path

logger = get_logger(__name__)


CANDIDATE_PATH_DEFAULT = "data/manual/beneficiary_universe_phase_c_candidates.csv"
EXPANDED_PATH_DEFAULT  = "data/manual/beneficiary_universe_expanded.csv"
LIQUIDITY_REPORT_PATH  = "data/output/universe_liquidity_check.csv"

DEFAULT_MIN_ADV_TWD     = 30_000_000     # NTD 30M average daily value
DEFAULT_MAX_MISSING_PCT = 0.10           # 10% missing data tolerance
LIQUIDITY_LOOKBACK_DAYS = 60


# ---------------------------------------------------------------------------
# Candidate loading + dedup

def load_candidates(path: str = CANDIDATE_PATH_DEFAULT) -> pd.DataFrame:
    """Load candidate CSV; dedup on ticker (first occurrence wins)."""
    p = resolve_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Candidate CSV missing: {p}")
    df = pd.read_csv(p, dtype={"ticker": str})
    df["ticker"] = df["ticker"].str.strip()
    before = len(df)
    df = df.drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)
    if len(df) < before:
        logger.warning("Dropped %d duplicate ticker(s); kept first occurrence.", before - len(df))
    return df


# ---------------------------------------------------------------------------
# Liquidity check

@dataclass
class LiquidityStats:
    avg_daily_value_60d: float
    avg_volume_60d:      float
    missing_data_ratio:  float
    n_obs:               int
    last_date:           pd.Timestamp | None


def _compute_stats_for_ticker(df: pd.DataFrame | None,
                              lookback: int = LIQUIDITY_LOOKBACK_DAYS) -> LiquidityStats:
    if df is None or df.empty:
        return LiquidityStats(np.nan, np.nan, 1.0, 0, None)
    sub = df.tail(lookback).copy()
    close = sub.get("Close")
    volume = sub.get("Volume")
    if close is None or volume is None:
        return LiquidityStats(np.nan, np.nan, 1.0, len(sub), sub.index[-1] if len(sub) else None)
    daily_value = close * volume
    n = len(sub)
    valid = (~close.isna() & ~volume.isna()).sum()
    missing = 1.0 - valid / n if n else 1.0
    return LiquidityStats(
        avg_daily_value_60d=float(daily_value.dropna().mean()) if daily_value.notna().any() else np.nan,
        avg_volume_60d=float(volume.dropna().mean()) if volume.notna().any() else np.nan,
        missing_data_ratio=float(missing),
        n_obs=int(n),
        last_date=sub.index[-1] if n else None,
    )


def liquidity_check(
    candidates: pd.DataFrame,
    use_cache: bool = True,
    start: str | None = None,
) -> pd.DataFrame:
    """Run yfinance fetch (cached) + liquidity stats for every candidate.

    Returns a frame keyed by ticker with stats + tier classification:
    - ``A`` — ADV ≥ 100M TWD
    - ``B`` — 30M ≤ ADV < 100M
    - ``C`` — ADV < 30M
    - ``X`` — no data
    """
    tickers = candidates["ticker"].tolist()
    logger.info("Fetching prices for %d candidates …", len(tickers))
    raw = download_prices(tickers, start=start, use_cache=use_cache)

    rows: list[dict] = []
    universe_idx = candidates.set_index("ticker")
    for t in tickers:
        df = raw.get(t)
        s = _compute_stats_for_ticker(df)
        adv = s.avg_daily_value_60d
        if np.isnan(adv):
            tier = "X"
        elif adv >= 100_000_000:
            tier = "A"
        elif adv >= 30_000_000:
            tier = "B"
        else:
            tier = "C"
        rows.append({
            "ticker":              t,
            "company_name":        universe_idx.loc[t, "company_name"] if t in universe_idx.index else "",
            "theme":               universe_idx.loc[t, "theme"] if t in universe_idx.index else "",
            "avg_daily_value_60d": adv,
            "avg_volume_60d":      s.avg_volume_60d,
            "missing_data_ratio":  s.missing_data_ratio,
            "n_obs":               s.n_obs,
            "last_date":           s.last_date,
            "liquidity_tier":      tier,
            "data_available":      s.n_obs > 0 and not np.isnan(adv),
        })
    return pd.DataFrame(rows)


def apply_liquidity_filter(
    candidates: pd.DataFrame,
    liquidity: pd.DataFrame,
    min_adv: float = DEFAULT_MIN_ADV_TWD,
    max_missing: float = DEFAULT_MAX_MISSING_PCT,
    keep_required: list[str] | None = None,
) -> pd.DataFrame:
    """Combine candidate + liquidity → final universe with include/exclude flags.

    ``keep_required``: list of tickers that always pass (e.g. issuer 2330.TW).
    """
    keep_required = set(keep_required or [])
    merged = candidates.merge(liquidity, on=["ticker", "company_name", "theme"], how="left")

    def _decide(row) -> tuple[bool, str]:
        t = row["ticker"]
        if t in keep_required:
            return True, "always_keep"
        if not row.get("data_available", False):
            return False, "no_data"
        if pd.isna(row.get("avg_daily_value_60d", np.nan)):
            return False, "no_adv"
        if row["missing_data_ratio"] > max_missing:
            return False, f"missing_ratio_{row['missing_data_ratio']:.1%}"
        if row["avg_daily_value_60d"] < min_adv:
            return False, f"adv_below_{min_adv:.0f}"
        return True, "ok"

    decisions = merged.apply(_decide, axis=1)
    merged["include_final"] = [d[0] for d in decisions]
    merged["exclude_reason"] = [d[1] for d in decisions]
    return merged


# ---------------------------------------------------------------------------
# Build expanded CSVs

def _trim_to_universe_schema(merged: pd.DataFrame) -> pd.DataFrame:
    """Keep only the columns ``load_universe()`` and downstream code expect."""
    cols_needed = ["ticker", "company_name", "theme"]
    extras = [c for c in ["sub_theme", "benefit_logic", "capex_stage",
                          "expected_lag_months", "confidence_level", "notes"]
              if c in merged.columns]
    return merged[cols_needed + extras].copy()


def build_expanded_universes(
    candidates: pd.DataFrame,
    liquidity: pd.DataFrame,
    output_path: str = EXPANDED_PATH_DEFAULT,
    min_adv: float = DEFAULT_MIN_ADV_TWD,
    max_missing: float = DEFAULT_MAX_MISSING_PCT,
    keep_required: list[str] | None = None,
    write: bool = True,
) -> dict[str, pd.DataFrame]:
    """Produce the family of universe CSVs.

    Returns
    -------
    dict with keys:
      - ``expanded_all_available`` : every candidate that has data
      - ``expanded_liquid_60``     : top 60 by ADV (data-available subset)
      - ``expanded_liquid_40``     : top 40 by ADV
    """
    merged = apply_liquidity_filter(candidates, liquidity, min_adv=min_adv,
                                    max_missing=max_missing, keep_required=keep_required)

    available = merged[merged["data_available"].astype(bool)].copy()
    available = available.sort_values("avg_daily_value_60d", ascending=False)

    passed = merged[merged["include_final"]].copy()
    passed = passed.sort_values("avg_daily_value_60d", ascending=False)

    out: dict[str, pd.DataFrame] = {
        "expanded_all_available": _trim_to_universe_schema(available),
        "expanded_liquid_60":     _trim_to_universe_schema(passed.head(60)),
        "expanded_liquid_40":     _trim_to_universe_schema(passed.head(40)),
    }

    if write:
        ensure_dir("data/manual")
        ensure_dir("data/output")
        # The "primary" expanded CSV (used by daily pipeline if user opts in)
        out["expanded_liquid_60"].to_csv(resolve_path(output_path), index=False)
        for name, df in out.items():
            extra = resolve_path(f"data/manual/beneficiary_universe_{name}.csv")
            df.to_csv(extra, index=False)
        merged.to_csv(resolve_path(LIQUIDITY_REPORT_PATH), index=False)
        logger.info("Wrote %s + 3 expanded variants + liquidity report.", output_path)

    return out
