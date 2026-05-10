"""Data loaders: manual CSVs + yfinance prices with on-disk cache."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .utils import (
    ensure_dir,
    get_logger,
    load_data_sources_config,
    load_universe_config,
    resolve_path,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Manual CSV loaders
# ---------------------------------------------------------------------------

_UNIVERSE_OVERRIDE: str | None = None


def set_universe_override(path: str | None) -> None:
    """Set / clear a process-level override for ``load_universe()``.

    Used by Phase C universe validation to swap universes for backtests
    without touching every callsite.  Pass ``None`` to clear.
    """
    global _UNIVERSE_OVERRIDE
    _UNIVERSE_OVERRIDE = path


def load_universe(path: str | None = None) -> pd.DataFrame:
    """Load the beneficiary universe CSV.

    Resolution order: explicit ``path`` > module-level override >
    ``config/universe.yaml``.  Explicit/override paths must point to a CSV
    with the same schema as ``data/manual/beneficiary_universe.csv``
    (ticker, company_name, theme, ...).
    """
    if path is None:
        path = _UNIVERSE_OVERRIDE
    if path is None:
        cfg = load_universe_config()
        path = cfg["manual_files"]["beneficiary_universe"]
    p = resolve_path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Universe file missing: {p}. Run scripts/init_manual_data.py first."
        )
    df = pd.read_csv(p, dtype={"ticker": str})
    df["ticker"] = df["ticker"].str.strip()
    return df


def load_capex_events() -> pd.DataFrame:
    """Load the TSMC CAPEX event table; coerces ``event_date`` to datetime."""
    cfg = load_universe_config()
    path = resolve_path(cfg["manual_files"]["capex_events"])
    if not path.exists():
        raise FileNotFoundError(
            f"CAPEX events file missing: {path}. Run scripts/init_manual_data.py first."
        )
    df = pd.read_csv(path)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df.dropna(subset=["event_date"]).sort_values("event_date").reset_index(drop=True)
    return df


def load_institutional_flow() -> pd.DataFrame:
    """Load the daily institutional flow CSV; returns empty frame if absent."""
    path = resolve_path("data/manual/institutional_flow.csv")
    if not path.exists():
        logger.warning(
            "Institutional flow file missing: %s — run "
            "`python scripts/fetch_institutional_flow.py` to populate.",
            path,
        )
        return pd.DataFrame(
            columns=[
                "ticker",
                "date",
                "foreign_buy",
                "foreign_sell",
                "foreign_net",
                "trust_net",
                "dealer_net",
                "total_net",
            ]
        )
    df = pd.read_csv(path, dtype={"ticker": str})
    df["ticker"] = df["ticker"].str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"])


def load_valuation() -> pd.DataFrame:
    """Load daily PER / PBR / dividend yield CSV; returns empty frame if absent."""
    path = resolve_path("data/manual/valuation.csv")
    if not path.exists():
        logger.warning(
            "Valuation file missing: %s — run "
            "`python scripts/fetch_valuation.py` to populate.",
            path,
        )
        return pd.DataFrame(columns=["ticker", "date", "per", "pbr", "dividend_yield"])
    df = pd.read_csv(path, dtype={"ticker": str})
    df["ticker"] = df["ticker"].str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"])


def load_monthly_revenue() -> pd.DataFrame:
    """Load manual monthly revenue CSV; returns empty frame if absent."""
    cfg = load_universe_config()
    path = resolve_path(cfg["manual_files"]["monthly_revenue"])
    if not path.exists():
        logger.warning("Monthly revenue file missing: %s — returning empty frame.", path)
        return pd.DataFrame(
            columns=[
                "ticker",
                "company_name",
                "year_month",
                "revenue",
                "yoy_pct",
                "mom_pct",
                "source_url",
                "notes",
            ]
        )
    df = pd.read_csv(path, dtype={"ticker": str})
    df["ticker"] = df["ticker"].str.strip()
    df["year_month"] = pd.to_datetime(df["year_month"], format="%Y-%m", errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Price loader (yfinance + on-disk cache)
# ---------------------------------------------------------------------------

# Process-wide override so callers like run_daily_pipeline can force-skip
# refetch (e.g. ``--skip-fetch`` for offline / dev work) without threading
# the flag through every loader. ``None`` = use per-call default.
_CACHE_MAX_AGE_DAYS_OVERRIDE: int | None = None


def set_cache_max_age_override(days: int | None) -> None:
    """Set process-wide max cache age (in business days) for ``download_prices``.

    Pass ``None`` to clear. Pass a very large number (e.g. ``10**9``) to make
    the cache always considered fresh — i.e. the on-disk cache is the only
    source of truth for this process. Used by ``run_pipeline(skip_fetch=True)``.
    """
    global _CACHE_MAX_AGE_DAYS_OVERRIDE
    _CACHE_MAX_AGE_DAYS_OVERRIDE = days


def _cache_is_fresh(df: pd.DataFrame, max_age_business_days: int) -> bool:
    """True iff ``df``'s last index is within ``max_age_business_days`` of today.

    Uses business days so a Friday cache is still fresh on Monday.
    """
    if df is None or df.empty:
        return False
    last = pd.Timestamp(df.index.max()).normalize()
    today = pd.Timestamp.today().normalize()
    if last >= today:
        return True
    bdays = len(pd.bdate_range(last + pd.Timedelta(days=1), today))
    return bdays <= max_age_business_days


def _cache_path(ticker: str) -> Path:
    cfg = load_data_sources_config()
    base = ensure_dir(cfg["sources"]["yfinance"]["cache_dir"])
    safe = ticker.replace("/", "_").replace("^", "_idx_")
    return base / f"{safe}.parquet"


def _read_cache(ticker: str) -> pd.DataFrame | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001 - parquet engine missing → fall back
        logger.warning("Cache read failed for %s (%s); will re-fetch.", ticker, exc)
        return None


def _write_cache(ticker: str, df: pd.DataFrame) -> None:
    path = _cache_path(ticker)
    try:
        df.to_parquet(path)
    except Exception as exc:  # noqa: BLE001 - missing pyarrow/fastparquet
        # Fallback to CSV in same directory
        csv_path = path.with_suffix(".csv")
        df.to_csv(csv_path)
        logger.warning("Parquet write failed for %s (%s); wrote CSV: %s", ticker, exc, csv_path)


def download_prices(
    tickers: Iterable[str],
    start: str | None = None,
    end: str | None = None,
    use_cache: bool = True,
    max_cache_age_days: int = 1,
) -> dict[str, pd.DataFrame]:
    """Download adjusted OHLCV via yfinance; returns ``{ticker: DataFrame}``.

    Caching semantics:
    - ``use_cache=True`` → read cache when it is fresh (max age in business days
      controlled by ``max_cache_age_days``, default 1). If stale or missing,
      refetch from yfinance.
    - ``use_cache=False`` → always refetch.
    - The on-disk cache is **always** updated on a successful fetch, regardless
      of ``use_cache``, so a fresh fetch leaves the cache up-to-date for next time.
    - If a fetch fails (rate-limit, network error) and a stale cache exists, we
      fall back to the stale cache rather than dropping the ticker.
    - ``set_cache_max_age_override(N)`` overrides ``max_cache_age_days`` process-
      wide; use it to implement ``--skip-fetch``-style behavior at the runner
      layer without threading the flag through every caller.

    Missing or failing tickers (with no cache fallback) are reported via
    ``logger.warning`` and silently skipped — the caller gets only the
    successful ones, never a crash.
    """
    cfg = load_data_sources_config()["sources"]["yfinance"]
    if not cfg.get("enabled", True):
        logger.warning("yfinance source disabled in config; returning empty.")
        return {}

    start = start or cfg.get("history_start", "2018-01-01")
    end = end or cfg.get("history_end") or datetime.today().strftime("%Y-%m-%d")
    auto_adjust = bool(cfg.get("auto_adjust", True))

    try:
        import yfinance as yf  # imported lazily so the package imports without yfinance present
    except ImportError:
        logger.error("yfinance not installed. Run `pip install -r requirements.txt`.")
        return {}

    def _try_fetch(symbol: str) -> pd.DataFrame | None:
        try:
            df = yf.download(
                symbol,
                start=start,
                end=end,
                progress=False,
                auto_adjust=auto_adjust,
                threads=False,
            )
        except Exception as exc:  # noqa: BLE001 - yfinance raises a variety of errors
            logger.warning("yfinance download failed for %s: %s", symbol, exc)
            return None
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        return df

    def _fallback_symbols(symbol: str) -> list[str]:
        # Twin-suffix fallback: yfinance often serves Taiwan tickers under either
        # .TW (TWSE) or .TWO (TPEx) regardless of actual listing venue.
        if symbol.endswith(".TWO"):
            return [symbol[:-4] + ".TW"]
        if symbol.endswith(".TW"):
            return [symbol[:-3] + ".TWO"]
        return []

    eff_max_age = (
        _CACHE_MAX_AGE_DAYS_OVERRIDE
        if _CACHE_MAX_AGE_DAYS_OVERRIDE is not None
        else max_cache_age_days
    )

    out: dict[str, pd.DataFrame] = {}
    for raw_ticker in tickers:
        ticker = raw_ticker.strip()
        if not ticker:
            continue

        cached = _read_cache(ticker) if use_cache else None
        if (
            use_cache
            and cached is not None
            and not cached.empty
            and _cache_is_fresh(cached, eff_max_age)
        ):
            out[ticker] = cached
            continue

        df = _try_fetch(ticker)
        if df is None:
            for alt in _fallback_symbols(ticker):
                df = _try_fetch(alt)
                if df is not None:
                    logger.info("Resolved %s via fallback symbol %s", ticker, alt)
                    break
        if df is None:
            # Fetch failed; fall back to stale cache if we have one.
            if cached is not None and not cached.empty:
                logger.warning(
                    "Fetch failed for %s — using stale cache (last=%s).",
                    ticker, pd.Timestamp(cached.index.max()).date(),
                )
                out[ticker] = cached
            else:
                logger.warning("No data returned for %s — skipping.", ticker)
            continue

        # Always write cache on successful fetch, even when use_cache=False —
        # so next-run's cache is current.
        _write_cache(ticker, df)
        out[ticker] = df

    return out


def get_close_panel(
    tickers: Iterable[str],
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Return a wide ``Close`` price DataFrame indexed by date, columns by ticker."""
    raw = download_prices(tickers, start=start, end=end)
    series = {}
    for tkr, df in raw.items():
        if "Close" in df.columns:
            series[tkr] = df["Close"]
        elif "Adj Close" in df.columns:
            series[tkr] = df["Adj Close"]
    if not series:
        return pd.DataFrame()
    panel = pd.concat(series, axis=1).sort_index()
    panel.columns = list(series.keys())
    return panel
