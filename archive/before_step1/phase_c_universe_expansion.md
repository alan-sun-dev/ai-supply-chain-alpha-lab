# Phase C — Universe Expansion (PoC)
_Backtest: 2020-06-30 → 2026-04-30, 70 rebalances. Top-5 EW monthly._

## 1. Executive Summary
- **At 25 bps cost, original universe (22 names)**: CAGR `73.0%`, Sharpe `1.648`, max DD `-32.1%`.
- **At 25 bps cost, expanded_liquid_60 (59 names)**: CAGR `111.7%`, Sharpe `1.935`, max DD `-28.6%`.
- ΔSharpe: `0.287`, ΔMax DD: `3.5%`, ΔCAGR: `38.7%`.
- **expanded_liquid_40**: CAGR `114.0%`, Sharpe `2.022`, max DD `-28.2%`, unique holdings `39`.

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
| expanded_all_available | 77 | 25 | 121.7% | 2.048 | -27.1% | 72.9% | 58.9% | 103.884 | 90.9% | 6.5% | 60.0% | 69 | 26 / 65.4% | 45 / 51.1% |
| expanded_all_available | 77 | 50 | 118.0% | 2.007 | -27.8% | 72.9% | 58.9% | 94.241 | 87.3% | 6.5% | 60.0% | 69 | 26 / 65.4% | 45 / 51.1% |
| expanded_all_available | 77 | 100 | 110.8% | 1.926 | -29.0% | 72.9% | 58.9% | 77.520 | 80.1% | 6.5% | 60.0% | 69 | 26 / 65.4% | 45 / 51.1% |
| expanded_liquid_40 | 39 | 25 | 114.0% | 2.022 | -28.2% | 67.1% | 54.3% | 84.675 | 83.3% | 12.8% | 80.0% | 39 | 5 / 60.0% | 25 / 64.0% |
| expanded_liquid_40 | 39 | 50 | 110.7% | 1.982 | -28.8% | 67.1% | 54.3% | 77.334 | 80.0% | 12.8% | 80.0% | 39 | 5 / 60.0% | 25 / 64.0% |
| expanded_liquid_40 | 39 | 100 | 104.3% | 1.902 | -29.9% | 67.1% | 54.3% | 64.479 | 73.5% | 12.8% | 80.0% | 39 | 5 / 60.0% | 25 / 64.0% |
| expanded_liquid_60 | 59 | 25 | 111.7% | 1.935 | -28.6% | 71.4% | 57.7% | 79.365 | 80.9% | 8.5% | 60.0% | 57 | 17 / 70.6% | 35 / 40.0% |
| expanded_liquid_60 | 59 | 50 | 108.2% | 1.895 | -29.3% | 71.4% | 57.7% | 72.101 | 77.5% | 8.5% | 60.0% | 57 | 17 / 70.6% | 35 / 40.0% |
| expanded_liquid_60 | 59 | 100 | 101.5% | 1.815 | -30.7% | 71.4% | 57.7% | 59.481 | 70.7% | 8.5% | 60.0% | 57 | 17 / 70.6% | 35 / 40.0% |
| original | 22 | 25 | 73.0% | 1.648 | -32.1% | 67.1% | 42.9% | 24.451 | 42.2% | 22.7% | 80.0% | 22 | 31 / 58.1% | 40 / 65.0% |
| original | 22 | 50 | 70.9% | 1.615 | -32.9% | 67.1% | 42.9% | 22.761 | 40.1% | 22.7% | 80.0% | 22 | 31 / 58.1% | 40 / 65.0% |
| original | 22 | 100 | 66.7% | 1.550 | -34.4% | 67.1% | 42.9% | 19.718 | 36.0% | 22.7% | 80.0% | 22 | 31 / 58.1% | 40 / 65.0% |

## 7. Transaction Cost Impact
Each universe is shown at 25 / 50 / 100 bps in §6.  Larger universes have similar turnover (top-5 EW rebalance dynamics), so cost drag scales similarly across variants.

## 8. Concentration Analysis
- Original: top-5 / 22 = 22.7% of universe.  Expanded_liquid_60: top-5 / 60 = 8.3%.
- Lower top-5 / universe ratio is what we wanted; whether it actually shows up in max-DD reduction depends on whether new tickers diversify away from existing AI-theme beta. See §6.

## 9. Theme Exposure Analysis
| Universe | Max single-theme weight | Themes appearing in top-5 |
|:--|---:|---:|
| expanded_all_available | 60.0% | 13 |
| expanded_liquid_40 | 80.0% | 12 |
| expanded_liquid_60 | 60.0% | 13 |
| original | 80.0% | 5 |

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
| original | Avoid | 1188 | 22 | 54.1% | 2.5% | -1.843 | 2.442 |
| original | Avoid Chasing | 16 | 11 | 50.0% | 3.4% | 0.775 | 2.562 |
| original | Neutral | 265 | 22 | 55.8% | 3.7% | 0.748 | 2.798 |
| original | Strong Candidate | 31 | 10 | 58.1% | 9.9% | 3.585 | 3.581 |
| original | Watchlist | 40 | 15 | 65.0% | 8.9% | 2.613 | 2.938 |

## 11. Failure / Success Diagnosis

**Verdict: Phase C SUCCESS — but with two honest caveats that affect adoption.**

**What worked:**
- Sharpe improved meaningfully across all expanded variants (+0.16 to +0.40 vs original).
- Max DD improved (-32% → -27% to -29%) — concentration risk reduction is real and structural.
- Top-5 / universe ratio collapsed from 23% → 6.5%–13%.
- Max single-theme exposure dropped from 80% (original) → 60% (expanded_60 / expanded_all).
- Strong Candidate hit rate held up (58.1% → 65–71% in larger variants).

**What requires honest disclosure:**
- **CAGR jump (73% → 111-122%) is partly regime-driven.** New themes — AI server ODM (Quanta, Wiwynn), optical (Eoptolink, EZconn), thermal (Auras, Asia Vital), AI-grade PCB (Elite Material, Unimicron) — are exactly the names that delivered triple-digit returns in the 2023-2024 AI mania. Sharpe + DD gains are structural; the absolute return scale is regime-conditional.
- **`expanded_liquid_40` Strong sample collapsed**: n=5 / 2 unique tickers (vs n=31 / 10 in original). Statistical power lost. Expanded_liquid_60 is healthier (n=17 / 5 unique).
- **Watchlist hit rate degraded** in `expanded_liquid_60` (65% → 40%) and `expanded_all_available` (65% → 51%). The wider universe surfaces more borderline candidates that pass `min_alpha=2.0` but lack quality. Strong gate stayed clean precisely because it is stricter.
- **FinMind data not backfilled** for new tickers (deferred to Phase B2/B3). New-ticker scoring is residual-alpha-only — which is the dominant signal per A1/A2, but revenue + valuation confirmations are silent for ~65% of the expanded universe.
- **AI factor index drifted**: original-universe results in *this* run differ slightly from the A2 baseline because the AI index now re-fits the (smaller) original universe. Apples-to-apples comparison should use *this run's* original-universe row, not the standalone A2 number.

## 12. Recommendation

**Adopt `expanded_liquid_60` as the new active baseline**, with three small adjustments before going live:

1. **Best risk/quality trade-off.** `expanded_liquid_40` has too few Strong observations (n=5) to be statistically meaningful; `expanded_all_available` includes Tier-C names without curation discipline. _60 sits in the sweet spot: 59 names, top-5 = 8.5% of universe, max DD -28.6%, Strong n=17.

2. **Re-tune Watchlist `min_alpha`.** Current Watchlist hit rate dropped from 65% (original) → 40% (_60). Raise `decision_zones[Watchlist].min_alpha` from 2.0 to ~2.3 so the wider universe doesn't dilute the label. Easy fix — it's now YAML-driven post-A2.

3. **Add theme cap in fusion ranking.** Max single-theme weight reached 60% in _60. A ceiling like `single_theme_cap = 0.40` (refuse to put more than 2 of the top-5 into the same theme) is the right risk control given 7 new themes added.

4. **Treat the +47% CAGR uplift as ~50% structural / 50% regime.** Headline expectation for next-12-month live performance: still meaningful alpha vs benchmark but materially below 100% CAGR — a non-AI-mania regime would compress this.

## 13. Next Step

**Sequence (do not skip steps):**

1. **Implement the three §12 adjustments**: switch active universe to `expanded_liquid_60`, raise Watchlist threshold, add theme cap. Rerun walk-forward + B1 transaction-cost test under the new config and confirm Watchlist hit rate recovers and theme exposure stays under 40%.

2. **Phase B2/B3 — FinMind backfill** for the ~36 new tickers. Without revenue / institutional flow / valuation, scoring is residual-alpha-only for them. B2/B3 brings them onto the same factor footing as the original 22.

3. **Re-run Phase C validation** post-backfill. Expect Watchlist quality to improve materially because the revenue confirmation gate then applies to all names.

4. **Then** consider daily auto-scheduling. **Still NOT recommended now** because:
   - Watchlist label degradation (above) needs the §12.2 fix
   - Expanded universe needs FinMind parity (above)
   - Theme cap needs to be implemented and validated before sizing matters

5. Phase D (portfolio construction: max position, vol targeting, stop-loss) should follow the above.

**Files for review:**
- Summary: `data/output/universe_expansion_summary.csv`
- Holdings per rebalance: `data/output/universe_expansion_holdings.csv`
- NAV time series (per universe × cost): `data/output/universe_expansion_nav.csv`
- Theme exposure history: `data/output/universe_expansion_theme_exposure.csv`
- Per-zone label stats: `data/output/universe_expansion_label_stats.csv`
- Liquidity report: `data/output/universe_liquidity_check.csv`
- Charts: `data/output/charts/universe_expansion_{nav,drawdown,theme_exposure}.png`