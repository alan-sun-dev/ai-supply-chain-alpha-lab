# Phase C — Universe Expansion (PoC)
_Backtest: 2020-06-30 → 2026-04-30, 70 rebalances. Top-5 EW monthly._

## 1. Executive Summary
- **At 25 bps cost, original universe (59 names)**: CAGR `77.5%`, Sharpe `1.622`, max DD `-29.7%`.
- **At 25 bps cost, expanded_liquid_60 (59 names)**: CAGR `77.5%`, Sharpe `1.622`, max DD `-29.7%`.
- ΔSharpe: `0.000`, ΔMax DD: `0.0%`, ΔCAGR: `0.0%`.
- **expanded_liquid_40**: CAGR `83.7%`, Sharpe `1.832`, max DD `-29.6%`, unique holdings `39`.

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
| expanded_all_available | 77 | 25 | 88.7% | 1.810 | -30.6% | 70.0% | 58.9% | 40.616 | 58.0% | 6.5% | 40.0% | 68 | 87 / 58.6% | 116 / 54.3% |
| expanded_all_available | 77 | 50 | 85.5% | 1.764 | -31.1% | 68.6% | 58.9% | 36.790 | 54.8% | 6.5% | 40.0% | 68 | 87 / 58.6% | 116 / 54.3% |
| expanded_all_available | 77 | 100 | 79.3% | 1.673 | -32.2% | 65.7% | 58.9% | 30.171 | 48.6% | 6.5% | 40.0% | 68 | 87 / 58.6% | 116 / 54.3% |
| expanded_liquid_40 | 39 | 25 | 83.7% | 1.832 | -29.6% | 62.9% | 50.9% | 34.709 | 53.0% | 12.8% | 40.0% | 39 | 40 / 55.0% | 73 / 50.7% |
| expanded_liquid_40 | 39 | 50 | 81.0% | 1.792 | -30.1% | 61.4% | 50.9% | 31.881 | 50.3% | 12.8% | 40.0% | 39 | 40 / 55.0% | 73 / 50.7% |
| expanded_liquid_40 | 39 | 100 | 75.8% | 1.711 | -31.1% | 61.4% | 50.9% | 26.889 | 45.1% | 12.8% | 40.0% | 39 | 40 / 55.0% | 73 / 50.7% |
| expanded_liquid_60 | 59 | 25 | 77.5% | 1.622 | -29.7% | 60.0% | 58.0% | 28.443 | 46.8% | 8.5% | 40.0% | 56 | 72 / 55.6% | 110 / 55.5% |
| expanded_liquid_60 | 59 | 50 | 74.6% | 1.579 | -31.2% | 60.0% | 58.0% | 25.808 | 43.9% | 8.5% | 40.0% | 56 | 72 / 55.6% | 110 / 55.5% |
| expanded_liquid_60 | 59 | 100 | 68.9% | 1.495 | -34.2% | 60.0% | 58.0% | 21.238 | 38.1% | 8.5% | 40.0% | 56 | 72 / 55.6% | 110 / 55.5% |
| original | 59 | 25 | 77.5% | 1.622 | -29.7% | 60.0% | 58.0% | 28.443 | 46.8% | 8.5% | 40.0% | 56 | 72 / 55.6% | 110 / 55.5% |
| original | 59 | 50 | 74.6% | 1.579 | -31.2% | 60.0% | 58.0% | 25.808 | 43.9% | 8.5% | 40.0% | 56 | 72 / 55.6% | 110 / 55.5% |
| original | 59 | 100 | 68.9% | 1.495 | -34.2% | 60.0% | 58.0% | 21.238 | 38.1% | 8.5% | 40.0% | 56 | 72 / 55.6% | 110 / 55.5% |

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
| expanded_all_available | Avoid | 4164 | 77 | 54.9% | 3.0% | -1.746 | 2.400 |
| expanded_all_available | Avoid Chasing | 30 | 20 | 56.7% | 9.1% | 0.815 | 2.533 |
| expanded_all_available | Neutral | 993 | 77 | 55.9% | 4.3% | 0.732 | 2.795 |
| expanded_all_available | Strong Candidate | 87 | 40 | 58.6% | 9.0% | 3.244 | 3.529 |
| expanded_all_available | Watchlist | 116 | 45 | 54.3% | 3.6% | 2.576 | 2.871 |
| expanded_liquid_40 | Avoid | 2080 | 39 | 55.9% | 4.2% | -1.977 | 2.370 |
| expanded_liquid_40 | Avoid Chasing | 10 | 8 | 60.0% | 13.2% | 0.543 | 2.550 |
| expanded_liquid_40 | Neutral | 527 | 39 | 58.4% | 5.4% | 0.792 | 2.781 |
| expanded_liquid_40 | Strong Candidate | 40 | 21 | 55.0% | 6.6% | 3.334 | 3.500 |
| expanded_liquid_40 | Watchlist | 73 | 27 | 50.7% | 3.1% | 2.659 | 2.911 |
| expanded_liquid_60 | Avoid | 3097 | 59 | 56.3% | 3.5% | -1.886 | 2.396 |
| expanded_liquid_60 | Avoid Chasing | 13 | 11 | 53.8% | 11.1% | 0.490 | 2.577 |
| expanded_liquid_60 | Neutral | 838 | 59 | 56.6% | 4.7% | 0.762 | 2.810 |
| expanded_liquid_60 | Strong Candidate | 72 | 36 | 55.6% | 5.8% | 3.241 | 3.521 |
| expanded_liquid_60 | Watchlist | 110 | 40 | 55.5% | 4.7% | 2.546 | 2.855 |
| original | Avoid | 3097 | 59 | 56.3% | 3.5% | -1.886 | 2.396 |
| original | Avoid Chasing | 13 | 11 | 53.8% | 11.1% | 0.490 | 2.577 |
| original | Neutral | 838 | 59 | 56.6% | 4.7% | 0.762 | 2.810 |
| original | Strong Candidate | 72 | 36 | 55.6% | 5.8% | 3.241 | 3.521 |
| original | Watchlist | 110 | 40 | 55.5% | 4.7% | 2.546 | 2.855 |

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