"""Tests for paper_portfolio MVP."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from capex_alpha import paper_portfolio as pp


def _toy_universe() -> pd.DataFrame:
    return pd.DataFrame([
        {"ticker": "AAA.TW", "company_name": "Big Co",   "theme": "thermal"},
        {"ticker": "BBB.TW", "company_name": "Mid Co",   "theme": "thermal"},
        {"ticker": "CCC.TW", "company_name": "Small Co", "theme": "optical_communication"},
        {"ticker": "DDD.TW", "company_name": "Tiny Co",  "theme": "memory_hbm"},
        {"ticker": "EEE.TW", "company_name": "Edge Co",  "theme": "passive_components"},
        {"ticker": "FFF.TW", "company_name": "Other",    "theme": "thermal"},
    ])


def _toy_ranking(date: pd.Timestamp) -> pd.DataFrame:
    universe = _toy_universe().assign(
        rebalance_date=date,
        alpha_score=[3.0, 2.5, 2.0, 1.5, 1.0, 0.5],
        residual_alpha_score=[2.0, 1.8, 1.5, 1.0, 0.8, 0.3],
        risk_penalty=[0.5, 0.3, 0.4, 0.2, 0.1, 0.1],
        decision_zone=["Watchlist"] * 6,
        fwd_return_1m=[0.05, -0.02, 0.04, 0.01, 0.00, -0.01],
    )
    return universe


def _toy_price_panel(idx: pd.DatetimeIndex) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    cols = ["AAA.TW", "BBB.TW", "CCC.TW", "DDD.TW", "EEE.TW", "FFF.TW", "0050.TW"]
    panel = pd.DataFrame(
        100.0 + rng.normal(0, 1, (len(idx), len(cols))).cumsum(axis=0),
        index=idx, columns=cols,
    )
    return panel


def test_compute_target_holdings_respects_theme_cap():
    """Top-5 with max_per_theme=2 should pick at most 2 thermal names."""
    theme_map = _toy_universe().set_index("ticker")["theme"].to_dict()
    ranking = _toy_ranking(pd.Timestamp("2024-01-31"))
    targets = pp.compute_target_holdings(ranking, theme_map, top_n=5, max_per_theme=2)
    # 3 thermal candidates exist (AAA, BBB, FFF); cap=2 → exactly 2 selected
    thermal_picks = targets[targets["theme"] == "thermal"]
    assert len(thermal_picks) == 2
    assert set(thermal_picks["ticker"]) == {"AAA.TW", "BBB.TW"}  # top alpha thermals
    assert len(targets) == 5
    assert targets["target_weight"].sum() == pytest.approx(1.0)


def test_estimate_one_way_cost_zero_when_no_change():
    new = {"A": 0.5, "B": 0.5}
    prev = {"A": 0.5, "B": 0.5}
    assert pp.estimate_one_way_cost(new, prev, 25.0) == pytest.approx(0.0)


def test_estimate_one_way_cost_full_redeploy():
    """Going from cash to fully invested = 100% one-way trade."""
    new = {"A": 0.5, "B": 0.5}
    prev = {}
    cost = pp.estimate_one_way_cost(new, prev, 25.0)
    # one_way_fraction = 0.5 * (0.5 + 0.5) = 0.5; cost = 0.5 * 25 / 10000 = 0.00125
    assert cost == pytest.approx(0.5 * 25 / 10000.0)


def test_estimate_one_way_cost_partial_rotation():
    """Rotate 1 of 2 names → 50% turnover."""
    new = {"A": 0.5, "C": 0.5}
    prev = {"A": 0.5, "B": 0.5}
    cost = pp.estimate_one_way_cost(new, prev, 25.0)
    # delta = |0|+|0.5|+|0.5| = 1.0; one-way = 0.5; cost = 0.5 * 25 / 10000
    assert cost == pytest.approx(0.5 * 25 / 10000.0)


def test_realized_period_return_handles_missing_ticker():
    panel = _toy_price_panel(pd.bdate_range("2024-01-01", "2024-12-31"))
    weights = {"AAA.TW": 0.5, "ZZZ.TW": 0.5}  # ZZZ not in panel
    ret = pp.realized_period_return(
        weights, pd.Timestamp("2024-02-29"),
        pd.Timestamp("2024-06-28"), panel,
    )
    # Should not crash; ZZZ contributes 0
    assert isinstance(ret, float)


def test_append_rebalance_initializes_nav_to_one():
    state = pp._empty_state()
    universe = _toy_universe()
    theme_map = universe.set_index("ticker")["theme"].to_dict()
    ranking = _toy_ranking(pd.Timestamp("2024-01-31"))
    targets = pp.compute_target_holdings(ranking, theme_map, top_n=5, max_per_theme=2)
    panel = _toy_price_panel(pd.bdate_range("2024-01-01", "2024-12-31"))
    state = pp.append_rebalance(
        state, pd.Timestamp("2024-01-31"), targets,
        price_panel=panel, benchmark_panel=panel[["0050.TW"]],
    )
    assert state.n_rebalances == 1
    row = state.log.iloc[0]
    assert row["nav_paper"] == pytest.approx(1.0)
    assert row["nav_benchmark"] == pytest.approx(1.0)
    assert row["period_return"] == 0.0  # no prior holdings → no period return
    assert row["base_turnover"] == pytest.approx(0.5)  # full deployment from cash


def test_append_two_rebalances_updates_nav():
    state = pp._empty_state()
    universe = _toy_universe()
    theme_map = universe.set_index("ticker")["theme"].to_dict()
    panel = _toy_price_panel(pd.bdate_range("2024-01-01", "2024-12-31"))

    # First rebalance
    r1 = _toy_ranking(pd.Timestamp("2024-01-31"))
    t1 = pp.compute_target_holdings(r1, theme_map, top_n=5, max_per_theme=2)
    state = pp.append_rebalance(
        state, pd.Timestamp("2024-01-31"), t1,
        price_panel=panel, benchmark_panel=panel[["0050.TW"]],
    )

    # Second rebalance — same ranking so same picks
    r2 = _toy_ranking(pd.Timestamp("2024-02-29"))
    t2 = pp.compute_target_holdings(r2, theme_map, top_n=5, max_per_theme=2)
    state = pp.append_rebalance(
        state, pd.Timestamp("2024-02-29"), t2,
        price_panel=panel, benchmark_panel=panel[["0050.TW"]],
    )

    assert state.n_rebalances == 2
    # Period return should be non-zero (prices moved)
    assert state.log.iloc[1]["period_return"] != 0.0
    # No churn: same picks both rebalances → turnover ≈ 0
    assert state.log.iloc[1]["base_turnover"] == pytest.approx(0.0)
    # NAV updated
    assert state.log.iloc[1]["nav_paper"] != 1.0


def test_overwrite_same_date_replaces_entry():
    state = pp._empty_state()
    universe = _toy_universe()
    theme_map = universe.set_index("ticker")["theme"].to_dict()
    panel = _toy_price_panel(pd.bdate_range("2024-01-01", "2024-12-31"))
    r1 = _toy_ranking(pd.Timestamp("2024-01-31"))
    t1 = pp.compute_target_holdings(r1, theme_map, top_n=5, max_per_theme=2)
    state = pp.append_rebalance(state, pd.Timestamp("2024-01-31"), t1, panel, panel[["0050.TW"]])
    # Re-run same date with same targets
    state = pp.append_rebalance(state, pd.Timestamp("2024-01-31"), t1, panel, panel[["0050.TW"]])
    # Should have just 1 entry (the second replaced the first)
    assert state.n_rebalances == 1
    n_rows = (state.portfolio["rebalance_date"] == pd.Timestamp("2024-01-31")).sum()
    assert n_rows == 5  # 5 holdings, not 10


def test_render_report_handles_empty_state():
    state = pp._empty_state()
    text = pp.render_report(state, output_path="reports/_test_paper_report.md")
    assert "no rebalance history yet" in text.lower()


def test_render_report_after_one_rebalance(tmp_path):
    state = pp._empty_state()
    universe = _toy_universe()
    theme_map = universe.set_index("ticker")["theme"].to_dict()
    panel = _toy_price_panel(pd.bdate_range("2024-01-01", "2024-12-31"))
    r1 = _toy_ranking(pd.Timestamp("2024-01-31"))
    t1 = pp.compute_target_holdings(r1, theme_map, top_n=5, max_per_theme=2)
    state = pp.append_rebalance(state, pd.Timestamp("2024-01-31"), t1, panel, panel[["0050.TW"]])
    out = tmp_path / "report.md"
    text = pp.render_report(state, output_path=str(out))
    assert "Paper Portfolio Report" in text
    assert "Current Holdings" in text
    assert "Theme Exposure" in text
    assert out.exists()
