# Phase C — Universe Expansion (PoC)
_Backtest: 2020-06-30 → 2026-04-30, 70 rebalances. Top-5 EW monthly._

## 1. Executive Summary
- **At 25 bps cost, original universe (59 names)**: CAGR `117.5%`, Sharpe `2.031`, max DD `-27.8%`.
- **At 25 bps cost, expanded_liquid_60 (59 names)**: CAGR `117.5%`, Sharpe `2.031`, max DD `-27.8%`.
- ΔSharpe: `0.000`, ΔMax DD: `0.0%`, ΔCAGR: `0.0%`.
- **expanded_liquid_40**: CAGR `112.6%`, Sharpe `2.012`, max DD `-23.7%`, unique holdings `39`.

## 2. Why Universe Expansion
- A2 baseline runs on 22 ranked names.  Top-5 = 23% concentration → max DD -31% vs benchmark -29%.
- B1 confirmed transaction cost is not the bottleneck (break-even ~588 bps).  The remaining identified risk is concentration, addressable only by widening the universe.
- Phase C tests whether widening to 40/60 names (a) preserves Sharpe / alpha, (b) reduces max DD, (c) reduces single-theme exposure.

## 3. Candidate Universe
- 78 candidates across 13 themes (6 original + 7 new: optical_communication, thermal, memory_hbm, passive_components, pcb_substrate, power_grid_energy, leo_satellite, ai_server_assembly).
- Source: `data/manual/beneficiary_universe_phase_c_candidates.csv`. Manual research-grade list, no claim to completeness.

## 4. Liquidity Filter
- ADV proxy = mean(close × volume) over last 60 trading days.
- Tier A (ADV ≥ NTD 100M): 72 names.  Tier B (30M ≤ ADV < 100M): 5.  Tier C: 1.  Tier X (no data): 0.
- Filter applied: `data_available=True` AND `missing_ratio < 10%` AND `ADV ≥ 30M TWD`.  Issuer 2330.TW always kept.

## 5. Backtest Setup
- A2 baseline weights (`rev=0.30`, `flw=0.10`, `min_alpha=2.5`, others unchanged).
- For each universe variant: rebuild AI factor index, recompute residual alpha, rerun PIT-correct walk-forward, apply B1 transaction-cost machinery.
- **Important**: FinMind data (revenue / inst flow / valuation) is not backfilled for new tickers (deferred to Phase B2/B3).  Those factors are 0 for new names; ranking falls back to `residual_alpha` (dominant signal per A1/A2 ablation).

## 6. Performance Comparison
| Universe | N | cost | CAGR | Sharpe | max DD | Hit | Turnover | Final NAV | Net α | Top-5 conc. | Max θ exp | Uniq | Strong (n / hit) | Watch (n / hit) |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| expanded_all_available | 77 | 25 | 117.2% | 2.032 | -27.1% | 74.3% | 58.0% | 92.228 | 86.5% | 6.5% | 40.0% | 69 | 26 / 65.4% | 45 / 51.1% |
| expanded_all_available | 77 | 50 | 113.6% | 1.991 | -27.8% | 74.3% | 58.0% | 83.763 | 82.9% | 6.5% | 40.0% | 69 | 26 / 65.4% | 45 / 51.1% |
| expanded_all_available | 77 | 100 | 106.7% | 1.909 | -29.2% | 74.3% | 58.0% | 69.062 | 75.9% | 6.5% | 40.0% | 69 | 26 / 65.4% | 45 / 51.1% |
| expanded_liquid_40 | 39 | 25 | 112.6% | 2.012 | -23.7% | 65.7% | 54.0% | 81.479 | 81.9% | 12.8% | 40.0% | 39 | 5 / 60.0% | 25 / 64.0% |
| expanded_liquid_40 | 39 | 50 | 109.4% | 1.973 | -24.2% | 65.7% | 54.0% | 74.460 | 78.6% | 12.8% | 40.0% | 39 | 5 / 60.0% | 25 / 64.0% |
| expanded_liquid_40 | 39 | 100 | 103.0% | 1.893 | -25.3% | 64.3% | 54.0% | 62.158 | 72.2% | 12.8% | 40.0% | 39 | 5 / 60.0% | 25 / 64.0% |
| expanded_liquid_60 | 59 | 25 | 117.5% | 2.031 | -27.8% | 72.9% | 55.4% | 92.931 | 86.7% | 8.5% | 40.0% | 56 | 17 / 70.6% | 35 / 40.0% |
| expanded_liquid_60 | 59 | 50 | 114.1% | 1.991 | -28.5% | 72.9% | 55.4% | 84.752 | 83.3% | 8.5% | 40.0% | 56 | 17 / 70.6% | 35 / 40.0% |
| expanded_liquid_60 | 59 | 100 | 107.4% | 1.912 | -29.9% | 72.9% | 55.4% | 70.461 | 76.7% | 8.5% | 40.0% | 56 | 17 / 70.6% | 35 / 40.0% |
| original | 59 | 25 | 117.5% | 2.031 | -27.8% | 72.9% | 55.4% | 92.931 | 86.7% | 8.5% | 40.0% | 56 | 17 / 70.6% | 35 / 40.0% |
| original | 59 | 50 | 114.1% | 1.991 | -28.5% | 72.9% | 55.4% | 84.752 | 83.3% | 8.5% | 40.0% | 56 | 17 / 70.6% | 35 / 40.0% |
| original | 59 | 100 | 107.4% | 1.912 | -29.9% | 72.9% | 55.4% | 70.461 | 76.7% | 8.5% | 40.0% | 56 | 17 / 70.6% | 35 / 40.0% |

## 7. Transaction Cost Impact
Each universe is shown at 25 / 50 / 100 bps in §6.  Larger universes have similar turnover (top-5 EW rebalance dynamics), so cost drag scales similarly across variants.

## 8. Concentration Analysis
- Original: top-5 / 22 = 22.7% of universe.  Expanded_liquid_60: top-5 / 60 = 8.3%.
- Lower top-5 / universe ratio is what we wanted; whether it actually shows up in max-DD reduction depends on whether new tickers diversify away from existing AI-theme beta. See §6.

## 9. Theme Exposure Analysis
| Universe | Max single-theme weight | Themes appearing in top-5 |
|:--|---:|---:|
| expanded_all_available | 40.0% | 13 |
| expanded_liquid_40 | 40.0% | 12 |
| expanded_liquid_60 | 40.0% | 13 |
| original | 40.0% | 13 |

If `max_theme_exposure` exceeds 60% on a sustained basis, a theme cap (e.g. single theme ≤ 40%) would be the right next-step risk control — see §12.

## 10. Label Predictive Power
| Universe | Zone | n_obs | n_uniq | hit_rate | mean fwd_1m | avg α | avg conf |
|:--|:--|---:|---:|---:|---:|---:|---:|
| expanded_all_available | Avoid | 4408 | 77 | 54.3% | 2.9% | -1.365 | 2.358 |
| expanded_all_available | Avoid Chasing | 230 | 54 | 64.8% | 10.8% | 1.084 | 2.426 |
| expanded_all_available | Neutral | 681 | 77 | 57.0% | 4.1% | 0.656 | 2.366 |
| expanded_all_available | Strong Candidate | 26 | 9 | 65.4% | 9.6% | 3.413 | 3.596 |
| expanded_all_available | Watchlist | 45 | 23 | 51.1% | 4.6% | 2.507 | 2.711 |
| expanded_liquid_40 | Avoid | 2220 | 39 | 55.9% | 4.2% | -1.385 | 2.307 |
| expanded_liquid_40 | Avoid Chasing | 153 | 34 | 60.1% | 9.7% | 1.000 | 2.415 |
| expanded_liquid_40 | Neutral | 327 | 39 | 56.3% | 4.5% | 0.667 | 2.200 |
| expanded_liquid_40 | Strong Candidate | 5 | 2 | 60.0% | 1.4% | 3.347 | 3.600 |
| expanded_liquid_40 | Watchlist | 25 | 12 | 64.0% | 2.8% | 2.564 | 2.660 |
| expanded_liquid_60 | Avoid | 3329 | 59 | 55.3% | 3.3% | -1.380 | 2.340 |
| expanded_liquid_60 | Avoid Chasing | 201 | 46 | 63.7% | 10.7% | 1.069 | 2.420 |
| expanded_liquid_60 | Neutral | 548 | 59 | 60.0% | 5.0% | 0.674 | 2.318 |
| expanded_liquid_60 | Strong Candidate | 17 | 5 | 70.6% | 6.2% | 3.385 | 3.588 |
| expanded_liquid_60 | Watchlist | 35 | 18 | 40.0% | 0.6% | 2.577 | 2.686 |
| original | Avoid | 3329 | 59 | 55.3% | 3.3% | -1.380 | 2.340 |
| original | Avoid Chasing | 201 | 46 | 63.7% | 10.7% | 1.069 | 2.420 |
| original | Neutral | 548 | 59 | 60.0% | 5.0% | 0.674 | 2.318 |
| original | Strong Candidate | 17 | 5 | 70.6% | 6.2% | 3.385 | 3.588 |
| original | Watchlist | 35 | 18 | 40.0% | 0.6% | 2.577 | 2.686 |

## 11. Failure / Success Diagnosis
**Verdict: Phase C SUCCESS.** Sharpe drop ≤ 0.15 AND max DD improved or unchanged.

Possible diagnoses:
- New tickers ranked highly but proved over-fit to AI bull tail end → check `expanded_liquid_60` label hit rates in §10.
- FinMind-dependent factors zeroed for new names → revenue confirmation gate is weakened for new theme tickers.  Mitigation = Phase B2/B3 backfill before re-evaluating.
- AI factor index now includes new themes → residual alpha for original tickers shifts; compare original-universe results in this run vs A2 baseline to gauge the index drift.

## 12. Recommendation
- **Adopt expanded_liquid_40 instead** — better risk/reward trade-off than _60 for this data.

Theme cap recommendation: if max single-theme weight in §9 exceeds 60% sustained, introduce a `single_theme_cap = 0.40` in fusion ranking before adopting expanded universe live.

## 13. Next Step
Conditional on §12 verdict:
- If expansion adopted → run Phase B2/B3 (FinMind backfill) so new-ticker scoring uses full feature set; then redo this PoC and decide on theme cap.
- If expansion not adopted → Phase B2/B3 first to give expansion a fair test.
- **Daily auto-scheduling: still NOT recommended** until expansion + B2/B3 reach a stable verdict.