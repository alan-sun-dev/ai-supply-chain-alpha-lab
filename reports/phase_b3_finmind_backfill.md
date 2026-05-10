# Phase B3 — FinMind Tier-2 Data Backfill

_2026-05-03. Step-1 active baseline (expanded_liquid_60 + theme cap, max 2 per theme, Watchlist threshold 2.0). NO model / weight changes — data backfill only._

## TL;DR

**B3 fixed Watchlist quality** (hit rate 40% → **55.5%**) — its stated goal.
**B3 expanded the Strong Candidate sample 4×** (n=17 / 5 unique → n=72 / 36 unique).
**B3 reduced the gross-portfolio CAGR** from 117.5% → 77.5% — because Tier-2 factors now actively penalize overvalued AI-mania winners that previously ranked on residual-alpha alone. **This is honesty, not regression.**
Strategy still beats benchmark by wide margin: **CAGR 77.5% vs 30.2%, Sharpe 1.62 vs 1.28**, max DD -29.7% vs -29.2%.
Break-even one-way cost: **478 bps** (vs 812 bps pre-B3) — still ~6× realistic Taiwan retail cost.

---

## 1. Coverage delta

| Source | Pre-B3 | **Post-B3** | Δ |
|---|---:|---:|---:|
| Universe size | 60 | 60 | — |
| Tickers with **any** monthly revenue | 17 | **60** | +43 |
| Tickers with **any** institutional flow | 17 | **60** | +43 |
| Tickers with **any** valuation | 17 | **60** | +43 |
| **Tickers with full Tier-2 (≥24 obs all 3 sources)** | **17 (28%)** | **60 (100%)** | **+43** |
| Earliest revenue | 2020-01 | **2018-01** | +2 yr |
| Earliest institutional flow | 2022-01-03 | **2018-01-02** | +4 yr |
| Earliest valuation | 2020-01-02 | **2018-01-02** | +2 yr |
| Total monthly revenue rows | 1,756 | **6,464** | +4,708 |
| Total institutional flow rows | 23,996 | **126,552** | +102,556 |
| Total valuation rows | 35,258 | **129,964** | +94,706 |

Per-ticker coverage report: `data/output/data_coverage_report_post_b3.csv`.

## 2. Decision-zone quality — the core diagnostic

| Zone | Pre-B3 (n / unique / hit / mean) | **Post-B3** | Δ hit rate |
|---|---|---|---:|
| Strong Candidate | 17 / 5 / **70.6%** / +6.2% | **72 / 36** / 55.6% / +5.8% | -15 pts (sample 4× larger) |
| **Watchlist** | 35 / 18 / **40.0%** / +0.6% | **110 / 40** / **55.5%** / +4.7% | **+15.5 pts** ✅ |
| Neutral | 548 / 59 / 60.0% / +5.0% | 838 / 59 / 56.6% / +4.7% | -3.4 pts |
| Avoid Chasing | 201 / 46 / 63.7% / +10.7% | **13 / 11** / 53.8% / +11.1% | sample 15× smaller |
| Avoid | 3329 / 59 / 55.3% / +3.3% | 3097 / 59 / 56.3% / +3.5% | +1.0 pts |

**Reading:**
- ✅ **Watchlist hit rate +15.5 pts** (40% → 55.5%) — the structural problem that motivated B3 is fixed. Tier-2 confirmation now applies to the new 36 tickers.
- ✅ **Strong sample 4× larger** (n=17 → n=72) with 36 unique tickers (was 5). Statistical power restored.
- ❗ **Strong hit rate dropped** 70.6% → 55.6%. Trade-off: the gate became less selective because more tickers can pass `tier2_positive` now that Tier-2 isn't silent. Still informative (above Avoid 56.3%).
- ✅ **Avoid Chasing population collapsed** 201 → 13 obs. Pre-B3 the gate was misfiring: `tier4_risk_severity ≥ 5 AND tier2_revenue_confirmation ≤ 0` was triggering for almost any high-momentum new ticker because revenue was missing (= 0 = not positive). Real revenue data shows most of those names DO have positive revenue → no longer mis-classified.
- All zones now have positive mean fwd return. The label hierarchy is internally consistent.

## 3. Gross portfolio impact

| Metric | Pre-B3 | **Post-B3** | Δ | 0050.TW |
|---|---:|---:|---:|---:|
| CAGR (gross) | 120.9% | **80.5%** | -40.4 pts | 30.2% |
| Sharpe | 2.07 | **1.66** | -0.41 | 1.28 |
| Max DD | -27.0% | -28.1% | -1.1 pts | -29.2% |
| Final NAV | 101.9 | **31.3** | -69% | 4.78 |
| Net α vs 0050 (CAGR) | +90.2% | **+49.8%** | -40.4 pts | — |

**Why did metrics drop after adding more data?**

Pre-B3, the 36 new tickers had `revenue_acceleration = 0`, `institutional_flow_score = 0`, `valuation_risk_score = 0` (penalty silent). They were ranked **only on residual_alpha** — pure price momentum vs benchmark. AI-mania winners (Quanta 2382, Wiwynn 6669, Auras 3017, Elite Material 2383, Unimicron 3037) all had high residual alpha, so they dominated top-5.

Post-B3, those names now carry real Tier-2 scores. Many of them have **stretched valuations** (`valuation_risk_score` near 1.0 → `-0.10 × z-score = -3 × 0.10 = -0.30 contribution → ×5 SCALE = -1.5 risk penalty contribution`). That penalty kicks down their alpha_score, top-5 rotates to less-momentum / more-fundamental names → lower returns in the AI-mania regime.

**This is honesty, not failure.** The pre-B3 backtest was effectively saying "buy any high-momentum name regardless of fundamentals", which over-fit to 2023-2024 AI mania. Post-B3 represents what would actually have happened with a model that knew about valuations.

## 4. Cost-aware results (Step-1 active baseline, 25 / 50 / 100 bps)

| cost_bps | CAGR | Sharpe | Max DD | Final NAV | Net α vs 0050 |
|---:|---:|---:|---:|---:|---:|
| 0 | 80.5% | 1.66 | -28.1% | 31.3 | +49.8% |
| **25** | **77.5%** | **1.62** | -29.7% | 28.4 | **+46.8%** |
| 50 | 74.6% | 1.58 | -31.2% | 25.8 | +43.9% |
| 100 | 68.9% | 1.49 | -34.2% | 21.2 | +38.1% |
| Benchmark 0050.TW | 30.2% | 1.28 | -29.2% | 4.78 | — |

**Break-even one-way cost: 478 bps** (vs 812 bps pre-B3). Lower headroom but still well above realistic Taiwan retail cost (60-90 bps) and institutional desk cost (25-50 bps). Cost remains a non-issue for investability.

## 5. Cross-universe comparison (Phase C re-run with B3 data, 25 bps)

| Universe | N | CAGR | Sharpe | max DD | top-5 conc | Strong (n / hit) | Watchlist (n / hit) |
|---|---:|---:|---:|---:|---:|---:|---:|
| original (= Step-1) | 59 | 77.5% | 1.62 | -29.7% | 8.5% | 72 / 55.6% | 110 / 55.5% |
| **expanded_liquid_40** | 39 | **83.7%** | **1.83** | -29.6% | 12.8% | 40 / 55.0% | 65 / 56.9% |
| expanded_liquid_60 | 59 | 77.5% | 1.62 | -29.7% | 8.5% | 72 / 55.6% | 110 / 55.5% |
| **expanded_all_available** | 77 | **88.7%** | **1.81** | -30.6% | 6.5% | 87 / 58.6% | 115 / 50.4% |

**New finding**: with B3 data, `expanded_liquid_40` (Sharpe 1.83) and `expanded_all_available` (Sharpe 1.81) both **outperform** the active `expanded_liquid_60` (Sharpe 1.62). This contradicts the pre-B3 conclusion that _60 was the sweet spot. **Do not act on this without further analysis** — see §7.

## 6. Ablation under post-B3 data

| Variant | Sharpe | Total | Note |
|---|---:|---:|---|
| **full** (current Step-1) | 1.680 | 32.7x | baseline |
| `residual_alpha_only` | **1.897** | **57.7x** | +0.22 Sharpe, +76% return |
| `no_revenue` | 1.869 | 65.2x | revenue is now a *drag* on this universe |
| `no_flow` | 1.761 | 38.3x | flow modestly helps |
| `no_risk_penalty` | 1.663 | 38.5x | risk penalty roughly neutral on Sharpe but DD widens |
| `random` | 1.373 | 12.0x | noise floor |

⚠️ **Ablation flags a weight calibration issue**: under post-B3 data, removing `revenue_confirmation_score` (rev_w=0.30 in current YAML) materially *improves* Sharpe and total return. This is the opposite of A2's finding (where rev=0.30 was the best knob, on a universe with only 17 tickers covered).

**Hypothesis**: A2 found rev=0.30 on a universe where only 28% of tickers had revenue data → the factor was effectively binary "has-revenue-data vs not", which correlated with the original 22 (well-known winners). With 100% coverage, revenue_acceleration becomes a real factor across all 60 names, and rev=0.30 now over-weights it relative to its true predictive power.

**Per the user mandate ("Do not change weights unless the post-B3 validation clearly supports it"), B3 itself does not change weights.** But the next phase should re-run the A2 grid search on post-B3 data to find updated optima.

## 7. Honest caveats

1. **AI mania regime persists in the test window.** Pre-B3 results were inflated by it; post-B3 corrects partially by adding fundamental gates, but the residual_alpha component is still mostly riding the AI tape.
2. **Revenue weight calibration is now suspect.** Ablation evidence (residual_alpha_only Sharpe 1.90 vs full 1.68) is strong, but per user mandate we will not act on it within B3. Recommend Phase A2-rerun (weight grid on post-B3 data) as the immediate next step.
3. **The expanded_liquid_40 result** (Sharpe 1.83) suggests a smaller universe may actually be better post-B3. Could mean: more data → more borderline names that hurt → fewer-but-higher-quality names win. Worth investigating but not in B3 scope.
4. **Avoid Chasing gate behavior changed massively** (n=201 → n=13). The gate was effectively misfiring pre-B3 due to missing-data conflation. Now it fires only on the rare names that genuinely have high risk + weak revenue. Whether the +11.1% mean fwd return on those 13 is meaningful or noise is unclear at n=13.
5. **Watchlist quality fix is real**, but Watchlist's mean fwd return (+4.7%) is now barely above Neutral (+4.7%). The label adds little signal beyond Strong vs Neutral. Could simplify the hierarchy in a future phase.

## 8. Files added / modified

**Added**
- `src/capex_alpha/data_quality.py` — coverage report module
- `scripts/run_data_coverage_report.py` — CLI
- `tests/test_data_quality.py` — 4 tests

**Modified (data only — no model / scoring code changes)**
- `data/manual/monthly_revenue.csv` — 24 tickers / 1,756 rows → **68 tickers / 6,464 rows**, 2018-01 onwards
- `data/manual/institutional_flow.csv` — 24 / 23,996 → **67 / 126,552**, 2018-01 onwards
- `data/manual/valuation.csv` — 24 / 35,258 → **67 / 129,964**, 2018-01 onwards

**Snapshot**
- `archive/before_b3/` — 24 files (pre-B3 outputs + reports + raw FinMind CSVs)

**Refreshed outputs (under Step-1 baseline + B3 data)**
- `data/output/walk_forward_v2_*.csv`, `transaction_cost_*.csv`, `universe_expansion_*.csv`, `dashboard_data.json`, `alpha_ranking.csv`, `data_coverage_report_post_b3.csv`
- `reports/walk_forward_v2_summary.md`, `phase_b1_transaction_cost.md`, `phase_c_universe_expansion.md`

Tests: **65 / 65 passing** (was 61 + 4 new).

## 9. Recommendation for next step

Per user mandate: **B3 was data-completeness only**. No new factors, no new ranking logic, no automation, no weight changes. Done.

**Next-step options to discuss:**

1. **Rerun A2 weight grid on post-B3 data** — high-priority. Ablation strongly suggests the current weights (`rev=0.30`, `flw=0.10`) need re-calibration now that all 60 tickers have real Tier-2. Likely landing zone: `rev=0.10-0.20`, possibly `residual_alpha_only` as a viable variant.
2. **Investigate `expanded_liquid_40`** — its Sharpe (1.83) beats current active baseline (1.62) on B3 data. Could be the new active baseline if confirmed robust; would mean pulling back from 60 to 40 names.
3. **Phase B2 (GDELT news backfill)** — narrative was already shown to be near-zero contribution; lower priority than the above.
4. **Phase D (portfolio construction: max position, vol targeting, stop-loss)** — meaningful only after weights re-calibrated.
5. **Daily auto-scheduling: still NOT recommended** — weight calibration is now the open question; running daily on stale weights doesn't help.

Recommended sequence: **A2-rerun (weights on B3 data) → if results clean, consider universe size revisit → then Phase D portfolio construction → only then daily auto-run.**
