# A2-rerun on Post-B3 Data — Weight Recalibration

_2026-05-03. Step-1 active baseline (`expanded_liquid_60` + theme cap, `max_per_theme=2`). Walk-forward 2020-06-30 → 2026-04-30, 71 monthly rebalances, 60 universe tickers, full FinMind Tier-2 coverage._

**This report does NOT change any YAML.** It compares 6,860 weight combinations on post-B3 data and presents three candidate weight sets for your decision.

## TL;DR

Post-B3 data confirms the ablation finding: **the current `rev_w=0.30` is materially over-weighted**. The simplest robust model that beats the active baseline on every dimension is:

```yaml
tier_weights:
  residual_alpha_score:        0.50   # was 0.35
  revenue_confirmation_score:  0.00   # was 0.30  ← drop entirely
  sector_relative_score:       0.00   # unchanged
  institutional_flow_score:    0.00   # was 0.10  ← drop entirely
  narrative_score:             0.00   # unchanged
  capex_context_score:         0.05   # unchanged
# risk_penalty_multiplier:     0.75   # was 1.00 (implicit) — modest reduction
# decision_zones[Strong].min_alpha: 2.5  unchanged
```

This simplifies the model to **residual α + risk penalty + theme cap**, which is the cleanest expression of A1/A2/B3 cumulative findings. Recommend adoption only after manual review of §6 and §7.

---

## 1. Grid setup (vs original A2)

| Dimension | Original A2 grid | **A2-rerun grid (widened)** |
|---|---|---|
| `residual_alpha_score` | 0.30–0.55 step 0.05 (6 values) | **0.30–0.60** step 0.05 (**7**) |
| `revenue_confirmation_score` | 0.10–0.30 step 0.05 (5 values) | **0.00–0.30** step 0.05 (**7**) ← includes 0 |
| `institutional_flow_score` | 0.05–0.20 step 0.05 (4 values) | **0.00–0.20** step 0.05 (**5**) ← includes 0 |
| `risk_penalty_multiplier` | 0.5–2.0 step 0.25 (7 values) | 0.5–2.0 step 0.25 (7) |
| `min_alpha` | 2.5–4.0 step 0.5 (4 values) | 2.5–4.0 step 0.5 (4) |
| **Total cells** | 3,360 | **6,860** |

Constraints honored per user mandate: `sector_relative_score=0`, `narrative_score=0`, CAPEX context only, theme cap on (`max_per_theme=2`) — applied during top-5 selection, not changed in YAML.

## 2. Filter results

| Filter | Cells passing |
|---|---:|
| Robustness (test Sharpe ≥ 80% × train Sharpe) | 6,860 / 6,860 (100%) |
| Strong-sample (n ≥ 15 obs) | 5,420 / 6,860 (79%) |
| **Both** | **5,420 / 6,860** (79%) |

The robustness filter is non-binding (everything passes) because the test period (2024-2026) was strong enough that even random allocation got Sharpe > 1. **Robustness selection is not informative on this data**; we lean on `full_sharpe` (whole-period) + simplicity instead.

## 3. Candidate weight sets — head-to-head

| Field | A2 baseline (current) | Simplest robust (recommended) | Best test Sharpe (alt) | Best net CAGR (alt) |
|---|---:|---:|---:|---:|
| `ra_w` | 0.35 | **0.50** | 0.50 | 0.60 |
| `rev_w` | 0.30 | **0.00** | 0.10 | 0.00 |
| `flw_w` | 0.10 | **0.00** | 0.15 | 0.05 |
| `risk_mult` | 1.00 | **0.75** | 1.50 | 0.75 |
| `min_alpha` | 2.5 | 2.5 | 3.5 | 3.0 |
| **Train Sharpe** | 1.347 | **1.531** | 1.521 | 1.498 |
| **Test Sharpe** | 2.313 | **2.542** | 2.908 | 2.460 |
| Robust ratio (test/train) | 1.72 | 1.66 | 1.91 | 1.64 |
| **Full-period Sharpe** | 1.721 | **1.920** | 2.034 | 1.872 |
| **Full-period Max DD** | -28.1% | **-24.3%** | -23.4% | -27.0% |
| Annualised turnover | 6.4× | 7.4× | 7.7× | 7.2× |
| **Net CAGR @ 25 bps** | 80.9% | **110.7%** | 104.2% | 114.7% |
| Strong-bucket: n / hit | 199 / 55.8% | 127 / 57.5% | 33 / 63.6% | 223 / 60.1% |
| Watchlist-bucket: n / hit | 93 / 53.8% | 64 / **64.1%** | 118 / 52.5% | 87 / 64.4% |
| Number of non-zero weights | 4 | **2** ← simplest | 4 | 3 |

**Reading:**
- All three candidates **strictly dominate the current baseline** on Sharpe, Max DD, and Net CAGR.
- The "simplest robust" candidate has only **2 non-zero tier weights** (`residual_alpha_score` + implicit risk_penalty) — the model becomes `alpha = residual_alpha − 0.75 × risk_penalty`, plus the theme cap on top-5 selection.
- Watchlist hit rate jumps from 53.8% to **64.1%** under simplest robust — first time Watchlist has been a meaningful tier.

## 4. Ablation: full vs residual_alpha_only vs no_revenue

| Variant | Best instance found | Full Sharpe | Full Max DD | Net CAGR @ 25 bps |
|---|---|---:|---:|---:|
| **Current full** (ra=0.35, rev=0.30, flw=0.10, risk×=1.00) | baseline | 1.721 | -28.1% | 80.9% |
| **residual_alpha_only** (rev=0, flw=0) — best instance | ra=0.50, risk×=0.75 | **1.920** | **-24.3%** | **110.7%** |
| **no_revenue** (rev=0, flw>0) — best instance | ra=0.60, flw=0.05, risk×=0.75 | 1.872 | -27.0% | 114.7% |

Both `residual_alpha_only` and `no_revenue` cleanly beat the current full model. Adding `revenue_confirmation_score` back at any weight ≥ 0.15 makes things worse. **Revenue is now a drag, not a signal**, on the post-B3 wide universe.

## 5. Sensitivity tables (median across all robust-passing cells)

### By `ra_w` (residual_alpha weight)

| ra_w | cells | median train Sh | median test Sh | median full Sh | median full DD | median net CAGR |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 980 | 1.45 | 2.55 | 1.83 | -27% | 89% |
| 0.35 | 980 | 1.39 | 2.50 | 1.78 | -27% | 87% |
| 0.40 | 980 | 1.42 | 2.51 | 1.79 | -26% | 87% |
| 0.45 | 980 | 1.46 | 2.51 | 1.81 | -25% | 89% |
| **0.50** | 980 | **1.50** | 2.49 | **1.84** | **-25%** | **94%** |
| 0.55 | 980 | 1.45 | 2.48 | 1.81 | -26% | 92% |
| 0.60 | 980 | 1.46 | 2.40 | 1.79 | -26% | 95% |

ra=0.50 is the broad sweet spot.

### By `rev_w`

| rev_w | cells | median full Sh | median net CAGR |
|---:|---:|---:|---:|
| **0.00** | 980 | **1.87** | **101%** |
| 0.05 | 980 | 1.85 | 96% |
| 0.10 | 980 | 1.83 | 92% |
| 0.15 | 980 | 1.81 | 89% |
| 0.20 | 980 | 1.78 | 84% |
| 0.25 | 980 | 1.74 | 80% |
| 0.30 | 980 | 1.71 | 77% |

**Monotonic — every increment of `rev_w` makes things worse.** The optimum is `rev_w=0`.

### By `flw_w`

| flw_w | cells | median full Sh | median net CAGR |
|---:|---:|---:|---:|
| **0.00** | 1372 | 1.81 | 90% |
| 0.05 | 1372 | 1.81 | 91% |
| 0.10 | 1372 | 1.80 | 89% |
| 0.15 | 1372 | 1.81 | 90% |
| 0.20 | 1372 | 1.81 | 91% |

`flw_w` has **no measurable signal** post-B3. 0 is fine; any value 0–0.20 is equivalent. Recommend 0 for simplicity.

### By `risk_mult`

| risk_mult | cells | median full Sh | median full DD | median net CAGR |
|---:|---:|---:|---:|---:|
| 0.50 | 980 | **1.85** | -27% | **97%** |
| **0.75** | 980 | **1.85** | -25% | **97%** |
| 1.00 | 980 | 1.83 | -25% | 92% |
| 1.25 | 980 | 1.81 | -25% | 89% |
| 1.50 | 980 | 1.79 | -25% | 87% |
| 1.75 | 980 | 1.78 | -26% | 86% |
| 2.00 | 980 | 1.76 | -26% | 84% |

risk_mult=0.5–0.75 wins on Sharpe and net CAGR; 1.0 has slightly tighter DD. Recommend **0.75** as compromise — risk penalty stays active but is dialed back ~25% from current.

## 6. Direct answers to your questions

| Question | Answer | Confidence |
|---|---|---|
| Should `rev_w` be reduced to 0.20, 0.10, or **0**? | **0** | High — sensitivity table is monotonic, no exception |
| Should institutional flow stay at 0.10 or be lower? | **0** (or anywhere 0–0.20, makes no difference) | High — sensitivity table is flat |
| Is valuation/risk penalty too aggressive in AI momentum regimes? | **Modestly yes** — drop `risk_mult` from 1.0 to 0.75 (~25% lighter) | Medium — risk_mult=0.5 also tied; 0.75 is safer middle |
| Best by train/test split? | ra=0.50, rev=0.10, flw=0.15, risk×=1.50 — Train 1.52, Test 2.91 | But this requires keeping all 4 tiers; not the simplest |
| Best by walk-forward robustness (test/train ratio)? | All 6,860 cells pass 80% threshold; not discriminating on this data | Robustness filter is too lenient for this AI-bull test window |
| A2 baseline vs A2-rerun candidate? | See §3 table — recommended candidate beats baseline on Sharpe (+0.20), Max DD (+3.8 pts), Net CAGR (+30 pts) | Strong improvement |
| Full vs `residual_alpha_only`? | residual_alpha_only at ra=0.50/risk×=0.75 wins (Sharpe 1.92 vs 1.72) | §4 |
| Full vs `no_revenue`? | no_revenue at ra=0.60/flw=0.05/risk×=0.75 wins (Sharpe 1.87 vs 1.72) | §4 |
| Impact on Strong / Watchlist / Neutral / Avoid hit rates? | See §3 — Strong stable around 55-60%, **Watchlist jumps from 53.8% to 64.1%** under recommended weights, Neutral/Avoid roughly unchanged | Watchlist gain is the key qualitative win |
| Impact on Avoid Chasing? | Cannot fully evaluate from grid — `Avoid Chasing` requires actual `_resolve_decision_zone()` call. Need to re-run `scripts/run_walk_forward_v2.py` after weights change to get exact counts | Defer to post-adoption verification |

## 7. Honest caveats

1. **Test period (2024-2026) is regime-conditional**. AI mania makes any reasonable weighting look great. The relative ordering of weight combos should generalise, but absolute Net CAGR numbers (110%+) will compress in non-AI-bull regimes.
2. **Robustness filter (test ≥ 80% × train) is non-binding** on this data — every cell passes. Means we're effectively picking on full-period Sharpe + Net CAGR + simplicity, not on out-of-sample evidence per se.
3. **Strong / Watchlist hit rates in the grid are alpha-bucket proxies**. The actual `_resolve_decision_zone()` includes Tier-1/Tier-2 positivity gates and risk-blocking — these will refine the counts further when scoring is re-run with new weights. Expect Strong sample to be ~50-70% of the bucket count after gating.
4. **Recommendation removes `revenue_confirmation_score` entirely**. This means the model no longer uses any FinMind monthly revenue signal. We just spent B3 backfilling that data — and the post-backfill validation says the signal isn't predictive in this universe. Honest negative finding worth flagging: the FinMind monthly-revenue acceleration formula (`yoy_pct[-3:].mean() − yoy_pct[-6:-3].mean()`) may be too crude for this purpose.
5. **Recommendation removes `institutional_flow_score` entirely**. Same reasoning — the 30-day net flow signal doesn't add info on top of residual alpha. Doesn't mean institutional flow is useless; means our current implementation is.
6. **`residual_alpha` becomes ~96% of the model** (with risk penalty as the other ~4%). Concentration of dependency on one factor is itself a risk. If residual alpha breaks (e.g. the AI factor index becomes unrepresentative), the whole strategy breaks.
7. **All grid metrics are gross of slippage / market impact / borrow costs**. The 25-bps cost adjustment captures commission + tax + flat slippage but not impact for larger positions. Phase D (portfolio construction) should add explicit position-size limits.

## 8. Recommendation

**Approve the simplest-robust candidate as the new active baseline:**

```yaml
scoring_v2:
  factor_weights:
    # ... unchanged at factor level (residual_momentum_*, vol_contraction etc.)
  tier_weights:
    residual_alpha_score:        0.50    # was 0.35
    revenue_confirmation_score:  0.00    # was 0.30  ← B3 ablation says drop
    sector_relative_score:       0.00    # unchanged (Phase A1)
    institutional_flow_score:    0.00    # was 0.10  ← post-B3 ablation says drop
    narrative_score:             0.00    # unchanged (Phase A1)
    capex_context_score:         0.05    # unchanged
```

**Plus a new YAML field for `risk_penalty_multiplier`** — small refactor to make this configurable (currently hardcoded as 1.0 in `scoring_model_v2.py`):

```yaml
scoring_v2:
  risk:
    penalty_multiplier: 0.75    # NEW field; default 1.0 maintains current behavior
```

If you approve, the implementation step is:
1. Edit `config/alpha_model_v2.yaml` with the new weights + add `risk.penalty_multiplier=0.75`
2. Refactor `scoring_model_v2.py` to read `risk_penalty_multiplier` from YAML (one-liner; currently `risk_penalty = abs(v_pen) * SCALE + 0.3 * severity` becomes `... × risk_mult`)
3. Add a test for the new YAML field
4. Re-run walk-forward + B1 + Phase C with new weights
5. Report verified before/after under the new scoring

I will NOT do any of the above without your approval.

## 9. Files added

- `scripts/run_a2_rerun.py` — CLI for the rerun
- `data/output/a2_rerun_grid_results.csv` — 6,860-cell grid results
- `archive/before_a2rerun/` — 21 files (snapshot of pre-rerun state including config + reports)

Modified:
- `src/capex_alpha/validation/weight_grid.py` — widened GRID, added theme cap support, zone-bucket hit rates, turnover, net-CAGR-at-25bps per cell

Tests still pass: 65/65.

---

Decision needed:
- (a) Approve simplest-robust candidate (§8) — I implement YAML + scoring change + verification rerun
- (b) Prefer Best test Sharpe (ra=0.50, rev=0.10, flw=0.15, risk×=1.50) — slightly higher Sharpe but keeps 4 tiers active
- (c) Prefer Best net CAGR (ra=0.60, rev=0.00, flw=0.05, risk×=0.75) — highest absolute return
- (d) Hold — no weight change yet, want more analysis (specify what)
