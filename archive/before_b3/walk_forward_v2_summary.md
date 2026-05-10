# v2 Walk-Forward Validation Report
_Window: 2020-06-30 → 2026-04-30, 71 monthly rebalances, 4189 (date, ticker) observations._

## 0. TL;DR
- **Full v2 top-5 portfolio**: total return `8634.7%`, Sharpe `1.975`, max DD `-27.9%`.
- **0050.TW benchmark**: total return `377.5%`, Sharpe `1.285`.
- **Spearman(alpha_score, fwd_return_1m)** = `0.035`, p=`0.026` → ✅ statistically significant.
- **Top-quintile minus bottom-quintile** monthly spread = `3.7%`.

## 1. Decision Zone Forward-Return Performance
_Pooled across all rebalance dates. If the gate is informative, Strong Candidate > Watchlist > Neutral > Avoid in mean fwd return._

| Zone | n_obs | n_tickers | mean_fwd_1m | median | hit_rate | std | min | max |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| Strong Candidate | 17 | 5 | 6.2% | 8.1% | 70.6% | 19.4% | -27.2% | 62.0% |
| Watchlist | 35 | 18 | 0.6% | -2.1% | 40.0% | 13.9% | -19.8% | 55.7% |
| Neutral | 548 | 59 | 5.0% | 2.0% | 60.0% | 13.9% | -28.7% | 82.0% |
| Avoid Chasing | 201 | 46 | 10.7% | 7.1% | 63.7% | 23.0% | -27.3% | 98.7% |
| Avoid | 3329 | 59 | 3.3% | 1.3% | 55.3% | 14.6% | -53.0% | 107.7% |

## 2. Alpha-Score Quintile Performance
_Per-rebalance-date quintile bucket. Q1 = highest alpha_score, Q5 = lowest._

| Bucket | n_obs | mean_fwd_1m | median | hit_rate |
|:--|---:|---:|---:|---:|
| Q1 | 840 | 6.1% | 2.2% | 58.3% |
| Q2 | 840 | 3.9% | 1.1% | 56.7% |
| Q3 | 770 | 3.3% | 1.1% | 54.2% |
| Q4 | 840 | 3.3% | 1.7% | 56.8% |
| Q5 | 840 | 2.8% | 1.5% | 55.4% |

## 3. Factor Ablation — Top-5 Long-Only Portfolio
_Each variant rebuilds alpha_score from the recorded tier components, then a top-5 monthly-rebalance portfolio is simulated._

| Variant | Spearman ρ | p-value | Q1 mean | Q5 mean | spread | Sharpe | max DD | Total |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 0.035 | 0.026 | 6.4% | 2.7% | 3.7% | 1.975 | -27.9% | 8634.7% |
| `no_narrative` | 0.035 | 0.026 | 6.4% | 2.7% | 3.7% | 1.975 | -27.9% | 8634.7% |
| `no_risk_penalty` | 0.046 | 0.003 | 6.4% | 2.5% | 3.9% | 1.719 | -33.2% | 5221.6% |
| `no_revenue` | 0.030 | 0.053 | 6.2% | 2.9% | 3.3% | 1.906 | -27.9% | 10837.6% |
| `no_sector_relative` | 0.035 | 0.026 | 6.4% | 2.7% | 3.7% | 1.975 | -27.9% | 8634.7% |
| `no_flow` | 0.036 | 0.022 | 6.5% | 2.6% | 3.8% | 2.070 | -30.6% | 9283.8% |
| `no_residual_alpha` | -0.036 | 0.022 | 3.7% | 3.8% | -0.1% | 1.547 | -32.8% | 1210.5% |
| `residual_alpha_only` | 0.030 | 0.053 | 6.4% | 2.8% | 3.5% | 1.915 | -26.7% | 12640.4% |
| `narrative_only` | — | — | 3.6% | 3.4% | 0.1% | 1.197 | -37.0% | 599.1% |
| `random` | 0.021 | 0.187 | 4.3% | 3.0% | 1.2% | 1.684 | -18.5% | 1149.0% |

> Interpretation: `random` is the noise floor. If a variant matches `random` Sharpe, those factors contribute no signal. If `no_<X>` is materially better than `full`, that factor is hurting; if worse, it is helping.

## 4. Risk-Penalty Attribution
_Does the risk_penalty improve drawdown control without killing alpha?_

| Variant | mean_monthly | Sharpe | max DD | total_return |
|:--|---:|---:|---:|---:|
| `with_risk_penalty` | 7.3% | 1.975 | -27.9% | 8634.7% |
| `without_risk_penalty` | 6.6% | 1.719 | -33.2% | 5221.6% |

> Risk penalty improves max DD (-27.9% vs -33.2%).

## 5. Narrative Noise Check
_Does narrative_score add value or just inject noise?_

| Variant | mean_monthly | Sharpe | max DD | total / rho | note |
|:--|---:|---:|---:|---:|:--|
| `with_narrative` | 7.3% | 1.975 | -27.9% | 8634.7% |  |
| `without_narrative` | 7.3% | 1.975 | -27.9% | 8634.7% |  |
| `narrative_score_alone_spearman` | — | — | — | ρ=`—` | rho=nan, p=nan |

## 6. Caveats
- Universe is 22 tickers, all manually curated — survivorship bias is reduced by the SURVIVORSHIP-TEST cohort but not eliminated.
- Institutional flow data only starts 2022-01; pre-2022 the `institutional_flow_score` factor is mostly zero. Treat pre-2022 ablation results with caution.
- News data starts mid-2025 in the current `news_events.csv`; pre-mid-2025 narrative_score is mostly zero. The narrative ablation is therefore mostly testing the recent ~6-12 months.
- 1-month forward return is close-to-close on month-end; ignores execution costs, slippage, and Taiwan T+2 settlement.
- Factor weights are *priors*, not optimized on this data. A separate weight sweep would be needed to claim 'optimal' weights.
- 5-quintile bucketing on a 22-name universe yields ~4 names per bucket — small samples.