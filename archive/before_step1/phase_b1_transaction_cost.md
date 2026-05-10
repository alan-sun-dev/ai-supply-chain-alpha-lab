# Phase B1 — Transaction Cost Test (A2 active baseline)
_Window: 2020-06-30 → 2026-03-31, 70 monthly rebalances. Top-5 long-only equal-weight, monthly rebalance._

## 1. Executive Summary
- A2 strategy at **0 bps** (gross): CAGR `75.11%`, Sharpe `1.681`, max DD `-31.40%`, final NAV `26.265`.
- At **100 bps** (highest cost tested): CAGR `66.72%`, Sharpe `1.550`, final NAV `19.718`.
- **0050.TW benchmark**: CAGR `30.24%`, Sharpe `1.275`, max DD `-29.19%`.
- **Break-even one-way cost: ~588 bps** (strategy net CAGR equals benchmark CAGR at this cost).

## 2. A2 Baseline Recap
From `reports/phase_a2_comparison.md`:
- `revenue_confirmation_score`: 0.30 (was 0.20 in A1)
- `institutional_flow_score`: 0.10 (was 0.15)
- `decision_zones[Strong].min_alpha`: 2.5 (was 4.0)
- `sector_relative_score`, `narrative_score` pinned at 0; CAPEX context ≤ 0.05
- A2 gross (Sharpe 1.681 / max DD -31.4% / Strong n=31) is the baseline this report tests against transaction costs.

## 3. Transaction Cost Assumptions
- `one_way_turnover_t` = fraction of top-5 names replaced at rebalance t (equivalent to `0.5 × Σ |Δweight|` for equal-weight portfolios).
- `monthly_cost_t = one_way_turnover_t × one_way_cost_bps / 10000`.
- `net_return_t = gross_return_t − monthly_cost_t`.
- Initial month: 100% turnover charged (cash → fully invested). Marked `initial_position_turnover`.
- This treats `one_way_cost_bps` as cost-per-unit-of-rotated-portfolio. Real-world Taiwan retail (commission + 0.30% sell tax + slippage) ≈ 60-90 bps; institutional ≈ 25-50 bps.

## 4. Net Performance by Cost Scenario
| cost_bps | CAGR | Sharpe | Vol (ann) | Max DD | Hit | Avg mo turnover | Cost drag/yr | Final NAV | Net α vs 0050 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 75.11% | 1.681 | 38.04% | -31.40% | 67.14% | 42.86% | 0.00% | 26.265 | 44.38% |
| 10 | 74.26% | 1.668 | 38.03% | -31.70% | 67.14% | 42.86% | 0.51% | 25.524 | 43.52% |
| 25 | 72.98% | 1.648 | 38.02% | -32.15% | 67.14% | 42.86% | 1.29% | 24.451 | 42.24% |
| 50 | 70.87% | 1.615 | 38.00% | -32.89% | 67.14% | 42.86% | 2.57% | 22.761 | 40.13% |
| 100 | 66.72% | 1.550 | 37.96% | -34.36% | 67.14% | 42.86% | 5.14% | 19.718 | 35.98% |

## 5. NAV Comparison
See `data/output/charts/transaction_cost_nav.png` (log-scale time series).
Each cost scenario has its own NAV column in `data/output/transaction_cost_nav.csv`.

## 6. Break-even Cost Analysis
Binary-search result: **587.6 bps** (net CAGR equals benchmark `30.24%` at this cost).

Interpretation:
- A break-even of **588 bps** is well above realistic Taiwan retail costs (60-90 bps round-trip in this convention) and far above institutional desks (25-50 bps). The strategy retains positive net alpha at any plausible cost level.

## 7. Turnover Analysis
- Average monthly one-way turnover: **42.86%** (top-5 EW)
- Annualized: **5.14×** (514% of portfolio rotated per year)
- This is moderate by quant standards. With only 5 holdings, even one name change = 20% turnover, so the headline number is high but the absolute trade count per month is small (≈2 names).

## 8. Investability Assessment
**Verdict: investable across the full retail-to-institutional cost spectrum.**

- **0 bps** → net CAGR 75.11% (44.38% vs benchmark) — still beats benchmark with healthy margin.
- **10 bps** → net CAGR 74.26% (43.52% vs benchmark) — still beats benchmark with healthy margin.
- **25 bps** → net CAGR 72.98% (42.24% vs benchmark) — still beats benchmark with healthy margin.
- **50 bps** → net CAGR 70.87% (40.13% vs benchmark) — still beats benchmark with healthy margin.
- **100 bps** → net CAGR 66.72% (35.98% vs benchmark) — still beats benchmark with healthy margin.

## 9. Recommendations
- **Keep monthly rebalance** at this stage. Annualized turnover ~5× is acceptable given the cost headroom.
- **Do NOT add a turnover cap or top-N buffer yet** — break-even cost shows the strategy can absorb meaningful friction.
- **Skip rebalance optimisation** (only-rebalance-when-rank-changes-materially / quarterly rebalance) — premature; would trade simplicity for marginal cost savings.
- **DO add a real cost line** to the daily report (e.g. `Strategy NAV (gross) | NAV at 25 bps | NAV at 50 bps`) so the user always sees the realistic number.
- **Future B-phase work**: when universe expands (Phase C → 60+ names), top-5 will be a smaller fraction — turnover dynamics may shift, so re-test then.

## 10. Next Step
- Phase B1 confirms the strategy survives realistic transaction costs comfortably. No urgent need for turnover-reduction work.
- Recommended next phases (in priority order):
  - **Phase B2 / B3** (data backfill: GDELT news pre-2025, FinMind institutional flow pre-2022) — would let us re-run ablation on `narrative_score` and `institutional_flow_score` with full coverage.
  - **Phase C** (universe expansion) — bigger payoff for risk reduction (top-5 of 60+ = much lower concentration than top-5 of 22).
  - Daily auto-scheduling can wait until either B2/B3 or C lands.