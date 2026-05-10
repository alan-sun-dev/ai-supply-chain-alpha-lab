"""Tests for Phase C universe expansion + validation."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha import universe_expansion as ue
from capex_alpha.validation import universe_validation as uv


# ---------------------------------------------------------------------------
# Candidate dedup

def test_candidate_dedup_keeps_first_theme(tmp_path):
    """When the same ticker appears under two themes, keep the first row."""
    csv = tmp_path / "candidates.csv"
    csv.write_text(
        "ticker,company_name,market,theme,sub_theme,benefit_logic,confidence_level,notes\n"
        "2313.TW,華通,TWSE,pcb_substrate,server PCB,a,medium,first\n"
        "2313.TW,華通,TWSE,leo_satellite,sat PCB,b,medium,duplicate\n"
        "3017.TW,奇鋐,TWSE,thermal,liquid cooling,c,high,first\n"
    )
    df = ue.load_candidates(str(csv))
    assert len(df) == 2
    assert df.loc[df["ticker"] == "2313.TW", "theme"].iloc[0] == "pcb_substrate"
    assert df.loc[df["ticker"] == "2313.TW", "notes"].iloc[0] == "first"


# ---------------------------------------------------------------------------
# Liquidity stats

def _fake_price_panel(close: list[float], volume: list[float]) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-01", periods=len(close))
    return pd.DataFrame({"Close": close, "Volume": volume}, index=idx)


def test_liquidity_stats_with_full_data():
    df = _fake_price_panel([100.0] * 60, [10000.0] * 60)
    s = ue._compute_stats_for_ticker(df, lookback=60)
    assert s.avg_daily_value_60d == pytest.approx(100.0 * 10000.0)
    assert s.avg_volume_60d == pytest.approx(10000.0)
    assert s.missing_data_ratio == pytest.approx(0.0)
    assert s.n_obs == 60


def test_liquidity_stats_handles_missing_data():
    df = _fake_price_panel([np.nan] * 30 + [100.0] * 30, [10000.0] * 60)
    s = ue._compute_stats_for_ticker(df, lookback=60)
    assert s.missing_data_ratio == pytest.approx(0.5)
    assert s.avg_volume_60d == pytest.approx(10000.0)


def test_liquidity_stats_no_data():
    s = ue._compute_stats_for_ticker(None)
    assert s.n_obs == 0
    assert s.missing_data_ratio == 1.0
    assert np.isnan(s.avg_daily_value_60d)


# ---------------------------------------------------------------------------
# Filter

def test_apply_liquidity_filter_drops_low_adv():
    """ADV below threshold → excluded with reason; issuer always kept."""
    candidates = pd.DataFrame([
        {"ticker": "AAA", "company_name": "Big",   "theme": "x"},
        {"ticker": "BBB", "company_name": "Small", "theme": "y"},
        {"ticker": "CCC", "company_name": "None",  "theme": "z"},
        {"ticker": "DDD", "company_name": "Issuer","theme": "indirect"},
    ])
    liquidity = pd.DataFrame([
        {"ticker": "AAA", "company_name": "Big",   "theme": "x", "avg_daily_value_60d": 1e9, "avg_volume_60d": 1e6, "missing_data_ratio": 0.0, "n_obs": 60, "last_date": pd.Timestamp("2024-01-01"), "liquidity_tier": "A", "data_available": True},
        {"ticker": "BBB", "company_name": "Small", "theme": "y", "avg_daily_value_60d": 1e6, "avg_volume_60d": 1e3, "missing_data_ratio": 0.0, "n_obs": 60, "last_date": pd.Timestamp("2024-01-01"), "liquidity_tier": "C", "data_available": True},
        {"ticker": "CCC", "company_name": "None",  "theme": "z", "avg_daily_value_60d": np.nan,"avg_volume_60d": np.nan,"missing_data_ratio": 1.0, "n_obs": 0,  "last_date": None,                  "liquidity_tier": "X", "data_available": False},
        {"ticker": "DDD", "company_name": "Issuer","theme": "indirect","avg_daily_value_60d": np.nan,"avg_volume_60d": np.nan,"missing_data_ratio": 1.0,"n_obs":0,"last_date": None,"liquidity_tier":"X","data_available": False},
    ])
    out = ue.apply_liquidity_filter(candidates, liquidity, min_adv=30_000_000,
                                    keep_required=["DDD"])
    out = out.set_index("ticker")
    assert out.loc["AAA", "include_final"] == True
    assert out.loc["BBB", "include_final"] == False
    assert "adv_below" in out.loc["BBB", "exclude_reason"]
    assert out.loc["CCC", "include_final"] == False
    assert out.loc["CCC", "exclude_reason"] == "no_data"
    assert out.loc["DDD", "include_final"] == True   # issuer override
    assert out.loc["DDD", "exclude_reason"] == "always_keep"


# ---------------------------------------------------------------------------
# Builder caps

def _toy_universe_pair(n_stocks: int):
    """Make matching candidate + liquidity rows that all pass the filter."""
    candidates = pd.DataFrame({
        "ticker":       [f"T{i:02d}.TW" for i in range(n_stocks)],
        "company_name": [f"C{i:02d}" for i in range(n_stocks)],
        "theme":        ["facility_cleanroom"] * n_stocks,
    })
    liquidity = pd.DataFrame({
        "ticker":       candidates["ticker"],
        "company_name": candidates["company_name"],
        "theme":        candidates["theme"],
        "avg_daily_value_60d": np.linspace(1e9, 1e8, n_stocks),  # decreasing
        "avg_volume_60d":      [1e6] * n_stocks,
        "missing_data_ratio":  [0.0] * n_stocks,
        "n_obs":               [60] * n_stocks,
        "last_date":           [pd.Timestamp("2024-01-01")] * n_stocks,
        "liquidity_tier":      ["A"] * n_stocks,
        "data_available":      [True] * n_stocks,
    })
    return candidates, liquidity


def test_expanded_liquid_40_capped_at_40():
    cands, liq = _toy_universe_pair(80)
    out = ue.build_expanded_universes(cands, liq, write=False)
    assert len(out["expanded_liquid_40"]) <= 40
    assert len(out["expanded_liquid_40"]) == 40  # exactly 40 since 80 pass filter


def test_expanded_liquid_60_capped_at_60():
    cands, liq = _toy_universe_pair(80)
    out = ue.build_expanded_universes(cands, liq, write=False)
    assert len(out["expanded_liquid_60"]) <= 60
    assert len(out["expanded_liquid_60"]) == 60


def test_expanded_liquid_40_picks_most_liquid():
    cands, liq = _toy_universe_pair(50)
    out = ue.build_expanded_universes(cands, liq, write=False)
    # Most liquid 40 should be tickers T00..T39 (we set ADV decreasing with index)
    expected = {f"T{i:02d}.TW" for i in range(40)}
    actual = set(out["expanded_liquid_40"]["ticker"])
    assert actual == expected


# ---------------------------------------------------------------------------
# Validation analytics

def _toy_walk_forward_results(n_dates: int = 12, themes: dict | None = None):
    rng = np.random.default_rng(0)
    themes = themes or {f"T{i:02d}": "facility_cleanroom" for i in range(8)}
    dates = pd.bdate_range("2024-01-31", periods=n_dates, freq="ME")
    rows = []
    for d in dates:
        for j, t in enumerate(themes):
            rows.append({
                "rebalance_date": d,
                "ticker":         t,
                "alpha_score":    (len(themes) - j) + rng.normal(0, 0.3),
                "fwd_return_1m":  rng.normal(0.02, 0.04),
                "decision_zone":  "Strong Candidate" if j == 0 else "Avoid",
                "confidence_score": 4.0,
            })
    df = pd.DataFrame(rows)
    universe = pd.DataFrame({"ticker": list(themes), "theme": list(themes.values()),
                             "company_name": list(themes)})
    return df, universe


def test_theme_exposure_sum_to_one():
    df, universe = _toy_walk_forward_results()
    theme_exp = uv.theme_exposure_per_rebalance(df, universe, n=5)
    assert not theme_exp.empty
    sums = theme_exp.groupby("date")["weight"].sum()
    np.testing.assert_array_almost_equal(sums.values, np.ones_like(sums.values), decimal=6)


def test_label_stats_schema():
    df, _ = _toy_walk_forward_results()
    stats = uv.label_stats(df)
    expected = {"decision_zone", "n_obs", "n_unique_tickers", "hit_rate",
                "mean_forward_1m_return", "median_forward_1m_return",
                "avg_alpha_score", "avg_confidence_score"}
    assert expected.issubset(set(stats.columns))


def test_concentration_metrics_returns_correct_unique_count():
    df, _ = _toy_walk_forward_results(n_dates=4)
    conc = uv.concentration_metrics(df, n=3)
    # Top-3 picks are deterministic (T00, T01, T02 each rebalance)
    assert conc["unique_holdings_count"] == 3
    # 8 tickers in the synthetic universe → top-3 / 8 = 0.375
    assert conc["top5_concentration"] == pytest.approx(3 / 8)


# ---------------------------------------------------------------------------
# Theme cap (Step-1)

def test_theme_cap_limits_per_theme():
    """Greedy top-N respects max_per_theme."""
    from capex_alpha.validation import portfolio_metrics as pm
    # 6 tickers, all same theme → cap=2 should only pick 2
    df = pd.DataFrame([
        {"rebalance_date": pd.Timestamp("2024-01-31"), "ticker": f"T{i}",
         "alpha_score": 10 - i, "fwd_return_1m": 0.01}
        for i in range(6)
    ])
    theme_map = {f"T{i}": "thermal" for i in range(6)}
    holdings = pm.topn_holdings(df, n=5, theme_map=theme_map, max_per_theme=2)
    # 6 candidates, all thermal, cap 2 → can't fill 5 slots → empty
    assert holdings == {}

    # Mixed themes — 3 thermal, 3 optical, cap 2 → top-5 = 2 thermal + 2 optical = 4 only → empty
    theme_map_mixed = {f"T{i}": ("thermal" if i < 3 else "optical") for i in range(6)}
    holdings = pm.topn_holdings(df, n=4, theme_map=theme_map_mixed, max_per_theme=2)
    # Exactly 4 picks: T0, T1 (thermal), T3, T4 (optical) — T2 skipped (3rd thermal), T5 not needed
    assert pd.Timestamp("2024-01-31") in holdings
    picks = holdings[pd.Timestamp("2024-01-31")]
    assert len(picks) == 4
    assert picks.count("T0") + picks.count("T1") + picks.count("T2") <= 2  # at most 2 thermal


def test_theme_cap_disabled_returns_pure_topn():
    """When theme_map or cap is None, behaves as plain topn."""
    from capex_alpha.validation import portfolio_metrics as pm
    df = pd.DataFrame([
        {"rebalance_date": pd.Timestamp("2024-01-31"), "ticker": f"T{i}",
         "alpha_score": 10 - i, "fwd_return_1m": 0.01}
        for i in range(8)
    ])
    holdings = pm.topn_holdings(df, n=5)
    assert holdings[pd.Timestamp("2024-01-31")] == ["T0", "T1", "T2", "T3", "T4"]


def test_theme_cap_kwargs_reads_yaml():
    """Step-1: theme_cap_kwargs reads enable_theme_cap + max_per_theme from YAML."""
    from capex_alpha.validation import portfolio_metrics as pm
    cfg = pm.load_theme_cap_config()
    assert "enable_theme_cap" in cfg
    assert "max_per_theme" in cfg
    # Smoke: kwargs honor enable_theme_cap
    theme_map = {"AAA": "x"}
    kwargs = pm.theme_cap_kwargs(theme_map)
    if cfg["enable_theme_cap"]:
        assert kwargs["max_per_theme"] == cfg["max_per_theme"]
        assert kwargs["theme_map"] is theme_map
    else:
        assert kwargs["theme_map"] is None
