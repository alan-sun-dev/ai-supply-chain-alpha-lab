"""Tests for fusion.scoring_model_v2 — gate logic + cap enforcement."""
from __future__ import annotations

import pandas as pd

from capex_alpha.fusion import scoring_model_v2 as sm
from capex_alpha.fusion.signal_hierarchy import TierScores
from capex_alpha.utils import load_yaml


def _cfg() -> dict:
    return load_yaml("config/alpha_model_v2.yaml")


def test_strong_candidate_requires_residual_alpha_strength():
    """Gate-repair: Strong requires residual_alpha >= min_residual_alpha (1.5).
    High top-line alpha alone is insufficient if residual contribution is weak."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=0.5,   # below 1.5 threshold
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=0,
        risk_penalty=0.5,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=4.5, confidence=3.0, cfg=cfg)
    assert zone != "Strong Candidate"


def test_strong_candidate_under_simplest_robust_no_tier2_required():
    """Gate-repair: Under Simplest Robust (rev=flw=0), Strong should still
    fire if alpha + residual_alpha + risk caps are met. Old gate required
    tier2_positive which made Strong structurally empty."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=2.5,    # above 1.5 threshold
        tier2_revenue_confirmation=0.0,   # zero — Simplest Robust
        tier2_institutional_flow=0.0,     # zero — Simplest Robust
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=2,            # below blocking threshold
        risk_penalty=1.0,                 # under cap (2.0)
        overbought_flag=False,
        valuation_extreme_flag=False,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=3.5, confidence=2.5, cfg=cfg)
    assert zone == "Strong Candidate", (
        f"Strong gate failed under Simplest Robust profile; got {zone}"
    )


def test_narrative_only_caps_at_narrative_watch():
    """Narrative supports it but Tier-1 / Tier-2 don't → Narrative Watch."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=0.0,
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=2.0,
        tier3_capex_context=0.5,
        tier4_risk_severity=0,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=1.0, confidence=2.0, cfg=cfg)
    assert zone == "Narrative Watch"


def test_high_risk_blocks_strong():
    """High tier4_blocking severity (≥6) blocks Strong; without overbought/
    valuation_extreme flags it falls to risk-blocked Watchlist (or Avoid Chasing
    only if a chasing flag is also present)."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=2.0,
        tier2_revenue_confirmation=1.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=8,
        risk_penalty=3.0,
        overbought_flag=False,
        valuation_extreme_flag=False,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=5.0, confidence=3.0, cfg=cfg)
    assert zone != "Strong Candidate"


def test_avoid_chasing_requires_actual_chasing_flag():
    """Gate-repair: Avoid Chasing must require overbought OR valuation_extreme
    + high severity. High severity alone (without those flags) should NOT
    trigger Avoid Chasing — old gate would have inflated this."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=2.0,
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=5,   # at chase threshold
        risk_penalty=1.5,
        overbought_flag=False,
        valuation_extreme_flag=False,   # ← no chasing flag
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=2.5, confidence=2.5, cfg=cfg)
    assert zone != "Avoid Chasing", (
        f"Avoid Chasing fired without chasing flag; got {zone}"
    )


def test_avoid_chasing_fires_when_overbought_with_severity():
    """Avoid Chasing must fire when overbought_flag + severity ≥ threshold (6)."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=3.0,
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=6,   # at chase threshold (recalibrated from 5 → 6)
        risk_penalty=1.5,
        overbought_flag=True,
        valuation_extreme_flag=False,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=3.5, confidence=2.5, cfg=cfg)
    assert zone == "Avoid Chasing"


def test_avoid_chasing_does_not_fire_at_severity_below_threshold():
    """Recalibration (2026-05-09): severity=5 is *below* the chase threshold
    even when overbought. The replay showed that severity=5 cohort behaves
    like Strong, not chasers, so they should pass through to Strong/Watchlist.
    """
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=3.0,
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=5,   # one below new threshold
        risk_penalty=1.5,
        overbought_flag=True,
        valuation_extreme_flag=False,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=3.5, confidence=2.5, cfg=cfg)
    assert zone != "Avoid Chasing", f"got {zone}"
    # With these tier scores it should land in Strong Candidate.
    assert zone == "Strong Candidate", f"got {zone}"


def test_avoid_chasing_fires_when_valuation_extreme_with_severity():
    """Avoid Chasing must also fire on valuation_extreme + high severity."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=3.0,
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=6,
        risk_penalty=1.5,
        overbought_flag=False,
        valuation_extreme_flag=True,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=3.5, confidence=2.5, cfg=cfg)
    assert zone == "Avoid Chasing"


def test_watchlist_requires_positive_residual_alpha():
    """Gate-repair: Watchlist now requires tier1_residual_alpha > 0 by default."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=-0.5,   # negative residual
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=2,
        risk_penalty=1.0,
        overbought_flag=False,
        valuation_extreme_flag=False,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=2.5, confidence=2.5, cfg=cfg)
    assert zone != "Watchlist"


def test_watchlist_excludes_excessive_risk_penalty():
    """Watchlist max_risk_penalty (default 4.0) caps risky names."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=1.0,
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=3,
        risk_penalty=5.0,            # above 4.0 cap
        overbought_flag=False,
        valuation_extreme_flag=False,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=2.5, confidence=2.5, cfg=cfg)
    assert zone != "Watchlist"


def test_strong_excludes_excessive_risk_penalty():
    """Strong max_risk_penalty (default 2.0) is tighter than Watchlist's."""
    cfg = _cfg()
    tiers = TierScores(
        tier1_residual_alpha=2.0,
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=3,
        risk_penalty=2.5,            # above Strong's 2.0 cap (but under Watchlist's 4.0)
        overbought_flag=False,
        valuation_extreme_flag=False,
    )
    zone, _ = sm._resolve_decision_zone(tiers, alpha=3.0, confidence=2.5, cfg=cfg)
    # Should fall to Watchlist (under that cap), not Strong
    assert zone == "Watchlist"


def test_capex_weight_is_zero_by_default():
    cfg = _cfg()["scoring_v2"]
    assert cfg["factor_weights"]["capex_context_score"] == 0.0


def test_a1_a2_factors_remain_zero():
    """A1 + A2 + A2-adopt invariants: sector_relative, narrative, revenue,
    institutional_flow tier weights all 0 in current active baseline."""
    cfg = _cfg()["scoring_v2"]
    # A1 invariants
    assert cfg["tier_weights"]["sector_relative_score"] == 0.0
    assert cfg["tier_weights"]["narrative_score"] == 0.0
    assert cfg["factor_weights"]["sector_relative_strength"] == 0.0
    # A2-adopt invariants (Simplest robust)
    assert cfg["tier_weights"]["revenue_confirmation_score"] == 0.0, (
        "A2-adopt: rev_w must be 0 (post-B3 ablation)"
    )
    assert cfg["tier_weights"]["institutional_flow_score"] == 0.0, (
        "A2-adopt: flw_w must be 0 (post-B3 ablation)"
    )
    # CAPEX still context-only — at most 0.05
    assert cfg["tier_weights"]["capex_context_score"] <= 0.05


def test_active_baseline_is_simplest_robust():
    """A2-adopt: active model is residual_alpha + risk_penalty + capex_context only."""
    tw = _cfg()["scoring_v2"]["tier_weights"]
    # Exactly 2 non-zero positive weights (residual_alpha + capex_context)
    nonzero = [k for k, v in tw.items() if v > 0]
    assert set(nonzero) == {"residual_alpha_score", "capex_context_score"}, (
        f"Expected only residual_alpha + capex_context positive; got {nonzero}"
    )
    assert tw["residual_alpha_score"] == 0.50


def test_risk_penalty_multiplier_yaml_field_present():
    """A2-adopt added scoring_v2.risk.penalty_multiplier; verify it's set."""
    cfg = _cfg()["scoring_v2"]
    assert "risk" in cfg
    assert "penalty_multiplier" in cfg["risk"]
    pm = cfg["risk"]["penalty_multiplier"]
    assert 0.0 < pm <= 2.0, f"penalty_multiplier {pm} outside sane range"


def test_risk_penalty_multiplier_actually_applied(monkeypatch, tmp_path):
    """Patch YAML so multiplier=0 → risk_penalty contribution should be 0;
    verify by comparing two runs with different multipliers."""
    from capex_alpha.fusion import scoring_model_v2 as sm
    from capex_alpha import utils

    # Run with default multiplier (current YAML = 0.75)
    out_default = sm.run(write=False)

    # Patch load_yaml to return a config with multiplier = 0
    real_load = utils.load_yaml
    def fake_load(path):
        cfg = real_load(path)
        if "alpha_model_v2" in str(path):
            cfg = {**cfg}
            cfg["scoring_v2"] = {**cfg["scoring_v2"]}
            cfg["scoring_v2"]["risk"] = {"penalty_multiplier": 0.0}
        return cfg
    # utils._CONFIG_CACHE caches; clear the cached entry first
    utils._CONFIG_CACHE.pop("config/alpha_model_v2.yaml", None)
    monkeypatch.setattr(utils, "load_yaml", fake_load)
    monkeypatch.setattr(sm, "load_yaml", fake_load)

    out_zero = sm.run(write=False)

    # With multiplier=0, every row's risk_penalty contribution must be 0
    assert (out_zero["risk_penalty"].fillna(0).abs() < 1e-9).all()
    # Default run had at least some non-zero risk penalties
    assert (out_default["risk_penalty"].fillna(0) != 0).any()


def test_decision_zone_thresholds_read_from_yaml():
    """_resolve_decision_zone must honour all YAML threshold fields, not
    hardcoded constants. Sets every custom threshold low so a modest profile
    qualifies for Strong only because of YAML, not gate logic."""
    custom_cfg = {
        "scoring_v2": {
            "decision_zones": [
                {"name": "Strong Candidate",
                 "min_alpha": 1.5, "min_confidence": 1.0,
                 "min_residual_alpha": 0.5, "max_risk_penalty": 5.0},
                {"name": "Watchlist",
                 "min_alpha": 0.5, "min_confidence": 0.5,
                 "max_risk_penalty": 10.0,
                 "require_residual_positive": True},
                {"name": "Avoid Chasing",
                 "require_overbought_or_valuation_extreme": True,
                 "min_risk_severity": 5},
            ]
        }
    }
    tiers = TierScores(
        tier1_residual_alpha=1.0,
        tier2_revenue_confirmation=0.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=0,
        risk_penalty=0.5,
    )
    # alpha=2.0 passes custom Strong (1.5); residual=1.0 passes custom (0.5);
    # confidence=2.0 passes custom (1.0); risk_penalty=0.5 passes custom (5.0).
    zone, _ = sm._resolve_decision_zone(tiers, alpha=2.0, confidence=2.0, cfg=custom_cfg)
    assert zone == "Strong Candidate"


def test_default_thresholds_when_yaml_missing():
    """Falls back to A1 defaults if YAML omits decision_zones."""
    empty_cfg: dict = {}
    tiers = TierScores(
        tier1_residual_alpha=1.0,
        tier2_revenue_confirmation=1.0,
        tier2_institutional_flow=0.0,
        tier3_narrative=0.0,
        tier3_capex_context=0.0,
        tier4_risk_severity=0,
    )
    # Default Strong min_alpha is 4.0; alpha=3.0 should NOT be Strong.
    zone, _ = sm._resolve_decision_zone(tiers, alpha=3.0, confidence=4.0, cfg=empty_cfg)
    assert zone != "Strong Candidate"


def test_run_smoke_outputs_alpha_ranking():
    out = sm.run(write=False)
    assert not out.empty
    assert "alpha_score" in out.columns
    assert "decision_zone" in out.columns
    # Capped: capex contribution column must be present and (default) zero
    assert (out["capex_context_score"].fillna(0).abs() <= 0.5).all()
