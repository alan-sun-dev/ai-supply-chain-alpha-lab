# ai-supply-chain-alpha-lab

> Daily AI Supply Chain Alpha Discovery & Ranking Platform.
> Pure v2 fork — clean repo, no legacy CAPEX-event code.

---

## 0. Disclaimer

研究框架，**不構成投資建議**。Strong Candidate 是研究優先順序，不是 buy 訊號。
原始假說「TSMC CAPEX guidance 上修可預測供應鏈受益股報酬」已在前一階段實證下被拒絕（event-driven p=0.67）；本平台**不再**以 CAPEX 作為交易 trigger，CAPEX 僅作為 context（權重上限 ±0.5）。

---

## 1. Lineage

| | Repo | Purpose |
|---|---|---|
| v1 | `~/tsmc-capex-alpha-lab/` | CAPEX event-study + 5 個獨立驗證實驗（已完成） |
| **v2 (this)** | `~/ai-supply-chain-alpha-lab/` | Daily AI supply chain alpha ranking platform |

Shared assets carried over from v1：
- `data/manual/` — universe, monthly revenue, institutional flow, valuation, news, CAPEX events
- `data/raw/yfinance/` — price cache (parquet)
- `src/capex_alpha/{data_loader,universe,utils}.py` — common loaders
- 部分 fetch scripts（FinMind / GDELT / SEC EDGAR）

---

## 2. Architecture

```
src/capex_alpha/
├── quant/                      # Tier 1 + Tier 2
│   ├── ai_factor_index.py      # 6 themes + aggregate AI index
│   ├── residual_alpha.py       # rolling β_market, β_ai → residual return
│   ├── factor_model_v2.py      # 10 z-scored factors (no raw momentum)
│   ├── regime_filter.py        # market + AI regime → exposure
│   └── risk_model.py           # per-stock risk flags
│
├── narrative/                  # Tier 3
│   ├── news_parser.py          # GDELT → per-ticker narrative_score
│   ├── capex_interpreter.py    # CAPEX event → context tag (capped ±0.5)
│   ├── transcript_parser.py    # placeholder; lexicon stub
│   ├── tech_signal_classifier.py
│   └── narrative_scorer.py     # combine news + capex + transcript
│
├── fusion/                     # Tier 1+2+3+4 → final score
│   ├── signal_hierarchy.py     # tier gates (Strong / Watchlist / Narrative)
│   ├── scoring_model_v2.py     # alpha_score + decision_zone
│   └── alpha_ranking.py        # ranking + theme_ranking + watchlist
│
├── dashboard/
│   ├── dashboard_data.py       # JSON payload for any UI surface
│   └── daily_report_generator.py
│
├── automation/
│   └── run_daily_pipeline.py   # 9-step orchestrator
│
└── validation/                 # walk-forward + ablation + stress + portfolio research
    ├── walk_forward_v2.py
    ├── ablation.py             # incl. gate_attribution (zone-filter apples-to-apples)
    ├── validation_report.py
    ├── regime_stress.py        # calendar / event regime stress
    ├── cluster_cap.py          # AI-cluster joint exposure cap research
    ├── exposure_overlay.py     # regime → recommended_gross_exposure
    ├── portfolio_metrics.py
    ├── transaction_cost.py
    ├── universe_validation.py
    └── weight_grid.py          # tier-weight grid sweeps

src/capex_alpha/
├── data_loader.py              # yfinance cache w/ business-day TTL + stale fallback (2026-05-10)
├── data_quality.py
├── paper_portfolio.py          # paper-only rebalance / NAV / cost estimation
└── universe_expansion.py       # candidate liquidity check + theme attribution
```

`config/`:
- `alpha_model_v2.yaml` — factor weights, tier weights, decision zones, caps
- `narrative_keywords.yaml` — theme ↔ keyword dictionary
- `theme_mapping.yaml` — narrative tag → universe theme attribution
- `regime_rules.yaml` — regime cascade thresholds + exposure
- `dashboard_config.yaml` — JSON & report output paths
- `universe.yaml`, `data_sources.yaml` — shared with v1

---

## 3. Quick start

```bash
cd ~/ai-supply-chain-alpha-lab
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Daily ranking pipeline — refreshes stale yfinance cache by default
# (cache TTL = 1 business day; auto-fetches when stale, otherwise uses cache)
.venv/bin/python scripts/run_daily_pipeline.py

# Offline / dev: force-skip refetch and use whatever cache is on disk
.venv/bin/python scripts/run_daily_pipeline.py --skip-fetch

# Walk-forward validation
.venv/bin/python scripts/run_walk_forward_v2.py
```

Outputs land in `data/output/` and `reports/`:
- `data/output/alpha_ranking.csv` — primary ranking
- `data/output/dashboard_data.json` — UI payload
- `reports/daily_alpha_report.md` — human report
- `reports/walk_forward_v2_summary.md` — validation report

---

## 4. Daily pipeline — what it does

```
[1/9] Build AI factor index           → ai_factor_index.csv
[2/9] Compute residual alpha          → residual_alpha.csv
[3/9] Run regime filter               → regime_status.csv
[4/9] Build factor model v2           → factor_model_v2.csv
[5/9] Interpret CAPEX context         → capex_context.csv
[6/9] Parse news → narrative          → narrative_signals.csv
[7/9] Compute risk flags              → risk_flags.csv
[8/9] Score + rank                    → alpha_ranking.csv (+ theme/watchlist)
[9/9] Build dashboard + daily report  → dashboard_data.json + .md
```

Individual modules can also be run standalone via `scripts/run_*.py`.

---

## 5. Decision zones — how to interpret

CSV / JSON columns store the English keys below. The dashboard renders them in 繁中 with a hover tooltip on the column header that shows all six definitions at once. Translation lives in `dashboard/components/_columns.py` (`ZONE_LABELS_ZH`, `ACTION_LABELS_ZH`).

| Zone (en) | 中文 | Gate (post 2026-05-09) | Suggested action |
|---|---|---|---|
| **Strong Candidate** | 強候選 | `alpha ≥ 2.5` + `residual_alpha ≥ 1.5` + `risk_penalty ≤ 2.0` + `confidence ≥ 2.5`, not blocked | Research priority — confirm fundamentals + sizing. **NOT auto-buy.** |
| **Watchlist** | 觀察名單 | `alpha ≥ 2.0` + positive residual + `risk_penalty ≤ 4.0`, not blocked | Track |
| **Narrative Watch** | 題材觀察 | tier3 narrative-only path (legacy, no-op when narrative weight = 0) | Track only |
| **Avoid Chasing** | 避免追高 | (overbought ∨ valuation_extreme) ∧ `severity ≥ 6` | Do not chase strength |
| **Neutral** | 中性 | `alpha ≥ 0` but didn't qualify above | Skip |
| **Avoid** | 避免 | `alpha < 0` | Skip until setup changes |

`alpha_score` is a relative ranking, **not** an expected return.

The threshold `severity ≥ 6` for Avoid Chasing was raised from 5 → 6 on 2026-05-09 to match `tier4_blocking` and reclassify a misclassified boundary cohort. Apples-to-apples Δ Sharpe of the gate filter is +0.012 (within noise), so gates serve **dashboard interpretability**, not portfolio alpha. See `reports/phase_gate_recalibration.md` for the full retraction-and-honesty story.

---

## 6. Walk-forward validation — what we learned

71 monthly rebalances 2020-06-30 → 2026-04-30, 4189 (date, ticker) observations on the `expanded_liquid_60` universe. Numbers below reflect the active baseline post Gate-Recalibration (2026-05-09, sev=6).

### Decision zone IS informative

| Zone | n_obs | mean_fwd_1m | hit_rate |
|---|---:|---:|---:|
| Strong Candidate | 81 | **+9.5%** | **63.0%** |
| Watchlist | 45 | +5.1% | 64.4% |
| Neutral | 753 | +4.7% | 59.0% |
| Avoid Chasing | 120 | +7.9% | 55.0% |
| Avoid | 3131 | +3.3% | 55.4% |

✅ Strong > Watchlist > Neutral > Avoid in mean fwd. ⚠️ Strong is still only n=81 over 71 months ≈ 1 per month, with 29 months still showing 0 Strongs.

### Ablation says model is over-engineered

| Variant | Sharpe | max DD | Total Return |
|---|---:|---:|---:|
| **full** | 1.94 | -25.7% | 10,990% |
| **residual_alpha_only** | **1.94** | -25.7% | 10,990% |
| no_sector_relative | 1.94 | -25.7% | 10,990% |
| no_narrative | 1.94 | -25.7% | 10,990% |
| no_revenue | 1.94 | -25.7% | 10,990% |
| no_flow | 1.94 | -25.7% | 10,990% |
| no_risk_penalty | 1.85 | -34.2% | 8,901% |
| narrative_only | 1.45 | -30.3% | 1,340% |
| random | 1.48 | -41.0% | 1,366% |
| 0050.TW benchmark | 1.29 | -29.2% | 378% |

**Findings:**
- ✅ **Residual alpha is the entire model** — `residual_alpha_only` is mechanically identical to `full` because every other tier weight is already zero (rev / flow / sec / narrative all 0.00 since A2-adopt).
- ✅ **Risk penalty earns its place** — Sharpe +0.09, max DD +8.5pp.
- All other ablations are no-ops by construction.

### Decision-zone gate filter doesn't add portfolio alpha

The `gate_attribution` lens compares top-5 picked by raw alpha vs top-5 with `Avoid + Avoid Chasing` filtered out, on matched months:

| Variant | n_months | Sharpe | max DD | Total |
|---|---:|---:|---:|---:|
| `top5_by_alpha` (no filter) | 70 | 1.94 | -25.7% | 10,990% |
| `top5_zone_filtered` | 58 | 2.13 | -21.8% | 6,269% |
| `top5_by_alpha_aligned` (same 58 months) | 58 | 2.12 | -23.3% | 7,127% |

The apples-to-apples ΔSharpe of zone filtering = **+0.012** — within noise. The decision_zone machinery is for **human research interpretability**, not portfolio alpha.

This is why the recent gate-recalibration (`reports/phase_gate_recalibration.md`) explicitly retracted a first-pass claim of "Sharpe 1.86 → 2.04" — that came from a loose `head(5)` sim and was almost entirely a coverage artifact under the production `skip months with <5 eligible names` rule.

Full reports: `reports/walk_forward_v2_summary.md` (latest run), `reports/phase_gate_recalibration.md` (the methodology lesson), `reports/phase_regime_stress.md` (out-of-regime stress test, re-validated 2026-05-10).

---

## 7. Risk and bias

- **Universe size**: 60 tickers (`expanded_liquid_60`), top-5 ≈ 8% concentration. Max DD -25.7% vs benchmark -29.2%.
- **Universe excludes 2330.TW** — TSMC is too dominant; if it's in the basket every name correlates ~1.0 with it.
- **Survivorship**: 60-name expanded list is liquidity-curated; no truly de-listed names included.
- **Look-ahead**: PIT-correct — revenue lagged 45 days, prices/flow/valuation filtered to ≤ as_of.
- **News coverage**: `news_events.csv` only has 2025-mid onward — narrative weight is already 0 in the active baseline so this no longer affects portfolio outcome.
- **Inst flow coverage**: starts 2022-01 — flow weight is also 0 in the active baseline, so the gap is moot for live ranking. Pre-2022 ablation tests of those factors should be read with caution.
- **Window is 100% AI-bull-adjacent** in *return magnitude*: 2022 bear (12 months) is the only material non-bull stretch. Direction-wise the strategy beats benchmark in every regime including 2022 bear (Sharpe 0.93 residual-alpha-only vs benchmark −13%); magnitude-wise AI era is ~3.5× CAGR vs pre-AI mania. Treat 2-3× upside as regime gift, not the alpha source. See `reports/phase_regime_stress.md`.
- **Factor weights are priors**, not optimised on this data. The active baseline ("Simplest Robust") zeroed everything except residual_alpha + risk_penalty + a tiny capex_context after walk-forward weight grid (`scripts/run_weight_grid.py`).
- **Regime filter** controls exposure on paper but **nothing reads its output** in the current pipeline. `recommended_gross_exposure` is informational only — wiring it into actual sizing is the next-priority Phase D item.

---

## 8. Roadmap

Updated 2026-05-10 after the regime-stress re-validation. Items in **bold** are actively gating daily auto-execution.

Done since v2 launch:
- ✅ **Re-tune weights** — A1/A2-adopt zeroed `sector_relative_strength`, `narrative_score`, `revenue_confirmation_score`, `institutional_flow_score`. Active model is residual α + risk penalty.
- ✅ **Run weight optimisation** — grid over `ra_w` × `rev_w` × `flw_w` × `risk_mult`; settled on Simplest Robust (`reports/phase_a2rerun_post_b3.md`).
- ✅ **Universe expansion** — `expanded_liquid_60` (optical, photonics, thermal, HBM/memory, passives, LEO satellite, power grid) (`reports/phase_c_universe_expansion.md`).
- ✅ **Streamlit UI** on `dashboard_data.json` — 8 pages, paper-portfolio rebalance flow, Chinese decision-zone labels with hover tooltips.
- ✅ **Decision-zone gate-repair** + recalibration (`phase_gate_repair.md`, `phase_gate_recalibration.md`).
- ✅ **Out-of-regime stress test** — done 2026-05-03, re-validated under sev=6 on 2026-05-10. Conclusions hold (`reports/phase_regime_stress.md`).
- ✅ **Backfill institutional_flow.csv** to 2018+ via FinMind (Phase B3 — `reports/phase_b3_finmind_backfill.md`).
- ✅ **Transaction cost test** — break-even ~689 bps; not the binding constraint (`reports/phase_b1_transaction_cost.md`).
- ✅ **Drawdown control + cluster cap research** — Phase D1/D2 outputs in place but not yet wired into live sizing.
- ✅ **`data_loader` cache TTL + `--skip-fetch` made real** — 2026-05-10 fix.

Still pending:
1. ⏳ **Phase D portfolio construction live wiring** — `regime_filter.recommended_gross_exposure` is currently informational; needs to be threaded into actual sizing. Per stress-test recommendation: drawdown / regime exposure FIRST, theme cluster cap SECOND, vol targeting LAST (and only asymmetric).
2. ⏳ **Backfill `news_events.csv`** — GDELT 2018-2024. Lower priority since narrative weight is 0; only needed if narrative is reactivated.
3. ⏳ **Real transcript NLP** — TSMC + major suppliers + Nvidia/AMD/Broadcom/Marvell/Arista/Lumentum.
4. ⏳ **Decision-zone recalibration grid** — sweep `chase_severity` × `risk_penalty_multiplier`. Lower priority since gate calibration was shown to barely affect Sharpe in apples-to-apples.
5. ⏳ **Cross-market** — Taiwan + US + Japan + Korea.
6. ⏳ **Paper-portfolio shadow run** 1-3 months before considering daily auto-execution.
7. ⏳ **launchd / cron** — only after all above pre-conditions clear.

---

## 9. Not included from v1 (intentionally)

These v1 modules are **NOT** ported because v2 supersedes them:

- `scoring_model.py` (replaced by `fusion/scoring_model_v2.py`)
- `factor_backtest.py`, `event_study.py` (replaced by `validation/walk_forward_v2.py`)
- `revenue_tracker.py`, `report_writer.py`, `visualization.py` (v1-specific reporting)
- `sec_capex_parser.py` (only needed if you maintain CAPEX events; the existing CSV is preserved)
- `config/strategy_rules.yaml` (replaced by `config/alpha_model_v2.yaml`)
- v1 backtest reports (`reports/event_strategy_summary.md`, etc.)

If you need the original CAPEX validation work, see the v1 repo at `~/tsmc-capex-alpha-lab/`.
