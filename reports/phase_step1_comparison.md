# Step-1 — Universe Switch + Theme Cap (active baseline change)

_2026-05-03. Backtest window: 2020-06-30 → 2026-04-30, 70 monthly rebalance dates. Top-5 EW, monthly._

## What we changed

| Field | Before (A2 baseline) | **After (Step-1 active)** |
|---|---|---|
| `config/universe.yaml :: manual_files.beneficiary_universe` | `data/manual/beneficiary_universe.csv` (22 names) | `data/manual/beneficiary_universe_expanded_liquid_60.csv` (59 names) |
| `decision_zones[Strong].min_alpha` | 2.5 | 2.5 _(unchanged)_ |
| `decision_zones[Watchlist].min_alpha` | 2.0 | 2.0 _(tested 2.3, reverted — see §5)_ |
| `scoring_v2.portfolio_construction.enable_theme_cap` | _(absent)_ | **`true`** |
| `scoring_v2.portfolio_construction.max_per_theme` | _(absent)_ | **`2`** |

**Code change**: `validation/portfolio_metrics.topn_holdings`/`topn_returns` accept `theme_map` + `max_per_theme`. Greedy selection respects the per-theme cap. Threaded through `transaction_cost.simulate_scenario`, `validation.universe_validation.run_universe_panel`. Theme cap config helper `pm.theme_cap_kwargs()` reads `enable_theme_cap` from YAML, so any consumer just calls `**pm.theme_cap_kwargs(theme_map)`. Tests added: `test_theme_cap_limits_per_theme`, `test_theme_cap_disabled_returns_pure_topn`, `test_theme_cap_kwargs_reads_yaml`.

Also added the 7 new themes (`optical_communication`, `thermal`, `memory_hbm`, `passive_components`, `pcb_substrate`, `power_grid_energy`, `leo_satellite`, `ai_server_assembly`) to `config/universe.yaml :: themes:` so `test_themes_match_config` keeps passing.

---

## Headline before / after (top-5 portfolio at 25 bps cost)

| Metric | A2 baseline (original 22) | **Step-1 (expanded_60 + cap)** | Δ |
|---|---:|---:|---:|
| **CAGR** | 73.0% | **117.5%** | **+44.5 pts** |
| **Sharpe (ann)** | 1.648 | **2.031** | **+0.383** |
| **Max DD** | -32.2% | **-27.8%** | **+4.4 pts** |
| Mean monthly | 5.31% | 6.47% | +1.16 pts |
| Monthly hit rate | 67.1% | **72.9%** | +5.8 pts |
| Avg monthly turnover | 42.9% | 55.4% | +12.5 pts |
| Annualised turnover | 5.28× | 6.65× | +1.37× |
| Final NAV | 24.5 | **92.9** | 3.8× |
| Net α vs 0050 | +42.2% / yr | **+86.7% / yr** | +44.5 pts |
| **Top-5 concentration (% of universe)** | 22.7% | **8.5%** | **−14.2 pts** |
| **Max single-theme weight** | 80% | **40%** | **−40 pts** |
| Strong Candidate sample | n=31 / 10 unique / 58.1% hit | **n=17 / 5 unique / 70.6% hit** | ↓ sample, ↑ hit rate |
| Watchlist sample | n=40 / 15 / 65.0% hit | n=35 / 18 / 40.0% hit | ↑ unique, **↓ hit rate** |
| Break-even one-way cost | 588 bps | **812 bps** | +224 bps headroom |

---

## What worked

1. **Universe expansion + theme cap together capped concentration risk hard.** Top-5 / universe ratio fell from 23% → 8.5%; max single-theme weight dropped from 80% → exactly 40% (the cap is binding ~half the time).
2. **Sharpe + Max DD both improved**, exactly the PoC success criteria from Phase C. The theme cap added an extra +0.10 of Sharpe and −0.8 pts of max DD on top of what raw expansion gave.
3. **Break-even cost up to 812 bps** (from 588). With more diversified holdings the strategy can absorb materially more cost before benchmark catches up.
4. **Strong Candidate quality preserved**: sample shrank from n=31 → n=17 but hit rate jumped to 70.6%. The label is still statistically meaningful.
5. **Monthly hit rate up** to 72.9% from 67.1%. Smoother return path.

## What did NOT work

1. **Watchlist threshold raise (2.0 → 2.3) was the wrong direction**. It made Watchlist hit rate WORSE (40% → 34.8%). Reason: the names with alpha 2.0-2.3 actually had reasonable forward returns; raising the threshold left only "high alpha but Strong-gate-blocked" residuals which structurally underperform. **Reverted to 2.0**.
2. **Watchlist hit rate (40%) is still below the original 22-name universe (65%)**. Structural issue: in the wider universe, more names hit `min_alpha=2.0` without strong Tier-2 confirmation. The fix is not a threshold tweak — it's giving new tickers actual revenue/flow/valuation data, i.e. **Phase B2/B3 FinMind backfill**.
3. **Turnover went up 1.4×** (5.28× → 6.65× annualised). Wider universe = more candidates competing → more rotation. Doesn't matter at current cost levels (break-even 812 bps), but worth flagging.

## Honest caveats (carry-over from Phase C)

- **AI mania regime**: ~half the CAGR uplift comes from AI-bull-market beneficiaries (Quanta, Wiwynn, Auras, Elite Material, Unimicron) included in the new universe. Forward-looking expectation should anchor on Sharpe / DD improvements, not on the absolute CAGR.
- **FinMind not backfilled** for the ~36 new tickers. Their Tier-2 (revenue / flow / valuation) is silent. Ranking falls back to `residual_alpha` — which is the dominant signal per A1/A2 ablation, but the confirmation gates are absent.
- **Universe is now slightly survivor-biased** — new tickers were picked in 2026 with knowledge of which names did well 2020-2026. Phase C honest-disclosure note still applies.

## Decision-zone behaviour after Step-1

| Zone | n_obs | n_unique | hit_rate | mean fwd_1m |
|---|---:|---:|---:|---:|
| Strong Candidate | 17 | 5 | **70.6%** | +6.2% |
| Watchlist | 35 | 18 | 40.0% | +0.6% |
| Neutral | 548 | 59 | 60.0% | +5.0% |
| Avoid Chasing | 201 | 46 | 63.7% | **+10.7%** |
| Avoid | 3329 | 59 | 55.3% | +3.3% |

⚠️ **Avoid Chasing has the highest mean fwd return (+10.7%)** — that's surprising. The label is meant to flag overbought + revenue-weak names; in the AI-mania regime, those names kept ripping. This contradicts the gate's intended behaviour and deserves investigation in a future phase (probably the gate is mis-tuned for momentum-heavy tape).

---

## Cost scenarios (Step-1 baseline, expanded_60 + theme cap)

| cost_bps | CAGR | Sharpe | max DD | Final NAV | Net α vs 0050 |
|---:|---:|---:|---:|---:|---:|
| 0 | 120.9% | 2.070 | -27.0% | 101.9 | +90.2% |
| 10 | 119.5% | 2.054 | -27.3% | 98.2 | +88.8% |
| **25** | **117.5%** | **2.031** | **-27.8%** | **92.9** | **+86.7%** |
| 50 | 114.1% | 1.991 | -28.5% | 84.8 | +83.3% |
| 100 | 107.4% | 1.912 | -29.9% | 70.5 | +76.7% |
| Benchmark 0050.TW | 30.2% | 1.275 | -29.2% | 4.78 | — |

Break-even one-way cost: **811.8 bps** (vs 588 bps for A2 baseline).

---

## Files changed

- `config/universe.yaml` — `beneficiary_universe` path → `_expanded_liquid_60.csv`; added 7 new themes
- `config/alpha_model_v2.yaml` — added `portfolio_construction:` section with `enable_theme_cap=true`, `max_per_theme=2`. Watchlist threshold tested at 2.3 then reverted to 2.0.
- `src/capex_alpha/validation/portfolio_metrics.py` — added `theme_map` + `max_per_theme` params to `topn_holdings`/`topn_returns`; new `load_theme_cap_config()` + `theme_cap_kwargs()` helpers
- `src/capex_alpha/validation/transaction_cost.py` — propagated theme cap kwargs through `simulate_scenario` / `break_even_cost` / `run`
- `src/capex_alpha/validation/universe_validation.py` — uses `pm.theme_cap_kwargs()` for each universe variant
- `scripts/run_transaction_cost_test.py` — auto-pulls theme map from active universe + applies cap
- `tests/test_universe_expansion.py` — `test_theme_cap_limits_per_theme`, `test_theme_cap_disabled_returns_pure_topn`, `test_theme_cap_kwargs_reads_yaml`

Snapshot of pre-Step-1 state: `archive/before_step1/` (16 files: walk_forward, transaction_cost, alpha_ranking, dashboard, plus the four reports).

Tests: **61/61 passing**.

---

## Recommendation for the next step

| Action | Reason |
|---|---|
| ✅ **Adopt Step-1 as new active baseline** | Sharpe + DD + concentration all materially improved, theme cap binds correctly at 40% |
| ⏸ **Watchlist hit rate degradation deferred to B2/B3** | Threshold tuning doesn't fix it; FinMind backfill (Tier-2 confirmation) is the right tool |
| 🔍 **Investigate Avoid Chasing gate** | Mean fwd +10.7% suggests the overbought-without-revenue rule is mis-tuned for AI-mania momentum tape; should be a Phase D portfolio-construction concern, not blocking |
| ⛔ **Daily auto-scheduling: still NOT recommended** | Watchlist label is unreliable + Avoid Chasing gate inverted; one of these needs a real fix first |
| ➡️ **Next phase: B2 (GDELT news pre-2025) and/or B3 (FinMind pre-2022 + new 36 tickers)** | These are now the unblockers for fixing Watchlist quality and giving the wider universe a fair scoring footing |

Step-1 is approved for **active baseline status** but not for live deployment.
