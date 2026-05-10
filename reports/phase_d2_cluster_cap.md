# Phase D2 — AI-Infrastructure Cluster Cap

_2026-05-03. Active baseline (Simplest Robust + gate repair) **unchanged**. New layer: optional cap on cluster `{pcb_substrate, leo_satellite, facility_cleanroom, thermal, ai_server_assembly}` exposure within top-5. Theme cap (max 2 / theme) remains binding underneath._

## TL;DR — cluster cap makes things WORSE on every dimension. Do NOT adopt.

| Variant | CAGR | Sharpe | Calmar | Max DD | Worst Mo | Mo in DD | Longest Recovery |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline (no cluster cap) | 114.4% | 1.92 | 4.72 | -24.25% | -11.6% | 31 | 7 mo |
| **50% cap** (max 2/5) | 101.1% | 1.77 | 3.62 | **-27.95%** ❌ | **-14.5%** ❌ | 35 | 13 mo |
| **60% cap** (max 3/5) | 104.2% | 1.89 | 3.71 | **-28.08%** ❌ | -12.4% | 34 | 12 mo |
| **70% cap** (max 3/5†) | 114.1% | 1.92 | 4.70 | -24.25% | -11.6% | 31 | 7 mo |

† Note on cap interpretation: 70% × 5 = 3.5; rounded to **4** with banker's rounding (`round(3.5)` = 4). With max 4-of-5 it binds only 16/70 months (23%) — practically equivalent to baseline.

**The Phase regime stress §8 hypothesis ("PCB+LEO+facility co-drawdown drives worst months") was MISREAD.** Cluster names appear in worst months because they ARE the high-alpha picks — they appear in *all* months. Capping them just forces lower-quality non-cluster names into the portfolio, which then deliver worse drawdowns in different months.

---

## 1. Cluster definition

Following user spec: 5 themes flagged in Phase regime stress §8 worst-month attribution.

| Cluster theme | # tickers in active universe |
|---|---:|
| pcb_substrate | 10 |
| ai_server_assembly | 7 |
| facility_cleanroom | 4 |
| thermal | 6 |
| leo_satellite | 2 |
| **Total cluster** | **29 / 60 (48% of universe)** |

Half the active universe is in the cluster. That's the first clue something's off — capping ~50% of the universe to ≤ 40% of the portfolio will actively misallocate.

## 2. Per-variant performance (gross, monthly EW top-5)

| Variant | n | CAGR | Sharpe | Calmar | Max DD | Hit | Worst Mo | Mo in DD | Longest Recovery | n DD episodes | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 70 | 114.4% | 1.92 | 4.72 | -24.25% | 67.1% | -11.61% | 31 | 7 | 9 | 8451% |
| 50% cap | 70 | 101.1% | 1.77 | 3.62 | **-27.95%** | 67.1% | **-14.46%** | 35 | 13 | 7 | 5788% |
| 60% cap | 70 | 104.2% | 1.89 | 3.71 | **-28.08%** | 67.1% | -12.41% | 34 | 12 | 7 | 6334% |
| 70% cap | 70 | 114.1% | 1.92 | 4.70 | -24.25% | 67.1% | -11.61% | 31 | 7 | 9 | 8373% |

**Reading:**
- 50% and 60% caps DEEPEN max DD (24.25% → 28%). The cap reduced cluster exposure but the substitute non-cluster names produced worse drawdowns in some months.
- Worst single month under 50% cap is **deeper** (-14.5% vs baseline -11.6%) — the substitution actively hurts.
- 70% cap is essentially baseline (cap rarely binds).
- Hit rate identical across all variants (67.1%) — distribution shape unchanged.

## 3. Cost-adjusted (25 / 50 bps)

| Variant | 25 bps CAGR | 25 bps Sharpe | 50 bps CAGR | 50 bps Sharpe |
|---|---:|---:|---:|---:|
| baseline | 110.7% | 1.88 | 107.0% | 1.84 |
| 50% cap | 97.6% | 1.73 | 94.1% | 1.69 |
| 60% cap | 100.5% | 1.85 | 97.0% | 1.80 |
| 70% cap | 110.4% | 1.88 | 106.7% | 1.84 |

Cost-adjusted ranking is identical to gross — turnover impact is negligible across variants.

## 4. Cluster exposure path

| Variant | Mean cluster weight | Max cluster weight | # months at max |
|---|---:|---:|---:|
| baseline | **50.7%** | 100% | 2 |
| 50% cap | 35.8% | 40% | **57 / 70 (81%)** |
| 60% cap | 45.6% | 60% | 35 / 70 (50%) |
| 70% cap | 50.1% | 80% | 16 / 70 (23%) |

50% cap is binding 81% of the time — the strategy is constantly being pulled away from its preferred allocation. 60% binds half the time. 70% rarely binds.

## 5. Upside sacrifice during AI momentum months

26 months had AI factor index forward return > 5% ("AI momentum months").

| Variant | Baseline mean | Capped mean | Sacrifice / month | Sacrifice total |
|---|---:|---:|---:|---:|
| 50% cap | +16.17% | +15.84% | -0.33 pts | -2.51 pts (compounded) |
| 60% cap | +16.17% | +15.35% | **-0.81 pts** | **-6.03 pts (compounded)** |
| 70% cap | +16.17% | +16.13% | -0.04 pts | -0.38 pts |

Counter-intuitive: 60% cap sacrifices MORE during AI momentum than 50% cap. Reason: each cap forces a different non-cluster substitute, and those substitutes have different forward-return profiles. There's no monotonic "looser cap = less sacrifice" relationship.

The total upside given up (compounded) ranges from ~0.4 pts (70% cap) to ~6 pts (60% cap) over the 26 momentum months. That's the explicit cost in good times.

## 6. Worst-5 months attribution

### Baseline worst 5

| month | port_return | cluster_share | themes |
|---|---:|---:|---|
| 2025-02 | -11.61% | **80%** | ai_server, facility, leo, memory, pcb |
| 2021-04 | -10.96% | 40% | ai_server, inspection, memory, pcb, semi |
| 2023-09 | -10.94% | **80%** | facility, leo, pcb, power_grid |
| 2021-12 | -10.72% | **80%** | ai_server, facility, leo, semi |
| 2025-01 | -8.39% | 60% | facility, leo, optical, pcb |

Cluster share in worst months: 40-80% — wide range. NOT a clear "high-cluster-share = worst month" pattern.

### 50% cap worst 5 (cluster forced ≤ 40%)

| month | port_return | cluster_share | themes |
|---|---:|---:|---|
| **2021-12** | **-14.46%** ❌ | 40% | ai_server, inspection, leo, power_grid, semi |
| 2022-09 | -13.60% ❌ | 40% | ai_server, inspection, optical, semi, thermal |
| 2025-02 | -12.78% ❌ | 40% | facility, indirect, memory, optical, pcb |
| 2023-07 | -12.41% ❌ | 40% | ai_server, optical, semi |
| 2021-04 | -10.96% | 40% | ai_server, inspection, memory, pcb, semi |

**Worst month under 50% cap is DEEPER than baseline worst (−14.5% vs −11.6%)**. Even though cluster was capped at 40%, the substitute names (memory, optical, indirect, inspection, semi) drove a deeper loss.

This is the smoking gun: **the cluster wasn't causing worst-month losses — it was preventing them**. By holding fewer cluster names, the strategy held more non-cluster names that performed worse.

## 7. Why did Phase regime stress mislead us?

Phase regime stress §8 reported: "PCB substrate appears in 4 of 5 worst months; LEO satellite in 4 of 5". This is **a true statement** but I drew the wrong inference.

The right interpretation: cluster themes contain the highest-alpha names → they're in the portfolio almost every month → they appear in worst months *and* best months at similar frequency.

Looking at the regime stress §9 best 5 months:
- 2025-07: facility + pcb + power_grid → cluster ~60%
- 2023-06: ai_server + optical + semi + thermal → cluster ~60%
- 2025-12: facility + memory + semi + thermal → cluster ~40%
- 2025-11: facility + memory + semi + thermal → cluster ~40%
- 2026-03: leo + memory + pcb + semi → cluster ~60%

**Cluster share is similar in best months (40-60%) and worst months (40-80%)** — the cluster doesn't disproportionately drive losses; it drives the strategy in both directions.

## 8. Recommendation: do NOT adopt cluster cap

| Cap level | Verdict |
|---|---|
| 50% (max 2) | ❌ Hurts CAGR -13 pts, Sharpe -0.15, **deepens** Max DD by 3.7 pts, worst month -3 pts deeper |
| 60% (max 3) | ❌ Hurts CAGR -10 pts, Sharpe -0.03, **deepens** Max DD by 3.8 pts |
| 70% (max 4) | ≈ Baseline (cap rarely binds; not worth implementing) |

D2 + D1 together suggest a clear pattern: **simple structural risk-management interventions don't work for this strategy in this regime**. The alpha is structurally tied to AI cluster names; constraining the cluster destroys the alpha.

## 9. Where this leaves us — diagnosis of remaining options

The strategy has **one alpha source (residual_alpha + AI infrastructure cluster names)**. Both D1 (exposure scaling) and D2 (cluster cap) tried to dampen exposure to that source. Both made performance worse on most metrics.

**The drawdown-control problem is harder than expected.** Options that remain (none implemented):

| Option | Pro | Con | Suggested next |
|---|---|---|---|
| **D3: stop-loss at individual position level** | Targets the actual loss event, not the structural exposure | Higher turnover; whipsaw risk; needs intra-month or 2-week rebalance to be effective | Worth testing |
| **D4: regime-anticipatory hedging** (long top-5, short benchmark when regime turns) | Hedges market beta without giving up alpha | Adds short side complexity; benchmark short cost; may underperform in steady bull | Higher engineering cost |
| **D5: time-vol filter on entry** (skip new positions when 60d vol > threshold) | Targets vol increases as DD predictor | Could miss recovery setups | Worth testing |
| **D6: accept DD profile, move to paper portfolio** | The strategy already has Calmar 4.7 and beats benchmark in every regime — DD might just be the price of admission | No further DD reduction | If user accepts current profile |

**My recommendation: option D6 (accept the current DD profile and move to paper portfolio)**, with these caveats:
- Active baseline already has Calmar 4.7 (CAGR 114% / |DD| 24%) — that's an excellent reward-for-risk
- Max DD -24.25% is **deeper than benchmark -29.2% by only 5 pts** under current Step-1 universe (vs original 22-name universe -32%)
- Both D1 and D2 confirmed that the *correlated downside* isn't easily separable from the *correlated upside* — reducing one reduces the other proportionally
- Further DD-reduction work has diminishing returns; better to validate against real execution (paper portfolio) before more engineering

If the user wants one more DD-reduction attempt before paper portfolio, my pick is **D3 (individual stop-loss at e.g. -10% from cost basis)** — it targets the loss event directly rather than the structural exposure, which is probably the only intervention that *could* meaningfully reduce DD without killing alpha.

---

## Files added

**Active code (no scoring / weight / portfolio-construction changes)**
- `src/capex_alpha/validation/cluster_cap.py` — greedy top-N respecting both per-theme cap and cluster cap; cluster exposure path; upside sacrifice diagnostic
- `scripts/run_phase_d2_cluster_cap.py` — CLI

**Tests**
- `tests/test_cluster_cap.py` — 7 tests (cap conversion, greedy logic, exposure path, upside sacrifice)

**Outputs**
- `data/output/phase_d2_summary.csv` — 12 rows (baseline + 3 caps × 1 gross + 2 cost variants)
- `data/output/phase_d2_cluster_exposure_path.csv` — per-rebalance cluster weight per variant
- `data/output/phase_d2_upside_sacrifice.csv` — momentum-month sacrifice per variant
- `data/output/phase_d2_worst_months.csv` — top-5 worst per variant with cluster share
- `reports/phase_d2_cluster_cap.md` — this report

**No model / scoring / dashboard changes.** Active baseline weights, gates, and current portfolio are unaffected.

Tests: **96 / 96 passing** (was 89 + 7 new).

---

## Decision needed

| Option | Action |
|---|---|
| **(a) Recommended — accept current DD profile, move to paper portfolio (D6)** | Active baseline already has Calmar 4.72 and DD-24% which is acceptable for a 114% CAGR strategy in this regime. Further engineering has diminishing returns relative to validating real execution. |
| (b) Try D3 individual stop-loss before paper portfolio | One more attempt at DD reduction; targets actual loss event rather than structural exposure |
| (c) Try D5 vol-filter on entry | Less invasive than stop-loss; skips entries during high-vol periods |
| (d) Stop here for now and review | No more Phase D engineering; revisit later |

My recommendation: **(a)**. D1 and D2 together provided strong evidence that the strategy's alpha and DD are tied to the same structural exposure; further structural interventions are likely to repeat the same pattern (modest DD reduction at large CAGR cost). Paper-portfolio shadow run will reveal real execution issues (slippage, partial fills, rebalance timing) that backtest can't simulate, and inform whether further DD work is even needed.
