"""Tests for validation.cluster_cap (Phase D2)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha.validation import cluster_cap as cc


def _toy_df():
    """5 cluster names + 3 non-cluster names, alpha decreasing."""
    rows = []
    for date in pd.date_range("2024-01-31", periods=2, freq="ME"):
        for i, (ticker, theme) in enumerate([
            ("PCB1", "pcb_substrate"),         # alpha highest in cluster
            ("PCB2", "pcb_substrate"),
            ("LEO1", "leo_satellite"),
            ("FAC1", "facility_cleanroom"),
            ("THM1", "thermal"),
            ("OPT1", "optical_communication"), # non-cluster
            ("MEM1", "memory_hbm"),
            ("PSV1", "passive_components"),
        ]):
            rows.append({
                "rebalance_date": date,
                "ticker":         ticker,
                "alpha_score":    8 - i + (0.1 if date.month == 2 else 0),
                "fwd_return_1m":  0.05,
            })
    return pd.DataFrame(rows)


def _toy_theme_map():
    return {
        "PCB1": "pcb_substrate", "PCB2": "pcb_substrate",
        "LEO1": "leo_satellite", "FAC1": "facility_cleanroom",
        "THM1": "thermal",       "OPT1": "optical_communication",
        "MEM1": "memory_hbm",    "PSV1": "passive_components",
    }


def test_cap_pct_to_count_uses_round():
    assert cc.cap_pct_to_count(0.50, 5) == 2  # round(2.5) → 2 (banker's)
    assert cc.cap_pct_to_count(0.60, 5) == 3
    assert cc.cap_pct_to_count(0.70, 5) == 4  # round(3.5) → 4 (banker's rounds to even, but Python rounds half-to-even → 4 here is actually round(3.5) = 4? In Python round(3.5) = 4)


def test_cluster_cap_excludes_extra_cluster_names():
    """With max_cluster_count=2, top-5 should pull at most 2 cluster names + 3 non-cluster."""
    df = _toy_df()
    theme_map = _toy_theme_map()
    holdings = cc.topn_holdings_with_cluster_cap(
        df, n=5, theme_map=theme_map, max_per_theme=2,
        cluster_themes=cc.CLUSTER_THEMES_DEFAULT, max_cluster_count=2,
    )
    # Top alpha is PCB1 (cluster); per-theme cap=2 keeps PCB1+PCB2 at most 2 PCB.
    # Cluster cap=2 means total cluster ≤ 2.  So picks should be:
    #   PCB1, PCB2 (2 cluster from PCB; per-theme cap binds first), then 3 non-cluster.
    # But wait: PCB1+PCB2=2 cluster names already, so LEO1/FAC1/THM1 are excluded.
    # Remaining 3 slots filled with OPT1, MEM1, PSV1.
    for date, picks in holdings.items():
        cluster_count = sum(1 for t in picks if theme_map[t] in cc.CLUSTER_THEMES_DEFAULT)
        assert cluster_count <= 2
        assert len(picks) == 5


def test_cluster_cap_at_3_allows_three_cluster():
    df = _toy_df()
    theme_map = _toy_theme_map()
    holdings = cc.topn_holdings_with_cluster_cap(
        df, n=5, theme_map=theme_map, max_per_theme=2,
        cluster_themes=cc.CLUSTER_THEMES_DEFAULT, max_cluster_count=3,
    )
    for date, picks in holdings.items():
        cluster_count = sum(1 for t in picks if theme_map[t] in cc.CLUSTER_THEMES_DEFAULT)
        assert cluster_count <= 3


def test_baseline_no_cluster_cap_pulls_all_top_alpha():
    """No cluster cap → pulls 5 highest alpha (subject only to per-theme cap)."""
    df = _toy_df()
    theme_map = _toy_theme_map()
    holdings = cc.topn_holdings_with_cluster_cap(
        df, n=5, theme_map=theme_map, max_per_theme=2,
        cluster_themes=None, max_cluster_count=None,
    )
    # No cluster cap: top 5 by alpha respecting per-theme cap (PCB1+PCB2 max).
    # PCB1, PCB2 (PCB cap = 2), then LEO1, FAC1, THM1 (3 more cluster from different themes).
    for date, picks in holdings.items():
        assert "PCB1" in picks
        assert "PCB2" in picks
        assert len(picks) == 5


def test_cluster_exposure_path_correct_share():
    holdings = {
        pd.Timestamp("2024-01-31"): ["PCB1", "PCB2", "LEO1", "OPT1", "MEM1"],
        pd.Timestamp("2024-02-29"): ["OPT1", "MEM1", "PSV1", "PCB1", "FAC1"],
    }
    theme_map = _toy_theme_map()
    path = cc.cluster_exposure_path(holdings, theme_map)
    assert path.loc[pd.Timestamp("2024-01-31"), "cluster_count"] == 3   # PCB1, PCB2, LEO1
    assert path.loc[pd.Timestamp("2024-01-31"), "cluster_weight"] == pytest.approx(0.6)
    assert path.loc[pd.Timestamp("2024-02-29"), "cluster_count"] == 2   # PCB1, FAC1
    assert path.loc[pd.Timestamp("2024-02-29"), "cluster_weight"] == pytest.approx(0.4)


def test_upside_sacrifice_zero_when_no_momentum_months():
    """If AI index never crosses threshold, n_months should be 0."""
    rets = pd.Series([0.05, 0.05], index=pd.date_range("2024-01-31", periods=2, freq="ME"))
    ai = pd.Series([0.01, 0.01], index=rets.index)
    out = cc.upside_sacrifice(rets, rets, ai, momentum_threshold=0.10)
    assert out["n_months"] == 0


def test_upside_sacrifice_records_difference():
    rets_base = pd.Series([0.10, 0.20, 0.05],
                          index=pd.date_range("2024-01-31", periods=3, freq="ME"))
    rets_capped = pd.Series([0.06, 0.12, 0.05],
                            index=rets_base.index)
    ai = pd.Series([0.08, 0.10, 0.02], index=rets_base.index)
    out = cc.upside_sacrifice(rets_base, rets_capped, ai, momentum_threshold=0.05)
    # Months with AI > 5%: month 1 (0.08) and month 2 (0.10)
    assert out["n_months"] == 2
    # Sacrifice = (0.10+0.20)/2 - (0.06+0.12)/2 = 0.15 - 0.09 = 0.06
    assert out["sacrifice_per_month"] == pytest.approx(0.06)
