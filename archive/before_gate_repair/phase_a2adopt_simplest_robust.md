# A2-adopt — Simplest Robust Active Baseline

_2026-05-03. Engineering baseline change. All numbers below are from the **actual scoring pipeline** (`scripts/run_walk_forward_v2.py` + `scripts/run_transaction_cost_test.py` + `scripts/run_universe_expansion_test.py` + `scripts/run_daily_pipeline.py`), not bucket proxies._

## What changed

| Field | Pre-adoption (Post-B3) | **A2-adopt (Simplest robust)** |
|---|---:|---:|
| `tier_weights.residual_alpha_score` | 0.35 | **0.50** |
| `tier_weights.revenue_confirmation_score` | 0.30 | **0.00** |
| `tier_weights.institutional_flow_score` | 0.10 | **0.00** |
| `tier_weights.sector_relative_score` | 0.00 | 0.00 _(unchanged)_ |
| `tier_weights.narrative_score` | 0.00 | 0.00 _(unchanged)_ |
| `tier_weights.capex_context_score` | 0.05 | 0.05 _(unchanged)_ |
| `risk.penalty_multiplier` | _(absent → 1.00)_ | **0.75** _(new YAML field)_ |

**Non-zero positive tier weights:** 4 → **2** (residual_alpha + capex_context).

**Code change**: `scoring_model_v2.py` reads `scoring_v2.risk.penalty_multiplier` from YAML (defaults to 1.0 if absent — backward compatible). Multiplied into the per-ticker `risk_penalty` after severity addition. Three new tests cover the field + multiplier + active baseline invariant.

The model is now effectively:
```
alpha_score = residual_alpha_score
            + 0.05 * capex_context_score        (always 0 in current data)
            - 0.75 * risk_penalty
```

Plus theme cap (max 2 per theme) at portfolio-construction step.

---

## Headline before / after (gross walk-forward, top-5 EW)

| Metric | Pre-adoption | **A2-adopt** | Δ | 0050.TW |
|---|---:|---:|---:|---:|
| **Sharpe (ann)** | 1.681 | **1.941** | **+0.260** | 1.275 |
| **Max DD** | -28.94% | **-25.70%** | **+3.24 pts** | -29.19% |
| Total return | +3,173% | **+10,891%** | +7,718 pts | +377% |
| Final NAV | 32.7 | **109.9** | 3.4× | 4.78 |
| Mean monthly | 5.79% | 7.78% | +1.99 pts | 2.47% |
| Monthly hit rate | 60.0% | 67.1% | +7.1 pts | 62.9% |

## Cost-aware results (B1 driver, top-5 EW)

| cost_bps | CAGR | Sharpe | Max DD | Final NAV | Net α vs 0050 | Cost drag/yr |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 114.4% | 1.92 | -24.3% | 85.5 | +83.7% | 0.00% |
| 10 | 112.9% | 1.90 | -24.5% | 82.1 | +82.2% | 0.74% |
| **25** | **110.7%** | **1.88** | -24.9% | 77.2 | **+79.9%** | 1.86% |
| **50** | **107.0%** | **1.84** | -25.4% | 69.7 | **+76.3%** | 3.72% |
| 100 | 99.8% | 1.76 | -26.6% | 56.7 | +69.1% | 7.44% |
| Benchmark 0050.TW | 30.2% | 1.28 | -29.2% | 4.78 | — | — |

**Break-even one-way cost: 689 bps** (was 478 bps under pre-adoption). Cost headroom up ~44%.

| | Pre-adopt | **A2-adopt** | Δ |
|---|---:|---:|---:|
| 25 bps net CAGR | 77.5% | **110.7%** | +33.2 pts |
| 50 bps net CAGR | 74.6% | **107.0%** | +32.4 pts |
| Avg monthly turnover | 58.0% | 62.0% | +4 pts (modestly higher) |
| Annualised turnover | 6.96× | 7.44× | +0.48× |
| Break-even cost | 478 bps | **689 bps** | +211 bps |

## Decision-zone hit rates — actual pipeline output

| Zone | Pre-adoption (n / unique / hit / mean) | **A2-adopt** | Δ |
|---|---|---|---:|
| Strong Candidate | 72 / 36 / 55.6% / +5.8% | **0 / 0 / — / —** | **structural empty** ⚠️ |
| **Watchlist** | 110 / 40 / 55.5% / +4.7% | **103 / 41 / 65.0% / +8.2%** | **+9.5 pts hit rate** ✅ |
| Neutral | 838 / 59 / 56.6% / +4.7% | 701 / 59 / 58.3% / +4.6% | +1.7 pts |
| Avoid Chasing | 13 / 11 / 53.8% / +11.1% | **195 / 51 / 58.5% / +7.4%** | sample 15× larger |
| Avoid | 3097 / 59 / 56.3% / +3.5% | 3131 / 59 / 55.4% / +3.3% | basically same |

### ⚠️ Structural side-effect: Strong Candidate became empty

**Why**: the Strong gate in `signal_hierarchy.py` requires `tier2_positive = (tier2_revenue_confirmation > 0) OR (tier2_institutional_flow > 0)`. With both `rev_w` and `flw_w` set to 0, both tier-2 contributions are always 0 → `tier2_positive` is always False → Strong gate never triggers.

This is **logically consistent** under the new weights: we explicitly removed Tier-2 confirmation as a concept, so Strong (which by design *requires* Tier-2 confirmation) has nothing to qualify on. **Watchlist becomes the new top tier** — and it is now significantly better-quality (65.0% hit rate, +8.2% mean fwd, n=103).

### ⚠️ Avoid Chasing gate inflated

The Avoid Chasing gate fires on `tier4_risk_severity ≥ 5 AND tier2_revenue_confirmation ≤ 0`. Under new weights, the second condition is structurally always true → the gate now catches every name with any meaningful risk flag. Sample grew 15× (13 → 195 obs).

**Mitigation**: Avoid Chasing names still have positive forward returns (+7.4% mean / 58.5% hit), so the gate is informative as a *risk-flagged-but-may-still-be-fine* tier. But the label "Avoid Chasing" is now misleading — it is no longer warning of a chasing trade, it is just flagging risk.

**This is an engineering-baseline cost**, accepted per user mandate ("only the required changes"). A future micro-change could relax the Avoid Chasing gate (e.g. drop `tier2_revenue_confirmation ≤ 0` requirement when `rev_w == 0`), but that is logic change beyond A2-adopt scope.

## Top-5 holdings behavior

Walk-forward turnover stats:
- Avg monthly one-way turnover: **62.0%** (3.1 of 5 names rotated per month, on average)
- Annualised: **7.44×**
- A1 baseline → Step-1 → A2-adopt progression: 5.28× → 6.65× → **7.44×** (each generation slightly higher; trade-off for more dynamic alpha capture)

Today's top-5 alpha names (2026-04-30 daily snapshot):

| rank | ticker | company | theme | alpha | conf | zone |
|---:|:--|:--|:--|---:|---:|:--|
| 1 | 3081.TWO | 聯亞 LandMark Optoelectronics | optical_communication | 2.18 | 2.5 | Avoid Chasing |
| 2 | 3583.TW | 辛耘 Sun Tech | semi_equipment | 1.56 | 3.5 | Avoid Chasing |
| 3 | 6187.TWO | 萬潤 Wan Run | semi_equipment | 1.25 | 3.5 | Avoid Chasing |
| 4 | 2383.TW | 台光電 Elite Material | pcb_substrate | 0.87 | 2.5 | Avoid Chasing |
| 5 | 6213.TW | 聯茂 ITEQ | pcb_substrate | 0.73 | 2.5 | Avoid Chasing |

Daily portfolio (top-5 by alpha) is well-diversified — 3 themes (optical, semi_equipment, pcb_substrate). All flagged Avoid Chasing (per gate inflation discussion above). Theme cap holds: 2 of 5 from pcb_substrate is at the cap.

## Theme concentration

Walk-forward (Phase C re-run):

| Universe variant | Top-5 conc | Max single-theme weight | Strong / Watchlist (post-adopt) |
|---|---:|---:|:--|
| original (= active expanded_liquid_60) | 8.5% | **40.0%** (cap holds) | 0 / N/A in grid |
| expanded_liquid_40 | 12.8% | 40.0% | 0 / N/A |
| **expanded_liquid_60** _(active)_ | 8.5% | **40.0%** | 0 / 103 in walk-forward |
| expanded_all_available | 6.5% | 40.0% | 0 / N/A |

Theme cap (max 2 per theme) binds the portfolio at 40% single-theme exposure. Theme exposure looks healthy and well-diversified.

## Risk flag distribution (current snapshot)

| Severity | Count |
|:--|---:|
| high | 64 |
| medium | 33 |
| **Total** | **97** |

| Risk flag type | Count |
|:--|---:|
| **valuation_extreme** | **58** ⚠️ |
| overbought | 27 |
| revenue_not_confirmed | 5 |
| excessive_drawdown | 4 |
| price_up_revenue_down | 3 |

**`valuation_extreme` dominates** (58 of 97 = 60% of all flags). This is the AI-mania regime making PER/PBR look stretched on most semiconductor names. The new `risk.penalty_multiplier=0.75` reduces its impact by ~25% — exactly the calibration the user mandated.

## Dashboard output check (2026-04-30 snapshot)

- ✅ Pipeline ran successfully end-to-end
- ✅ Regime classification unchanged: bullish / AI bullish / risk low; recommended gross exposure 100%
- ✅ Top-10 alpha candidates in JSON populated (theme-diversified)
- ✅ Risk warnings populated (10 names flagged, all with valuation_extreme or overbought)
- ⚠️ Watchlist count = 0 today (vs 1 yesterday under pre-adoption) — only #1 candidate (3081.TWO at 2.18) qualifies on alpha threshold but gets Avoid Chasing instead, per gate inflation
- ⚠️ Strong Candidate count = 0 (structural — see above)

The dashboard is **functional but the labels are noisy under new weights**. For research priority, the user should sort the `top_alpha_candidates` list by `alpha_score` directly (which works correctly), rather than rely on `decision_zone` labels (which need a follow-up micro-change to be informative under the new model).

---

## Honest caveats — the main one the user mandated

> **The new model is effectively `residual_alpha − 0.75 × risk_penalty`. This is acceptable for now, but it means the system is highly dependent on the residual alpha regime. If residual alpha stops working, the model will degrade quickly.**

Specifically:
- **~96% of the alpha signal** comes from the residual-alpha tier. The remaining ~4% is risk penalty (subtractive only) and capex context (always 0 in current data).
- **Single point of failure**: if the AI factor index becomes unrepresentative (e.g. AI rotation collapses, residual alpha ceases to reward winners over the AI beta benchmark), the entire model degrades simultaneously across all top-N picks.
- **No fundamental confirmation** — the model now ignores monthly revenue and institutional flow signals. We just spent Phase B3 to backfill that data, and the post-backfill validation said the data isn't predictive. Honest negative finding: either (a) the FinMind raw data isn't useful at this universe + horizon, or (b) our `revenue_acceleration` formula (`yoy[-3:].mean() − yoy[-6:-3].mean()`) is too crude. Future Phase D (or B4) could re-engineer revenue features rather than re-add the same factor at a different weight.
- **Decision-zone labels are now degraded**: Strong = always empty, Avoid Chasing = inflated, Watchlist = the only meaningful "good" tier. The portfolio works; the explanation layer needs a follow-up micro-change.
- **Test period is AI mania regime**. The 110.7% Net CAGR @ 25 bps is regime-conditional. In a non-AI-bull regime, residual-alpha-only would likely degrade more sharply than a multi-tier model would. The single-point-of-failure risk is most visible in the *next* regime, which we haven't tested.

## Tests

| Test | Status |
|---|---|
| `test_a1_a2_factors_remain_zero` (extended for A2-adopt) | ✅ |
| `test_active_baseline_is_simplest_robust` (new) | ✅ |
| `test_risk_penalty_multiplier_yaml_field_present` (new) | ✅ |
| `test_risk_penalty_multiplier_actually_applied` (new — patches YAML, runs scoring twice) | ✅ |
| `test_decision_zone_thresholds_read_from_yaml` (existing) | ✅ |
| Full repo: **68 / 68 passing** | ✅ |

## Files

**Modified (active code)**
- `config/alpha_model_v2.yaml` — new tier weights + new `scoring_v2.risk.penalty_multiplier=0.75` block
- `src/capex_alpha/fusion/scoring_model_v2.py` — read + apply `risk_mult` from YAML

**Tests**
- `tests/test_scoring_model_v2.py` — 4 new assertions (12 total tests)

**Snapshot**
- `archive/before_a2adopt/` — 25 files (full pre-adoption state including YAML)

**Refreshed outputs (under new active baseline)**
- `data/output/walk_forward_v2_*.csv`, `transaction_cost_*.csv`, `universe_expansion_*.csv`, `alpha_ranking.csv`, `dashboard_data.json`
- `reports/walk_forward_v2_summary.md`, `phase_b1_transaction_cost.md`, `phase_c_universe_expansion.md`, `daily_alpha_report.md` — auto-regenerated

---

## Summary judgement

Per user mandate ("simplicity, robustness, explainability, maintainability — not performance maximisation"):

| Criterion | Verdict |
|---|---|
| **Simpler** | ✅ 4 → 2 non-zero tier weights; ablation chains (no_revenue, no_flow) collapse to baseline |
| **More robust** | ✅ Sharpe +0.26, Max DD +3.24 pts, break-even +211 bps, all on actual scoring pipeline |
| **Explainable** | 🟡 Model itself is trivially explainable (residual α − 0.75 × risk); decision-zone labels degraded — needs follow-up |
| **Maintainable** | ✅ Risk multiplier now YAML-driven; tests guard the active-baseline invariants |
| Performance side-effect | 🟢 Net CAGR 77.5% → 110.7% at 25 bps. Honest disclosure: regime-conditional |

**Decision-zone follow-up needed (next phase, NOT now):**
- Adjust Strong gate to not require `tier2_positive` when `rev_w + flw_w == 0`
- Adjust Avoid Chasing gate similarly
- Either change should be guarded by a small YAML toggle so we can A/B verify

## Next-step pre-conditions before daily auto-scheduling

Per user: "After this change, we still need one more validation pass before moving toward dashboard scheduling or paper portfolio."

The remaining gates I see:
1. **Decision-zone label fix** — the labels are misleading under new weights
2. **Out-of-regime stress test** — current backtest is dominated by AI bull. Need either a non-AI sub-period analysis or a synthetic stress simulation (e.g. cap residual_alpha contribution and see if the strategy survives)
3. **Phase D portfolio construction** — max position size, vol targeting, stop-loss
4. **Live paper portfolio** — 1-3 month run to capture intraday execution realities not in the backtest

Daily auto-scheduling should follow only after at least #1 and #2. **NOT recommended now.**
