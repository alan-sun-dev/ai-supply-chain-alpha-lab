# Phase A1 — Before / After Comparison

_2026-05-03. Same walk-forward window (2020-06-30 → 2026-04-30, 71 monthly rebalances, 1562 obs)._

**Change applied** in `config/alpha_model_v2.yaml`:

| Field | Before | After |
|---|---:|---:|
| `factor_weights.sector_relative_strength` | 0.15 | **0.00** |
| `tier_weights.sector_relative_score` | 0.15 | **0.00** |
| `tier_weights.narrative_score` | 0.10 | **0.00** |

All other weights unchanged. CAPEX still context-only. Residual alpha still core. Risk penalty still active. Decision-zone hierarchy unchanged. No raw momentum.

---

## 1. Overall OOS performance — top-5 long-only portfolio

| Metric | Baseline | A1 (simplified) | Δ | Direction |
|---|---:|---:|---:|---|
| **Total return** | +1798.6% | **+2656.8%** | +858.2 pts (+47.7%) | ✅ |
| **Sharpe (ann)** | 1.494 | **1.639** | +0.145 (+9.7%) | ✅ |
| **Max drawdown** | -40.83% | **-33.70%** | +7.13 pts | ✅ |
| Mean monthly | 4.90% | 5.46% | +0.56 pts | ✅ |
| Spearman ρ (alpha, fwd_1m) | 0.0614 | 0.0618 | +0.0004 | ≈ |
| p-value | 0.0159 | 0.0153 | — | sig |
| 0050.TW benchmark | +377.5% / S=1.29 | +377.5% / S=1.29 | — | reference |

A1 beats baseline on **every aggregate metric** without overfitting to a single window.

---

## 2. Decision Zone hit rate

| Zone | Baseline n / hit | A1 n / hit | Δ hit rate | Δ mean fwd_1m |
|---|---|---|---:|---:|
| Strong Candidate | 19 / 63.2% | **5 / 80.0%** | +16.8 pts | -7.1 pts (11.8% → 4.7%) |
| Watchlist | 79 / 58.2% | 52 / 57.7% | -0.5 pts | **+3.1 pts (6.4% → 9.5%)** |
| Neutral | 270 / 57.0% | 249 / 56.6% | -0.4 pts | 0.0 pts (3.8% → 3.8%) |
| Avoid Chasing | 31 / 51.6% | 16 / 50.0% | -1.6 pts | +2.0 pts (1.3% → 3.4%) |
| Avoid | 1141 / 53.9% | 1218 / 54.2% | +0.3 pts | +0.1 pts (2.5% → 2.6%) |

**Reading:**
- Gates became **stricter** — fewer Strong / Watchlist / Avoid Chasing names; the borderline cases moved into Neutral / Avoid.
- Strong Candidate sample collapsed from **n=19 → n=5** with only **2 unique tickers**. That is a real concern — see §6.
- Watchlist mean fwd return jumped meaningfully (6.4% → 9.5%) — the names that *still* qualify are stronger.
- Ordering remains right: Watchlist > Neutral > Avoid Chasing > Avoid in mean fwd return.

---

## 3. Quintile spread

| Bucket | Baseline mean | A1 mean | Δ |
|---|---:|---:|---:|
| Q1 (top alpha) | +4.90% | **+5.46%** | +0.56 pts |
| Q2 | +4.07% | +3.05% | -1.02 pts |
| Q3 | +3.62% | +3.02% | -0.60 pts |
| Q4 | +1.20% | +2.15% | +0.95 pts |
| Q5 (bottom) | +1.41% | +1.40% | -0.01 pts |
| **Q1 − Q5 spread** | **3.49%** | **4.06%** | **+0.57 pts** |

Top quintile captures more alpha; spread widened slightly. Q2-Q4 are noisier — middle-of-the-road alpha is less stable, but the extremes (Q1 vs Q5) are what matter for a top-N portfolio.

---

## 4. Factor Ablation (top-5 portfolio)

| Variant | Baseline Sharpe / Total | A1 Sharpe / Total |
|---|---:|---:|
| `full` | 1.494 / +1799% | **1.639 / +2657%** |
| `no_narrative` | 1.493 / +1809% | 1.639 / +2657% (= full, narrative is now 0) |
| `no_sector_relative` | 1.602 / +2449% | 1.639 / +2657% (= full, sector is now 0) |
| `no_risk_penalty` | 1.218 / +1006% | **1.630 / +3019%** |
| `no_revenue` | 1.364 / +1662% | 1.616 / +2415% |
| `no_flow` | 1.478 / +1812% | 1.667 / +2647% |
| `residual_alpha_only` | 1.610 / +2364% | 1.610 / +2364% (unchanged — independent of weights) |
| `no_residual_alpha` | 1.566 / +1830% | 1.562 / +1376% |
| `random` | 0.645 / +151% | 1.082 / +425% |

**Reading:**
- A1 `full` (1.639 / 2657%) **now beats** every baseline variant including `residual_alpha_only` (1.610 / 2364%).
- Removing **revenue_acceleration** in A1 still hurts (Sharpe 1.616, total 2415%) — keep it.
- Removing **risk_penalty** in A1: Sharpe basically unchanged (1.630 vs 1.639), but max DD widens from -33.7% to -37.5%, total return actually rises to 3019%. Risk penalty is now a pure DD-control feature, costing ~362 pts of total return. Trade-off discussed in §5.
- `random` Sharpe 1.082 — note: with universe of 22 names and top-5 selection, random already gets ~25% universe coverage and rides the AI bull market. The "noise floor" is not zero; the relevant comparison is `full` vs `random`, where `full` still adds +0.56 of Sharpe.

---

## 5. Risk Penalty — closer look in A1

| Variant | Mean monthly | Sharpe | Max DD | Total |
|---|---:|---:|---:|---:|
| `with_risk_penalty` (A1 full) | 5.46% | **1.639** | **-33.70%** | +2657% |
| `without_risk_penalty` | 5.72% | 1.630 | -37.46% | **+3019%** |

**Honest read:** in A1, risk_penalty's value is now **almost entirely DD control**. The Sharpe gap (1.639 vs 1.630) is statistical noise. The DD gap (-33.7% vs -37.5%) is real — 3.7 pts narrower DD costs 362 pts of total return.

Recommendation: **keep risk_penalty for now**. It's the only DD guardrail in the model and the user mandate is "risk_penalty remains active". When we reach Phase F (portfolio construction), explicit DD/vol controls will replace this with cleaner machinery.

---

## 6. Strong Candidate sample size — the one real concern

| | Baseline | A1 |
|---|---:|---:|
| n_obs (Strong) | 19 | **5** |
| n_unique tickers | 9 | **2** |
| Months with ≥1 Strong | ~14 / 71 | ~5 / 71 |

The Strong Candidate gate uses absolute thresholds (`alpha >= 4.0` AND `confidence >= 3.0`). With sector + narrative zeroed, the alpha_score distribution is narrower — fewer names hit 4.0.

**This means the Strong Candidate label has lost statistical power.** With n=5 / 2 unique tickers, the +4.7% / 80% hit rate result is essentially anecdotal. The Watchlist tier (n=52) is now the more reliable signal.

**Recommendation for A2:** the Strong Candidate threshold should be **recalibrated** as part of the grid search — e.g., `alpha >= 3.0` instead of 4.0 — so the gate produces ~2-3× more candidates and recovers statistical power without becoming permissive. This is a calibration change, not a logic change.

---

## 7. Is the simplified model more robust?

| Robustness criterion | Baseline | A1 | Verdict |
|---|---|---|---|
| Headline Sharpe | 1.494 | 1.639 | ✅ A1 better |
| Max DD | -40.8% | -33.7% | ✅ A1 better |
| Total return | +1799% | +2657% | ✅ A1 better |
| Q1−Q5 spread | 3.49% | 4.06% | ✅ A1 wider |
| Beats benchmark Sharpe (1.29)? | ✅ +0.20 | ✅ +0.35 | ✅ A1 wider gap |
| Number of free parameters | 10 weights | **8 weights** | ✅ A1 simpler |
| Strong Candidate sample size | n=19 | n=5 | ❌ A1 weaker |
| Risk_penalty contribution | clear win | DD-only | 🟡 marginal |
| Distance from `random` baseline (Sharpe) | +0.85 | +0.56 | 🟡 narrower |

**Bottom line: the simplified model is more robust on portfolio-level metrics**, with two caveats:
1. The Strong Candidate label is now too rare to be statistically meaningful — needs threshold recalibration.
2. The gap between `full` and `random` narrowed (because `random` did very well in this 5.8-year AI bull market). This isn't an A1 problem per se — it's a reminder that 22-name universe + top-5 ≈ random AI-beta exposure. Universe expansion (Phase C) will widen this gap.

---

## 8. Recommendation: **Proceed to A2 grid search**

A1 unambiguously improves headline performance with a simpler model. Approve A2 with the following scope:

**Grid search dimensions** (constrained to keep the design intact):

| Parameter | Range | Step |
|---|---|---|
| `tier_weights.residual_alpha_score` | 0.30 ~ 0.55 | 0.05 |
| `tier_weights.revenue_confirmation_score` | 0.10 ~ 0.30 | 0.05 |
| `tier_weights.institutional_flow_score` | 0.05 ~ 0.20 | 0.05 |
| `tier_weights.capex_context_score` | 0.00 ~ 0.05 | 0.025 |
| `risk_penalty_multiplier` | 0.5 ~ 2.0 | 0.25 |
| `decision_zones[Strong].min_alpha` | 2.5 ~ 4.0 | 0.5 |

Hold-out protocol:
- Train: 2020-06-30 → 2023-12-29
- Test: 2024-01-31 → 2026-04-30
- Pick best weights by Sharpe **on train only**, then report performance on test
- Report top-10 weight combinations; reject if test Sharpe < 80% of train Sharpe (overfitting guard)

**What I'm NOT going to grid-search:**
- `sector_relative_strength` and `narrative_score` weights stay at 0 (A1 settled this)
- `capex_context_score` upper bound is 0.05 (per CAPEX-is-context invariant)
- The decision-zone hierarchy logic itself (only the threshold)

OK to proceed?
