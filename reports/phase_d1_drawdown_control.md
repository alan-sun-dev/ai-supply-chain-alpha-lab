# Phase D1 — Drawdown Control MVP

_2026-05-03. Active baseline (Simplest Robust + gate repair) **unchanged**. New layer: `validation/exposure_overlay.py` reads `regime_filter.classify()` per rebalance date and scales gross exposure: 100% / 70% / 30% / 30% (risk_on / neutral / risk_off / drawdown_control). Hard override: strategy NAV DD > 15% → cap exposure ≤ 30%. PIT-correct (slice market price + AI NAV up to each rebalance date)._

## TL;DR — mixed result, not an automatic adoption

| Metric | Baseline | **D1 scaled** | Δ | Verdict |
|---|---:|---:|---:|---|
| **Max DD** | -24.25% | **-20.72%** | **+3.53 pts** ✅ | modestly better |
| **Calmar (CAGR / |maxDD|)** | 4.72 | **4.05** | -0.67 | slightly worse |
| **CAGR (gross)** | 114.4% | 84.0% | **-30.4 pts** ❌ | meaningful cost |
| **Sharpe (gross)** | 1.92 | 1.65 | -0.27 ❌ | meaningful cost |
| **Worst single month** | -11.61% | -11.61% | 0 | unchanged (flash drops too quick) |
| **Months in drawdown** | 31 / 70 (44%) | **39 / 70 (56%)** | **+8 mo** ❌ | worse |
| **Longest peak→recovery** | 7 months | **14 months** | **+7 mo doubled** ❌ | substantially worse |
| Net CAGR @ 25 bps | 110.7% | 80.6% | -30 pts | matches gross |
| Net CAGR @ 50 bps | 107.0% | 77.4% | -29.6 pts | matches gross |

**The overlay reduces drawdown depth modestly (-3.5 pts) but doubles drawdown duration and costs 30 pts of CAGR.** Exposure scaling in this regime cuts both sides of the volatility — the down months *and* the recovery months. **Recommend NOT auto-adopting D1 as currently configured**; see §6 for refinements to consider.

---

## 1. Per-regime exposure timeline

Distribution of the 70 walk-forward months across regime classifications:

| Regime label | n_months | Avg exposure | Avg raw return | Avg scaled return |
|---|---:|---:|---:|---:|
| `risk_on` | 42 (60%) | 100% | +7.55% | +7.55% |
| `neutral` | 14 (20%) | 70% | +5.91% | +4.14% |
| `risk_off` | 5 (7%) | 30% | +3.43% | +1.03% |
| `drawdown_control` | 9 (13%) | 30% | **+10.50%** | **+3.15%** |

**Critical observation**: the 9 months classified as `drawdown_control` (where exposure was cut to 30%) had **average raw return +10.5%** — these were the strong recovery months immediately following drawdowns. By scaling exposure down to 30%, we captured only +3.15% of the +10.5% on average.

This is the core asymmetry of regime-based DD control: the `drawdown_control` trigger fires *during* the DD, but DD typically resolves with a sharp recovery month — and the trigger is still active on that recovery.

`dd_override_applied` count = **0** across all regimes. The cascade's `drawdown_control` regime already triggered every time the explicit override would have. The explicit override is redundant with the cascade by design (both check `strategy_drawdown_min: -0.15`); it's a safety net for cases where YAML config changes break the cascade.

## 2. CAGR / Sharpe / Calmar / Max DD by variant

| Variant | n | CAGR | Sharpe | Calmar | Max DD | Hit | Worst Mo | Mo in DD | Longest Recovery |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 70 | 114.4% | 1.92 | 4.72 | -24.25% | 67.1% | -11.61% | 31 | 7 mo |
| **D1 scaled** | 70 | **84.0%** | **1.65** | 4.05 | **-20.72%** | 67.1% | -11.61% | **39** | **14 mo** |
| baseline @ 25 bps | 70 | 110.7% | 1.88 | 4.45 | -24.85% | 67.1% | -11.71% | 31 | 7 mo |
| D1 @ 25 bps | 70 | 80.6% | 1.61 | 3.78 | -21.34% | 67.1% | -11.71% | 39 | 14 mo |
| baseline @ 50 bps | 70 | 107.0% | 1.84 | 4.21 | -25.44% | 67.1% | -11.81% | 33 | 12 mo |
| D1 @ 50 bps | 70 | 77.4% | 1.57 | 3.52 | -21.96% | 67.1% | -11.81% | 39 | 14 mo |

**Reading:**
- Calmar is *worse* under D1 — CAGR drops faster than DD shrinks (CAGR -30 pts vs DD only -3.5 pts means CAGR/|DD| collapses)
- Worst single month is **identical** — overlay can't react fast enough to one-month flash drops because regime is computed at month-end after the damage is done
- Hit rate identical — distribution shape unchanged, just scaled
- Cost-adjusted ranking is the same — overlay doesn't change the conclusion

## 3. Drawdown episode comparison (peak → recovery)

| # | Baseline (start → end, duration, max DD) | D1 (start → end, duration, max DD) |
|---|---|---|
| 1 | 2020-12 → 2021-02, 2 mo, -8.1% | 2020-12 → 2021-02, 2 mo, -8.1% |
| 2 | 2021-04 → 2021-09, 5 mo, -12.0% | 2021-04 → 2021-10, **6 mo**, -12.0% |
| 3 | 2021-12 → 2022-07, 7 mo, -23.3% | 2021-12 → **2023-02**, **14 mo**, -15.9% |
| 4 | 2022-08 → 2022-10, 2 mo, -14.3% | _(merged into #3)_ | 
| 5 | 2022-11 → 2022-12, 1 mo, -2.8% | _(merged into #3)_ |
| 6 | 2023-07 → 2024-01, 6 mo, -19.8% | 2023-07 → **2024-03**, **8 mo**, -16.8% |
| 7 | 2024-04 → 2024-05, 1 mo, -2.5% | 2024-04 → 2024-05, 1 mo, -2.5% |
| 8 | 2024-12 → 2025-06, 6 mo, -24.3% | 2024-12 → **2025-07**, **7 mo**, -20.7% |
| 9 | 2025-10 → 2025-11, 1 mo, -3.6% | 2025-10 → 2025-11, 1 mo, -3.6% |
| **Total episodes** | **9** | **7** (some baseline episodes merged into longer D1 episodes) |

**Critical pattern**: D1 reduces episode *count* (9 → 7) by smoothing out shallow DDs, but **extends the deep ones**. The 2021-12 episode went from 7 months / -23.3% to **14 months** / -16% — half the depth, double the duration. Net DD experience in time-in-pain terms is similar or worse.

## 4. Worst single month — UNCHANGED at -11.6%

Both baseline and D1 share `2025-02 -11.6%` as the worst month. Why D1 doesn't help:
- Regime is computed at month-end based on EOM data
- The first month of a sharp drop sees the strategy **fully invested** under the previous month's regime classification
- Only after the bad month does the cascade switch to defensive
- D1 helps with **subsequent** months in the DD, not the **first** month

This is a structural limitation of monthly-rebalance regime overlays. To reduce worst-month, you'd need either:
- Shorter rebalance frequency (weekly?)
- Intra-month stop-loss
- Position-level (not portfolio-level) stops
None are in D1 scope.

## 5. Turnover decomposition (D1 portfolio)

| Component | Mean monthly | Annualised |
|---|---:|---:|
| Base name rotation | 61.43% | 7.37× |
| Exposure changes (|Δ exposure|) | 16.29% | 1.95× |
| **Total** | **63.63%** | **7.64×** |

Adding the exposure-scaling layer increases annualised turnover from baseline 7.44× → 7.64× — a modest +0.20× increase. Cost impact is small (cost drag ~3% additional per year at 25 bps), so transaction-cost concerns aren't the issue. The CAGR cost is from the exposure scaling itself, not from extra trading.

## 6. Honest assessment + Phase D2 / refinement options

**What D1 actually achieves:**
- ✅ Reduces max DD by 3.5 pts (-24.3% → -20.7%)
- ✅ Reduces deep-episode DD depth (-23% → -16% in the worst episode)
- ✅ Keeps Calmar above 4.0
- ✅ The model code is now wired (any future regime-based exposure rule plugs in trivially)

**What D1 doesn't achieve:**
- ❌ CAGR cost of -30 pts is large — comes mostly from scaling down during recovery months
- ❌ Worst single month unchanged
- ❌ Drawdown duration doubles (recovery is slower because we're under-invested when the rebound hits)
- ❌ Time spent in drawdown grows (31 → 39 months)

**Why this happens:** the `regime_filter` cascade defines `drawdown_control` based on strategy NAV DD ≤ -15%. But strategy DDs in this universe typically resolve in 1-2 months with a sharp +10-20% rebound. By the time we know we're in DD (end of bad month), the next month is often the recovery — and we're capping it at 30% exposure. Net result: less downside, much less upside, net negative for total return.

### Refinement options (not implemented — for your decision)

**Option A: looser DD trigger (e.g. -20% instead of -15%)**
- Pro: only the deepest DDs trigger scaling → less false-positive scaling
- Con: bigger DDs slip through unprotected
- Estimated impact: would push D1 closer to baseline performance (good and bad)

**Option B: asymmetric scaling (cut on entry, restore quickly on recovery signal)**
- Pro: avoids capping recovery upside
- Con: requires defining "recovery signal" — non-trivial
- Best academic literature: 3-month positive return after DD bottom = exit defensive mode
- Implementation cost: moderate

**Option C: scale based on AI-cluster DD instead of total NAV DD**
- Pro: catches the worst-case (PCB+LEO+facility cluster crashes — see Phase regime stress §8) before it hits the full strategy
- Con: requires defining the cluster + tracking its DD separately
- This is essentially Phase D2 (cluster cap) — might subsume D1

**Option D: keep D1 OFF the active baseline; archive as feature flag**
- Pro: preserves current performance; D1 module exists for future use
- Con: max DD remains -24.3% — Phase regime-stress identified as binding constraint
- Best if user accepts current DD profile as the cost of being in AI exposure

### Concrete recommendation

**Do NOT auto-adopt D1 as currently configured.** The CAGR cost is too high for the DD reduction achieved. Prefer one of:

1. **Move to D2 (cluster cap) first** — likely catches the same risk (correlated drawdowns from AI infrastructure cluster) without the recovery-month penalty. Per Phase regime stress §11, this was the second-priority recommendation.
2. **If proceeding with D1**, add asymmetric recovery logic (Option B above) as part of D1.5
3. **If accepting current DD profile**, leave D1 module in place but disabled, and skip to Phase D3 (paper portfolio shadow run)

---

## Files added

**Active code (no scoring or weight changes)**
- `src/capex_alpha/validation/exposure_overlay.py` — PIT-correct regime classification per rebalance + DD override + scaled return path + episode tracking
- `scripts/run_phase_d1_drawdown_control.py` — CLI

**Tests**
- `tests/test_exposure_overlay.py` — 8 tests (DD episodes, override invariant, cost-adjustment, etc.)

**YAML**
- `config/regime_rules.yaml` — `drawdown_control.gross_exposure` 0.20 → 0.30 per user spec

**Outputs**
- `data/output/phase_d1_summary.csv` — 6 rows (baseline + D1 + 4 cost variants)
- `data/output/phase_d1_exposure_path.csv` — 70 rows (per-rebalance regime + exposure + DD)
- `data/output/phase_d1_dd_episodes.csv` — 16 rows (9 baseline + 7 D1 episodes)
- `data/output/phase_d1_regime_summary.csv` — 4 rows (per-regime aggregate)
- `reports/phase_d1_drawdown_control.md` — this report

**No model / scoring / dashboard changes.** Active baseline weights, gates, and current portfolio are unaffected.

Tests: **89 / 89 passing** (was 81 + 8 new).

---

## Decision needed

| Option | Action |
|---|---|
| **(a) Skip D1, proceed to D2 cluster cap** | Try to address the same DD risk via correlated-theme cap; D1 module stays as a feature-flag |
| (b) Adopt D1 as-is | Accept the -30 pt CAGR cost for -3.5 pt DD improvement |
| (c) Build D1.5 with asymmetric recovery | Smarter version of D1; defer D2 until later |
| (d) Skip D1 + D2; go straight to paper shadow | Accept current DD profile as cost of doing business |

My recommendation: **(a) — proceed to D2 cluster cap**. Phase regime stress §11 already identified PCB+LEO+facility cluster correlation as the underlying driver; addressing that directly may shrink the worst DDs without the recovery-month cost.
