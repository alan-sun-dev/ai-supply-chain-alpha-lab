"""Signal hierarchy — Tier definitions and gate logic.

Tier 1: Residual Alpha / Expectation Change
Tier 2: Fundamental Confirmation
Tier 3: Narrative Catalyst
Tier 4: Risk / Penalty

Decision rules (enforced in ``fusion.scoring_model_v2._resolve_decision_zone``).
History:
- A1 / A2: Strong required Tier 1 + Tier 2 both positive
- Gate-repair (2026-05-03): under Simplest Robust active baseline
  (rev_w = flw_w = 0), Tier 2 contributions are structurally zero so the
  old "tier2_positive" requirement made Strong always empty. Strong gate
  rewritten to use residual_alpha strength + risk_penalty cap directly.
  Avoid Chasing rewritten to require *actual* chasing risk indicators
  (overbought_flag OR valuation_extreme_flag) instead of the broken
  "tier2_revenue_confirmation <= 0" proxy.

``TierScores`` carries the new fields with safe defaults so that older
constructions (e.g. tests, callers from prior to the gate repair) keep
working without explicit values.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TierScores:
    tier1_residual_alpha: float
    tier2_revenue_confirmation: float
    tier2_institutional_flow: float
    tier3_narrative: float
    tier3_capex_context: float
    tier4_risk_severity: int  # 0..n integer; from risk_model.severity_score()

    # Gate-repair extensions (default-safe so older callers don't break).
    risk_penalty: float = 0.0                 # actual numeric penalty in alpha_score units
    overbought_flag: bool = False             # any "overbought" risk_flag fired
    valuation_extreme_flag: bool = False      # any "valuation_extreme" risk_flag fired
    residual_momentum_20d: float = 0.0        # for optional overheating check

    @property
    def tier1_positive(self) -> bool:
        return self.tier1_residual_alpha > 0

    @property
    def tier2_positive(self) -> bool:
        # Either of the two Tier-2 confirmations needs to be supportive.
        return self.tier2_revenue_confirmation > 0 or self.tier2_institutional_flow > 0

    @property
    def tier3_positive(self) -> bool:
        return self.tier3_narrative > 0 or self.tier3_capex_context > 0

    @property
    def tier4_blocking(self) -> bool:
        return self.tier4_risk_severity >= 6  # ~2 high flags or 1 critical

    @property
    def narrative_only(self) -> bool:
        return (
            self.tier3_positive
            and not self.tier1_positive
            and not self.tier2_positive
        )

    @property
    def is_chasing_setup(self) -> bool:
        """Gate-repair: actual chasing risk = (overbought OR valuation_extreme)
        AND high risk severity. Replaces the old tier2_revenue_confirmation
        proxy which broke under rev_w = 0."""
        return (self.overbought_flag or self.valuation_extreme_flag) and self.tier4_risk_severity >= 5
