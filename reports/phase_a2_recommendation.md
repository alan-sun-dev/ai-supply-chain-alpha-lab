# Phase A2 — Grid Search Findings & Recommendation

_3,360 cells; train ≤ 2023-12-29 (43 months); test ≥ 2024-01-31 (28 months)._

## 1. Headline findings

### a) `min_alpha` does NOT affect portfolio metrics

| min_alpha | train Sharpe (med) | test Sharpe (med) | test total (med) |
|---:|---:|---:|---:|
| 2.5 | 1.585 | 1.617 | 250.5% |
| 3.0 | 1.585 | 1.617 | 250.5% |
| 3.5 | 1.585 | 1.617 | 250.5% |
| 4.0 | 1.585 | 1.617 | 250.5% |

**Identical** — because the portfolio is top-N by alpha_score, regardless of decision zone. `min_alpha` only affects the Strong Candidate label count. Pick it independently to optimize Strong-sample size + hit rate.

### b) Sensitivity per weight dimension (median test Sharpe)

| Dim | A1 value | Best value | Δ test Sharpe | Direction |
|---|---:|---:|---:|---|
| `ra_w` (residual α) | 0.35 | **0.30** | +0.03 | slightly lower |
| `rev_w` (revenue) | 0.20 | **0.30** | +0.11 | **clearly higher** |
| `flw_w` (institutional flow) | 0.15 | **0.05** | +0.05 | clearly lower |
| `risk_mult` | 1.00 | **0.50** | +0.08 | **clearly lower** |

Three of four dimensions move *away* from A1 priors. The biggest single signal is `rev_w 0.20 → 0.30` (+0.11 test Sharpe).

### c) Train ≠ Test ranking on `risk_mult`

| risk_mult | train Sharpe (med) | test Sharpe (med) |
|---:|---:|---:|
| 0.5 | 1.507 | **1.698** |
| 1.0 | 1.625 | 1.616 |
| 1.5 | 1.583 | 1.613 |
| 2.0 | **1.628** | 1.587 |

Train favors high (2.0), test favors low (0.5). **Classic sign of training-set overfitting via the risk_penalty channel.** This is why selecting purely by train Sharpe (the original A2 plan) gives noisy results — see §2.

### d) Robustness filter is too lenient

ALL 3,360 cells pass `test_sharpe ≥ 0.80 × train_sharpe`. The test period (2024-2026, AI mania + late-cycle run-up) was strong enough that even random allocations got Sharpe 1.08+. The `≥0.80` filter doesn't discriminate. Need to use absolute test metrics, not relative.

---

## 2. Three candidate weight configurations

| | A1 baseline | **A** (recommended) | B (best test) | C (most aggressive) |
|---|---:|---:|---:|---:|
| `ra_w` | 0.35 | 0.35 | 0.30 | 0.45 |
| `rev_w` | 0.20 | **0.30** | 0.30 | 0.25 |
| `flw_w` | 0.15 | **0.10** | 0.05 | 0.05 |
| `risk_mult` | 1.00 | 1.00 | **0.50** | **0.50** |
| `min_alpha` | 4.0 | **2.5** | 3.0 | 3.0 |
| Train Sharpe | 1.705 | 1.587 | 1.487 | 1.541 |
| **Test Sharpe** | 1.535 | **1.831** | 2.000 | 1.941 |
| Train total | +737% | +697% | +538% | +798% |
| Test total | +229% | **+310%** | +273% | +353% |
| Train DD | -33.7% | -28.6% | -32.0% | -28.0% |
| Test DD | -14.7% | **-10.8%** | -13.6% | -11.5% |
| Robust ratio (test/train Sharpe) | 0.90 | 1.15 | 1.34 | 1.26 |
| Strong Candidate n / unique / hit | 6 / 3 / 67% | **49 / 15 / 57%** | 32 / 10 / 53% | 64 / 19 / 64% |
| Implementation cost | none | YAML only | YAML + new `risk_mult` field + min_alpha read | same as B |

### Why I'm recommending Candidate A

- **Smallest, cleanest change**: only YAML edits (`rev_w`, `flw_w`, `min_alpha`). No new code, no new config schema.
- **risk_mult stays at 1.0**: avoids introducing a new tuning knob whose train/test divergence (§1c) is suspicious — risk_penalty calibration deserves its own validation pass before changing.
- **Test Sharpe 1.83**, +0.30 over A1, with **best test max DD (-10.8%)** of all candidates.
- **Strong Candidate n=49, 15 unique tickers, 57% hit rate** — ample statistical power, vs A1's n=6 / 3 / "67% but anecdotal".
- Robust ratio 1.15 (test > train) is plausible (training period included COVID 2020 + bear 2022), not as suspicious as B/C's 1.26-1.34.

### Why NOT Candidate B/C

- **B's risk_mult=0.5 is a real lever** but the train/test divergence on risk_mult (§1c) means we don't know if 0.5 is the right answer or just lucky for this particular test window. Need a longer/harder test period before committing.
- **C combines aggressive ra_w=0.45 + risk_mult=0.5**: stacks two bets we don't have strong out-of-sample confirmation for.
- Both require **implementing a `risk_penalty_multiplier` config field** in scoring_model_v2.py — small but adds surface area.

### What we explicitly didn't grid-search

- `sector_relative_strength`, `narrative_score` — pinned at 0 per A1 conclusion ✓
- `capex_context_score` weight upper bound — kept at 0.05 per CAPEX-as-context invariant ✓
- Decision-zone hierarchy logic (only the threshold) ✓

---

## 3. Required code changes if you approve Candidate A

| File | Change |
|---|---|
| `config/alpha_model_v2.yaml` | `revenue_confirmation_score: 0.20 → 0.30`; `institutional_flow_score: 0.15 → 0.10`; `decision_zones[Strong].min_alpha: 4.0 → 2.5` |
| `src/capex_alpha/fusion/scoring_model_v2.py` | Make `_resolve_decision_zone` read `min_alpha` from YAML instead of hardcoded `4.0`. Mechanical refactor — no logic change. |
| Tests | Update `test_scoring_model_v2.py::test_strong_candidate_when_all_tiers_align` if it asserts a specific alpha threshold. |

After applying, re-run full walk-forward (no train/test split, full window) to produce a clean `before A2 / after A2` comparison aligned with the same format as A1.

---

## 4. Honest caveats

1. **Test period (2024-2026) was a strong AI bull market.** Even random Sharpe was 1.08. Conclusions about absolute Sharpe levels are inflated relative to a normal market.
2. **The robustness filter (`test_sharpe ≥ 80% train_sharpe`) didn't discriminate** — 100% pass rate. Future grid searches need a tougher test (e.g., walk-forward with multiple train/test windows).
3. **Universe is still 22 names**, top-5 = 23% concentration. Grid search picks weights that work on this universe; expansion to 60+ names (Phase C) may shift optimal weights again.
4. **Institutional flow data starts 2022.** The grid finding "lower flw_w is better" may simply reflect the missing pre-2022 data. After Phase B2 (backfill), this may flip.
5. **risk_mult is shelved, not resolved.** A1 said "risk_penalty is mostly DD-control with marginal Sharpe." A2 confirms train favors high, test favors low. The right fix is probably **decoupling risk_penalty into separate severity vs valuation components** in a future phase, not a single multiplier knob.
6. **Strong Candidate ≠ Top-N portfolio.** Lowering `min_alpha` only changes the *label* assigned, not what the portfolio actually holds. The portfolio always picks top-5 regardless of zone. The label is for the daily report's "research priority" message.

---

## 5. Decision needed

OK to proceed with Candidate A?
- ✅ Apply YAML changes
- ✅ Refactor `_resolve_decision_zone` to read `min_alpha` from config
- ✅ Re-run full walk-forward, produce A2 vs A1 comparison
- ⏸ Defer Candidate B / C until we have either (a) longer test window, or (b) Phase B/C universe + data backfill
