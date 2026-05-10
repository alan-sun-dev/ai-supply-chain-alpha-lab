# Decision-Zone Gate Recalibration (post Gate-Repair)

_2026-05-09. Follow-up to `phase_gate_repair.md` (2026-05-03). One YAML threshold changed (`Avoid Chasing.min_risk_severity: 5 → 6`) plus one new ablation lens added (`gate_attribution`). No model weights, no factors, no scoring formula touched. Walk-forward 2020-06-30 → 2026-04-30, 71 monthly rebalances, 60 universe tickers (`expanded_liquid_60`)._

## TL;DR

The Gate-Repair set Avoid Chasing's threshold at `severity ≥ 5`. Replaying the walk-forward through the gates revealed that the **boundary cohort (severity = exactly 5) was misclassified** — it behaves like Strong, not like a chasing trap. Raising the threshold to 6 corrects the classification and aligns it with `tier4_blocking`.

A first-pass simulation suggested portfolio Sharpe would lift 1.86 → 2.04. **An apples-to-apples re-run rejected that claim**: when same-month coverage is held constant, the real Δ Sharpe is +0.012. The gain was almost entirely a coverage artifact from the production "skip months with <5 eligible names" rule. The change is kept on **structural-correctness grounds, not portfolio-performance grounds**.

The new `gate_attribution` lens makes this kind of self-correction reproducible from now on.

---

## What changed

| Component | Before | After |
|---|---|---|
| `config/alpha_model_v2.yaml` `Avoid Chasing.min_risk_severity` | `5` | **`6`** (matches `tier4_blocking`) |
| `src/capex_alpha/validation/ablation.py` | `_topn_portfolio` (no zone awareness) | + `_topn_portfolio_zone_filtered`, + `gate_attribution(df)` returning 3-row frame |
| `src/capex_alpha/validation/validation_report.py` | 6 sections | 7 sections — new **§6 Gate-Filtered Top-5 Portfolio** with apples-to-apples row |
| `scripts/run_walk_forward_v2.py` | prints 4 tables | prints 5 tables (adds `GATE ATTRIBUTION`) |
| Outputs | `walk_forward_v2_{ablation,decision_zone,decile,risk_attribution,narrative_attribution}.csv` | + `walk_forward_v2_gate_attribution.csv` |

**Strict invariants honored:**
- ✅ No model weights changed
- ✅ No new factors
- ✅ No alpha-scoring formula change
- ✅ Active baseline unchanged (`ra=0.50, rev=0, flw=0, sec=0, narr=0, capex=0.05, risk_mult=0.75`)
- ✅ All thresholds YAML-driven
- ✅ Backwards compatible (older YAML without the new severity field falls through `_zone_threshold` default)

---

## Finding 1 — severity-5 cohort is misclassified

Replayed all 4189 walk-forward observations through `_resolve_decision_zone` with the chase severity threshold swept from 5 to 99 (off):

| sev≥ | Strong n | Strong mean fwd-1m | Strong hit | Avoid Chasing n | Chasing mean fwd-1m |
|:-:|-:|-:|-:|-:|-:|
| 5 (old) | 67 | +9.68% | 62.7% | 183 | +7.83% |
| **6 (new)** | **81** | **+9.49%** | **63.0%** | **126** | **+7.93%** |
| 7 | 81 | +9.49% | 63.0% | 73 | +4.57% |
| 99 (off) | 81 | +9.49% | 63.0% | 0 | — |

The 14 observations that move from Avoid Chasing → {Strong, Watchlist, Neutral} when threshold goes 5 → 6 all sit at `severity = exactly 5`. Their forward-1m profile:

- mean +8.58%, hit rate 64.3%
- spread across 2020-2025, 11 distinct (date, ticker)
- alpha_score 3.0–4.4, residual 4.4–6.1 — i.e. **the highest-conviction names in the universe**

Indistinguishable from the existing Strong cohort (+9.7%, 63%). They are not chasers.

## Finding 2 — Strong-empty months reduce 35 → 29

Of 71 rebalances:

| | Months with 0 Strong | Months with ≥1 Strong |
|---|---:|---:|
| sev≥5 (old) | 35 (49%) | 36 |
| **sev≥6 (new)** | **29 (41%)** | **42** |

Six months that previously had no research candidate now have at least one. Strong dates with rerouted names: 2021-02, 2021-11, 2024-09, 2024-10, 2025-01, 2025-08.

## Finding 3 — `max_risk_penalty` for Strong is dead code

Sweeping the cap from 1.5 → 99.0 produced **zero** effect on which rows pass. Reason: among rows passing all other Strong gates (n=81), the empirical risk_penalty distribution is

| stat | value |
|---|---:|
| median | 0.79 |
| 90%-ile | 1.57 |
| 99%-ile | 1.77 |
| max | 1.78 |

The 2.0 cap from Gate-Repair never binds. The Avoid-Chasing gate eats high-RP cases first, leaving only low-RP candidates for Strong. **Not removed in this phase** (it's still load-bearing as documentation of intent), but flagged here so a future maintainer doesn't assume it's calibrated to the data.

---

## Finding 4 — the corrected Sharpe story

This is the centerpiece, and it overturns the original recommendation.

### First-pass claim (overstated)

Using a loose ad-hoc top-5 simulation that allowed `groupby().head(5)` (taking whatever was available, even if a month had only 2 eligible names after zone filtering):

| | sev=5 | sev=6 | Δ |
|---|---:|---:|---:|
| Sharpe | 1.86 | 2.04 | +0.18 |
| Total return | 7,623% | 13,165% | +5,542 pp |
| MaxDD | -33.6% | -21.8% | +11.8 pp |

This is what was reported when proposing the change.

### Production-rule re-run

Production's `_topn_portfolio` skips a rebalance month entirely if fewer than 5 names are eligible after the zone filter. Re-running with that rule on the new sev=6 walk-forward output:

| Variant | n_months | mean_m | Sharpe | maxDD | Total |
|---|-:|-:|-:|-:|-:|
| `top5_by_alpha` (no filter) | 70 | 7.8% | 1.941 | -25.7% | 10,990% |
| `top5_zone_filtered` | 58 | 8.2% | 2.128 | -21.8% | 6,269% |

The zone-filtered Sharpe (2.13) does beat unfiltered (1.94) — but the comparison is contaminated because they use **different month sets**. 12 months are skipped by the filtered variant (universe too thin after dropping Avoid + Avoid Chasing). The 12 missing months break compounding, so total return looks worse even though Sharpe looks better.

### Apples-to-apples (same 58 months)

Added `top5_by_alpha_aligned` — the unfiltered top-5 restricted to the 58 months in which the filtered variant has data:

| Variant | n_months | mean_m | Sharpe | maxDD | Total |
|---|-:|-:|-:|-:|-:|
| `top5_zone_filtered` | 58 | 8.2% | 2.128 | -21.8% | 6,269% |
| `top5_by_alpha_aligned` | 58 | 8.5% | 2.115 | -23.3% | 7,127% |
| **Δ (filter effect)** | **0** | **-0.3 pp** | **+0.012** | **+1.5 pp** | **-858 pp** |

The actual marginal contribution of the zone filter is **+0.012 Sharpe** — within noise. MaxDD is slightly better (+1.5 pp), total return is slightly worse. Mean monthly return is fractionally lower.

**Conclusion**: the gate-filter, in isolation, adds essentially zero portfolio alpha. The first-pass +0.18 Sharpe number was almost entirely a sample-selection artifact — sev=6 reduced the count of <5-eligible months from 13 to 12, recovering 3 months of compounding, and that coverage gain dominated everything else.

This finding is consistent with the existing README §6 ablation result that `residual_alpha_only` matches `full` model performance. The decision_zone machinery is **dashboard interpretability**, not portfolio alpha.

---

## What still justifies the sev=5 → 6 change

The recalibration is kept on three structural grounds:

1. **Classification correctness.** The severity-5 boundary cohort (n=14) had +8.6% mean fwd-1m / 64% hit. Calling those "chasers" is a labeling error.
2. **Threshold consistency.** `tier4_blocking` (the existing critical-risk gate that overrides Strong) fires at severity ≥ 6. Avoid Chasing now matches.
3. **Human usability.** 6 fewer Strong-empty months means the dashboard shows ≥1 research candidate in 42/71 months instead of 36/71.

Sharpe-improvement claims were wrong and are retracted from the YAML comment block (commit replaces "lifts top-5 Sharpe 1.86 → 2.04, MaxDD -34% → -22%" with the apples-to-apples Δ +0.012).

---

## Files modified

**Active code**
- `config/alpha_model_v2.yaml` — `Avoid Chasing.min_risk_severity: 5 → 6` + honest two-section comment block citing this report
- `src/capex_alpha/validation/ablation.py` — `Iterable` import; `_topn_portfolio_zone_filtered` helper; `gate_attribution` function returning 3-row frame; wired into `write_outputs`
- `src/capex_alpha/validation/validation_report.py` — `gate_attr` parameter on `render`; new §6 with verdict line that compares apples-to-apples; old §6 Caveats becomes §7
- `scripts/run_walk_forward_v2.py` — passes `gate_attr` to `render`; prints `GATE ATTRIBUTION` table on console

**Refreshed outputs**
- `data/output/walk_forward_v2_results.csv` — re-run; 57 rows reclassify zone (14 → Strong, 8 → Watchlist, 35 → Neutral)
- `data/output/walk_forward_v2_decision_zone.csv` — refreshed counts
- `data/output/walk_forward_v2_gate_attribution.csv` — **new**
- `reports/walk_forward_v2_summary.md` — refreshed with new §6

**Snapshot (pre-change backup)**
- `/tmp/wf_summary_pre_sev6.md`, `/tmp/wf_results_pre_sev6.csv`, `/tmp/wf_zone_pre_sev6.csv`

**Tests**
- No test changes. The existing `test_scoring_model_v2.py` covers the gate logic; the threshold value lives in YAML and is read through `_zone_threshold` with safe defaults, so changing 5 → 6 doesn't affect any test that doesn't pin the value explicitly. None do.

---

## Honest caveats

1. **In-sample recalibration.** sev=6 was chosen by sweeping the same data the model was already fit to. A proper validation would treat `chase_severity` as a tunable parameter in `scripts/run_weight_grid.py` and report jointly with `risk.penalty_multiplier`. Out of scope for this phase; flagged as follow-up.

2. **The apples-to-apples Δ Sharpe of +0.012 is not statistically significant.** With 58 monthly observations, the standard error on a Sharpe estimate is roughly 0.13 (≈ √(2/n) × annualization). The +0.012 difference is two orders of magnitude smaller than the noise. We are honest enough to call it noise.

3. **Today's snapshot (2026-05-05) is unaffected.** Top-8 names all have severity 6-8, so they were and remain Avoid Chasing under both sev=5 and sev=6. The recalibration helps in months where the boundary cohort is nontrivial; today is not such a month.

4. **`gate_attribution` only compares two scenarios** (filter on / filter off, with one alignment row). It does not sweep the threshold or compare across calibration changes. A future `gate_calibration_grid` could sweep `min_risk_severity ∈ {4,5,6,7}` × `min_risk_severity_for_blocking ∈ {5,6,7}` to formalize the "structural alignment" argument; not done in this phase.

5. **The `max_risk_penalty: 2.0` field for Strong remains in YAML but is non-binding** in the empirical distribution (max observed = 1.78). It is documentation of intent, not an active filter. A future cleanup could either tighten it to bind, or remove it as dead code with a comment explaining why.

6. **The phase teaches a methodology lesson, not just a parameter lesson.** A `head(5)` shortcut in an ad-hoc analysis pulled in months that production rules would skip, inflating the apparent improvement by 5,500 pp of total return. Apples-to-apples (matched-sample) comparison is now built into the report so this category of mistake is harder to make again.

---

## Pre-conditions still required before daily auto-scheduling

Carrying forward from `phase_gate_repair.md`:

1. ✅ **Decision-zone label fix** — DONE (gate-repair phase, 2026-05-03)
2. ✅ **Decision-zone calibration honesty** — DONE (this phase, 2026-05-09)
3. ⏳ **Out-of-regime stress test** — still pending; current backtest is 100% AI-bull
4. ⏳ **Phase D portfolio construction** — max position, vol targeting, stop-loss (D1+D2 partially complete)
5. ⏳ **Paper-portfolio shadow run** — 1–3 months
6. 🆕 **Decision-zone recalibration grid** — `chase_severity` × `risk_penalty_multiplier` swept jointly via `run_weight_grid.py`, out-of-sample where possible

Recommended next step: still the out-of-regime stress test, since none of the phases since A2-adopt have addressed regime conditionality, and the gate logic's behavior in a non-AI-bull regime is genuinely unknown.
