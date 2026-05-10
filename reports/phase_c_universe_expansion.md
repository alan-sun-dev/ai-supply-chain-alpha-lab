# Phase C — Universe Expansion (PoC)
_Backtest: 2020-06-30 → 2026-04-30, 70 rebalances. Top-5 EW monthly._

## 1. Executive Summary
- **At 25 bps cost, original universe (59 names)**: CAGR `110.7%`, Sharpe `1.880`, max DD `-24.8%`.
- **At 25 bps cost, expanded_liquid_60 (59 names)**: CAGR `110.7%`, Sharpe `1.880`, max DD `-24.8%`.
- ΔSharpe: `0.000`, ΔMax DD: `0.0%`, ΔCAGR: `0.0%`.
- **expanded_liquid_40**: CAGR `97.7%`, Sharpe `1.765`, max DD `-26.5%`, unique holdings `39`.

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
| expanded_all_available | 77 | 25 | 120.0% | 1.861 | -33.3% | 70.0% | 65.1% | 99.363 | 89.2% | 6.5% | 40.0% | 73 | 0 / — | 129 / 64.3% |
| expanded_all_available | 77 | 50 | 116.0% | 1.822 | -34.5% | 70.0% | 65.1% | 89.240 | 85.2% | 6.5% | 40.0% | 73 | 0 / — | 129 / 64.3% |
| expanded_all_available | 77 | 100 | 108.1% | 1.744 | -36.9% | 70.0% | 65.1% | 71.945 | 77.4% | 6.5% | 40.0% | 73 | 0 / — | 129 / 64.3% |
| expanded_liquid_40 | 39 | 25 | 97.7% | 1.765 | -26.5% | 67.1% | 55.4% | 53.246 | 66.9% | 12.8% | 40.0% | 39 | 0 / — | 66 / 68.2% |
| expanded_liquid_40 | 39 | 50 | 94.6% | 1.727 | -27.0% | 67.1% | 55.4% | 48.532 | 63.8% | 12.8% | 40.0% | 39 | 0 / — | 66 / 68.2% |
| expanded_liquid_40 | 39 | 100 | 88.5% | 1.650 | -27.9% | 65.7% | 55.4% | 40.303 | 57.7% | 12.8% | 40.0% | 39 | 0 / — | 66 / 68.2% |
| expanded_liquid_60 | 59 | 25 | 110.7% | 1.880 | -24.8% | 67.1% | 62.0% | 77.191 | 79.9% | 8.5% | 40.0% | 58 | 0 / — | 103 / 65.0% |
| expanded_liquid_60 | 59 | 50 | 107.0% | 1.840 | -25.4% | 67.1% | 62.0% | 69.670 | 76.3% | 8.5% | 40.0% | 58 | 0 / — | 103 / 65.0% |
| expanded_liquid_60 | 59 | 100 | 99.8% | 1.759 | -26.6% | 67.1% | 62.0% | 56.727 | 69.1% | 8.5% | 40.0% | 58 | 0 / — | 103 / 65.0% |
| original | 59 | 25 | 110.7% | 1.880 | -24.8% | 67.1% | 62.0% | 77.191 | 79.9% | 8.5% | 40.0% | 58 | 0 / — | 103 / 65.0% |
| original | 59 | 50 | 107.0% | 1.840 | -25.4% | 67.1% | 62.0% | 69.670 | 76.3% | 8.5% | 40.0% | 58 | 0 / — | 103 / 65.0% |
| original | 59 | 100 | 99.8% | 1.759 | -26.6% | 67.1% | 62.0% | 56.727 | 69.1% | 8.5% | 40.0% | 58 | 0 / — | 103 / 65.0% |

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
| expanded_all_available | Avoid | 4120 | 77 | 54.0% | 2.8% | -1.459 | 2.347 |
| expanded_all_available | Avoid Chasing | 243 | 68 | 59.3% | 7.9% | 1.619 | 2.469 |
| expanded_all_available | Neutral | 898 | 77 | 57.6% | 4.3% | 0.768 | 2.145 |
| expanded_all_available | Watchlist | 129 | 52 | 64.3% | 8.8% | 2.928 | 2.504 |
| expanded_liquid_40 | Avoid | 2086 | 39 | 55.6% | 4.0% | -1.599 | 2.302 |
| expanded_liquid_40 | Avoid Chasing | 140 | 36 | 57.1% | 8.7% | 1.511 | 2.454 |
| expanded_liquid_40 | Neutral | 438 | 39 | 57.3% | 4.5% | 0.865 | 2.061 |
| expanded_liquid_40 | Watchlist | 66 | 29 | 68.2% | 10.6% | 2.940 | 2.500 |
| expanded_liquid_60 | Avoid | 3131 | 59 | 55.4% | 3.3% | -1.516 | 2.336 |
| expanded_liquid_60 | Avoid Chasing | 195 | 51 | 58.5% | 7.4% | 1.540 | 2.454 |
| expanded_liquid_60 | Neutral | 701 | 59 | 58.3% | 4.6% | 0.822 | 2.085 |
| expanded_liquid_60 | Watchlist | 103 | 41 | 65.0% | 8.2% | 2.962 | 2.500 |
| original | Avoid | 3131 | 59 | 55.4% | 3.3% | -1.516 | 2.336 |
| original | Avoid Chasing | 195 | 51 | 58.5% | 7.4% | 1.540 | 2.454 |
| original | Neutral | 701 | 59 | 58.3% | 4.6% | 0.822 | 2.085 |
| original | Watchlist | 103 | 41 | 65.0% | 8.2% | 2.962 | 2.500 |

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