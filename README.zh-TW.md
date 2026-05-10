# ai-supply-chain-alpha-lab

> 每日 AI 供應鏈 Alpha 探勘與排名平台
> 純 v2 fork — 乾淨 repo,沒有 legacy CAPEX-event 程式碼。

[English](README.md) | **繁體中文**

---

## 0. 免責聲明

研究框架,**不構成投資建議**。Strong Candidate 是研究優先順序,不是 buy 訊號。
原始假說「TSMC CAPEX guidance 上修可預測供應鏈受益股報酬」已在前一階段實證下被拒絕(event-driven p=0.67);本平台**不再**以 CAPEX 作為交易 trigger,CAPEX 僅作為 context(權重上限 ±0.5)。

---

## 1. 專案譜系

| | Repo | 用途 |
|---|---|---|
| v1 | `~/tsmc-capex-alpha-lab/` | CAPEX event-study + 5 個獨立驗證實驗(已完成) |
| **v2(本專案)** | `~/ai-supply-chain-alpha-lab/` | 每日 AI 供應鏈 alpha 排名平台 |

從 v1 帶過來的共用資產:
- `data/manual/` — universe、月營收、法人籌碼、估值、新聞、CAPEX 事件
- `data/raw/yfinance/` — 價格 cache (parquet)
- `src/capex_alpha/{data_loader,universe,utils}.py` — 共用 loaders
- 部分 fetch scripts(FinMind / GDELT / SEC EDGAR)

---

## 2. 架構

```
src/capex_alpha/
├── quant/                      # Tier 1 + Tier 2
│   ├── ai_factor_index.py      # 6 個題材 + 加總 AI 指數
│   ├── residual_alpha.py       # rolling β_market, β_ai → residual return
│   ├── factor_model_v2.py      # 10 個 z-scored factors(無 raw momentum)
│   ├── regime_filter.py        # market + AI regime → exposure
│   └── risk_model.py           # 個股風險旗標
│
├── narrative/                  # Tier 3
│   ├── news_parser.py          # GDELT → 個股 narrative_score
│   ├── capex_interpreter.py    # CAPEX 事件 → context tag(上限 ±0.5)
│   ├── transcript_parser.py    # placeholder;字典骨架
│   ├── tech_signal_classifier.py
│   └── narrative_scorer.py     # 整合 news + capex + transcript
│
├── fusion/                     # Tier 1+2+3+4 → 最終分數
│   ├── signal_hierarchy.py     # tier 閘(Strong / Watchlist / Narrative)
│   ├── scoring_model_v2.py     # alpha_score + decision_zone
│   └── alpha_ranking.py        # ranking + theme_ranking + watchlist
│
├── dashboard/
│   ├── dashboard_data.py       # 給任何 UI 介面用的 JSON payload
│   └── daily_report_generator.py
│
├── automation/
│   └── run_daily_pipeline.py   # 9 步驟 orchestrator
│
└── validation/                 # walk-forward + ablation + 壓力測試 + 投組研究
    ├── walk_forward_v2.py
    ├── ablation.py             # 含 gate_attribution(zone-filter apples-to-apples)
    ├── validation_report.py
    ├── regime_stress.py        # calendar / event regime 壓力測試
    ├── cluster_cap.py          # AI-cluster 聯合曝險上限研究
    ├── exposure_overlay.py     # regime → recommended_gross_exposure
    ├── portfolio_metrics.py
    ├── transaction_cost.py
    ├── universe_validation.py
    └── weight_grid.py          # tier-weight grid sweeps

src/capex_alpha/
├── data_loader.py              # yfinance cache 含 business-day TTL + stale fallback (2026-05-10)
├── data_quality.py
├── paper_portfolio.py          # 紙上組合的 rebalance / NAV / 成本估算
└── universe_expansion.py       # 候選名單流動性檢查 + 題材歸屬
```

`config/`:
- `alpha_model_v2.yaml` — 因子權重、tier 權重、決策區、上限
- `narrative_keywords.yaml` — 題材 ↔ 關鍵字字典
- `theme_mapping.yaml` — narrative tag → universe 題材歸屬
- `regime_rules.yaml` — regime cascade 門檻 + exposure
- `dashboard_config.yaml` — JSON 與報告輸出路徑
- `universe.yaml`, `data_sources.yaml` — 與 v1 共用

---

## 3. 快速開始

```bash
cd ~/ai-supply-chain-alpha-lab
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 每日排名 pipeline — 預設會自動刷新過期的 yfinance cache
# (cache TTL = 1 個交易日;過期就重抓,沒過期就用 cache)
.venv/bin/python scripts/run_daily_pipeline.py

# Offline / dev:強制不重抓,直接吃 cache
.venv/bin/python scripts/run_daily_pipeline.py --skip-fetch

# Walk-forward 驗證
.venv/bin/python scripts/run_walk_forward_v2.py
```

產出落在 `data/output/` 與 `reports/`:
- `data/output/alpha_ranking.csv` — 主排名
- `data/output/dashboard_data.json` — UI payload
- `reports/daily_alpha_report.md` — 人類可讀報告
- `reports/walk_forward_v2_summary.md` — 驗證報告

---

## 4. 每日 pipeline 做什麼

```
[1/9] 建立 AI factor index           → ai_factor_index.csv
[2/9] 計算 residual alpha             → residual_alpha.csv
[3/9] 跑 regime filter                → regime_status.csv
[4/9] 建立 factor model v2            → factor_model_v2.csv
[5/9] 解讀 CAPEX context              → capex_context.csv
[6/9] 解析新聞 → narrative            → narrative_signals.csv
[7/9] 計算風險旗標                    → risk_flags.csv
[8/9] 評分 + 排名                     → alpha_ranking.csv (+ theme/watchlist)
[9/9] 產出 dashboard + 每日報告        → dashboard_data.json + .md
```

各模組也可以透過 `scripts/run_*.py` 獨立跑。

---

## 5. 決策區 — 怎麼解讀

CSV / JSON 欄位儲存的是下面的英文 keys。儀表板會以**繁中**呈現,並在欄位標題提供 hover tooltip 一次顯示六種定義。翻譯定義在 `dashboard/components/_columns.py`(`ZONE_LABELS_ZH`、`ACTION_LABELS_ZH`)。

| Zone (en) | 中文 | 觸發條件(2026-05-09 後) | 建議動作 |
|---|---|---|---|
| **Strong Candidate** | 強候選 | `alpha ≥ 2.5` + `residual_alpha ≥ 1.5` + `risk_penalty ≤ 2.0` + `confidence ≥ 2.5`,未被 blocked | 研究優先 — 確認基本面與部位大小。**不是 auto-buy**。 |
| **Watchlist** | 觀察名單 | `alpha ≥ 2.0` + 殘差 α 為正 + `risk_penalty ≤ 4.0`,未被 blocked | 追蹤 |
| **Narrative Watch** | 題材觀察 | tier3 narrative-only 路徑(legacy,narrative 權重 = 0 時為 no-op) | 僅追蹤 |
| **Avoid Chasing** | 避免追高 | (overbought ∨ valuation_extreme) ∧ `severity ≥ 6` | 不要追高 |
| **Neutral** | 中性 | `alpha ≥ 0` 但沒進到上面任何條件 | 跳過 |
| **Avoid** | 避免 | `alpha < 0` | 跳過,等 setup 改變 |

`alpha_score` 是相對排名,**不是**預期報酬。

Avoid Chasing 的 `severity ≥ 6` 門檻是 2026-05-09 從 5 提高到 6,為了對齊 `tier4_blocking` 並修正一個錯分類的邊界 cohort。閘的過濾在 apples-to-apples 下的 Δ Sharpe 只有 +0.012(噪音範圍內),所以閘是給**儀表板可讀性**用的,不是 portfolio alpha 的來源。完整撤回與誠實檢討見 `reports/phase_gate_recalibration.md`。

---

## 6. Walk-forward 驗證 — 我們學到什麼

71 個月 rebalance,2020-06-30 → 2026-04-30,在 `expanded_liquid_60` universe 上 4189 筆 (date, ticker) 觀察。下方數字反映 Gate-Recalibration 後(2026-05-09, sev=6)的 active baseline。

### 決策區「有」資訊量

| Zone | n_obs | mean_fwd_1m | hit_rate |
|---|---:|---:|---:|
| Strong Candidate | 81 | **+9.5%** | **63.0%** |
| Watchlist | 45 | +5.1% | 64.4% |
| Neutral | 753 | +4.7% | 59.0% |
| Avoid Chasing | 120 | +7.9% | 55.0% |
| Avoid | 3131 | +3.3% | 55.4% |

✅ 平均次月報酬 Strong > Watchlist > Neutral > Avoid。⚠️ Strong 仍然只有 n=81 / 71 個月 ≈ 每月 1 筆,還有 29 個月 0 Strong。

### Ablation 顯示 model 過度工程化

| Variant | Sharpe | max DD | 累積報酬 |
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

**發現:**
- ✅ **residual alpha 就是整個 model** — `residual_alpha_only` 跟 `full` 機械上完全相同,因為其他 tier 權重在 A2-adopt 之後就全部歸零(rev / flow / sec / narrative 都是 0.00)。
- ✅ **risk penalty 站得住腳** — Sharpe +0.09、max DD +8.5pp。
- 其他所有 ablation 結構上都是 no-op。

### 決策區的閘過濾「不會」加 portfolio alpha

`gate_attribution` lens 比較「以原始 alpha 排前 5」vs「過濾掉 Avoid + Avoid Chasing 再排前 5」,在相同月份上比:

| Variant | n_months | Sharpe | max DD | 累積 |
|---|---:|---:|---:|---:|
| `top5_by_alpha`(無過濾) | 70 | 1.94 | -25.7% | 10,990% |
| `top5_zone_filtered` | 58 | 2.13 | -21.8% | 6,269% |
| `top5_by_alpha_aligned`(同 58 個月) | 58 | 2.12 | -23.3% | 7,127% |

過濾的 apples-to-apples ΔSharpe = **+0.012** — 噪音範圍內。decision_zone 機制是給**人類研究可讀性**用的,不是 portfolio alpha。

這就是為什麼最近的 gate-recalibration(`reports/phase_gate_recalibration.md`)明確撤回了「Sharpe 1.86 → 2.04」這個第一手聲明 — 那是 loose `head(5)` sim 的結果,在 production 的「< 5 檔合格就跳過月份」規則下幾乎全是 coverage artifact。

完整報告:`reports/walk_forward_v2_summary.md`(最新 run)、`reports/phase_gate_recalibration.md`(方法論教訓)、`reports/phase_regime_stress.md`(out-of-regime 壓力測試,2026-05-10 重新驗證)。

---

## 7. 風險與偏誤

- **Universe 大小**:60 檔(`expanded_liquid_60`),top-5 ≈ 8% 集中度。Max DD -25.7% vs 大盤 -29.2%。
- **Universe 排除 2330.TW** — 台積電太支配;放進籃子的話每檔票跟它的相關係數都接近 1.0。
- **存活者偏誤**:60 檔擴展名單是流動性過濾後的,沒有真正下市的票。
- **Look-ahead**:PIT-correct — 月營收延遲 45 天、價格 / 籌碼 / 估值都過濾到 ≤ as_of。
- **News 覆蓋率**:`news_events.csv` 只有 2025 年中以後 — narrative 權重在 active baseline 已是 0,所以這對 portfolio outcome 沒影響。
- **法人籌碼覆蓋率**:從 2022-01 開始 — flow 權重在 active baseline 也是 0,所以對 live ranking 沒差。pre-2022 對這些因子的 ablation 結果要小心解讀。
- **回測窗口在報酬量級上 100% 偏 AI 多頭**:2022 bear(12 個月)是唯一明顯的非多頭區段。**方向上**策略在每個 regime 都打贏 benchmark(含 2022 bear,殘差 α only Sharpe 0.93 vs 大盤 -13%);**量級上**AI era 的 CAGR 是 pre-AI mania 的 ~3.5×。把 2-3× 上漲看成 regime gift,不是 alpha 來源。見 `reports/phase_regime_stress.md`。
- **因子權重是 prior**,不是在這份資料上 optimise 的。Active baseline(「Simplest Robust」)在 walk-forward weight grid(`scripts/run_weight_grid.py`)後把除了 residual_alpha + risk_penalty + 微量 capex_context 以外都歸零。
- **Regime filter** 紙上控制 exposure,但**目前 pipeline 沒有任何模組讀它的輸出**。`recommended_gross_exposure` 只是 informational — 接到實際 sizing 是 Phase D 的下一個優先項目。

---

## 8. Roadmap

2026-05-10 regime-stress 重新驗證後更新。**粗體**項目是還在 gate 每日自動執行的關鍵。

v2 launch 以來已完成:
- ✅ **重新調整權重** — A1/A2-adopt 把 `sector_relative_strength`、`narrative_score`、`revenue_confirmation_score`、`institutional_flow_score` 都歸零。Active model 是殘差 α + risk penalty。
- ✅ **跑權重 optimisation** — 對 `ra_w` × `rev_w` × `flw_w` × `risk_mult` 做 grid;最終定在 Simplest Robust(`reports/phase_a2rerun_post_b3.md`)。
- ✅ **Universe 擴張** — `expanded_liquid_60`(光通訊、矽光子、散熱、HBM/記憶體、被動、低軌衛星、電網)(`reports/phase_c_universe_expansion.md`)。
- ✅ **Streamlit UI** 蓋在 `dashboard_data.json` 上 — 8 頁、紙上組合再平衡流程、決策區中文標籤含 hover tooltip。
- ✅ **決策區 gate-repair** + recalibration(`phase_gate_repair.md`、`phase_gate_recalibration.md`)。
- ✅ **Out-of-regime 壓力測試** — 2026-05-03 完成,2026-05-10 在 sev=6 下重新驗證。結論成立(`reports/phase_regime_stress.md`)。
- ✅ **Backfill `institutional_flow.csv`** 到 2018+(走 FinMind,Phase B3 — `reports/phase_b3_finmind_backfill.md`)。
- ✅ **交易成本測試** — 損益兩平 ~689 bps;不是 binding constraint(`reports/phase_b1_transaction_cost.md`)。
- ✅ **Drawdown control + cluster cap 研究** — Phase D1/D2 產出已就位,但還沒接到實際 sizing。
- ✅ **`data_loader` cache TTL + `--skip-fetch` 變成真實 flag** — 2026-05-10 修。

仍待處理:
1. ⏳ **Phase D portfolio construction live wiring** — `regime_filter.recommended_gross_exposure` 目前只是 informational,需要接到實際 sizing。依 stress-test 建議:drawdown / regime exposure 第一、theme cluster cap 第二、vol targeting 最後(且只能 asymmetric)。
2. ⏳ **Backfill `news_events.csv`** — GDELT 2018-2024。優先度低,因為 narrative 權重是 0;只有重新啟用 narrative 才需要。
3. ⏳ **真實 transcript NLP** — 台積電 + 主要供應商 + Nvidia/AMD/Broadcom/Marvell/Arista/Lumentum。
4. ⏳ **決策區 recalibration grid** — 對 `chase_severity` × `risk_penalty_multiplier` 做 grid。優先度低,因為閘的校正在 apples-to-apples 下幾乎不影響 Sharpe。
5. ⏳ **跨市場** — 台 + 美 + 日 + 韓。
6. ⏳ **紙上組合 shadow run** 1-3 個月,再考慮每日自動執行。
7. ⏳ **launchd / cron** — 上面所有 pre-condition 清完才會啟動。

---

## 9. 從 v1 「故意不」帶過來的東西

下列 v1 模組**沒有** port,因為 v2 已經取代:

- `scoring_model.py`(由 `fusion/scoring_model_v2.py` 取代)
- `factor_backtest.py`、`event_study.py`(由 `validation/walk_forward_v2.py` 取代)
- `revenue_tracker.py`、`report_writer.py`、`visualization.py`(v1-specific 報告)
- `sec_capex_parser.py`(只有維護 CAPEX 事件才需要;既有 CSV 仍保留)
- `config/strategy_rules.yaml`(由 `config/alpha_model_v2.yaml` 取代)
- v1 backtest 報告(`reports/event_strategy_summary.md` 等)

如果需要原始的 CAPEX 驗證工作,見 v1 repo `~/tsmc-capex-alpha-lab/`。
