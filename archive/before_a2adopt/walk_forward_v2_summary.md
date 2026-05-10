# v2 Walk-Forward Validation Report
_Window: 2020-06-30 → 2026-04-30, 71 monthly rebalances, 4189 (date, ticker) observations._

## 0. TL;DR
- **Full v2 top-5 portfolio**: total return `3273.0%`, Sharpe `1.680`, max DD `-28.9%`.
- **0050.TW benchmark**: total return `377.5%`, Sharpe `1.285`.
- **Spearman(alpha_score, fwd_return_1m)** = `0.018`, p=`0.254` → ❌ not significant.
- **Top-quintile minus bottom-quintile** monthly spread = `2.0%`.

## 1. Decision Zone Forward-Return Performance
_Pooled across all rebalance dates. If the gate is informative, Strong Candidate > Watchlist > Neutral > Avoid in mean fwd return._

| Zone | n_obs | n_tickers | mean_fwd_1m | median | hit_rate | std | min | max |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| Strong Candidate | 72 | 36 | 5.8% | 3.3% | 55.6% | 18.7% | -27.2% | 83.5% |
| Watchlist | 110 | 40 | 4.7% | 0.9% | 55.5% | 16.5% | -23.5% | 81.5% |
| Neutral | 838 | 59 | 4.7% | 1.5% | 56.6% | 15.1% | -34.9% | 81.8% |
| Avoid Chasing | 13 | 11 | 11.1% | 0.7% | 53.8% | 25.0% | -20.6% | 59.8% |
| Avoid | 3097 | 59 | 3.5% | 1.6% | 56.3% | 14.9% | -53.0% | 107.7% |

## 2. Alpha-Score Quintile Performance
_Per-rebalance-date quintile bucket. Q1 = highest alpha_score, Q5 = lowest._

| Bucket | n_obs | mean_fwd_1m | median | hit_rate |
|:--|---:|---:|---:|---:|
| Q1 | 840 | 5.4% | 1.6% | 56.1% |
| Q2 | 840 | 4.2% | 1.4% | 57.3% |
| Q3 | 770 | 3.3% | 1.9% | 55.8% |
| Q4 | 840 | 2.7% | 1.0% | 54.8% |
| Q5 | 840 | 3.6% | 2.0% | 57.5% |

## 3. Factor Ablation — Top-5 Long-Only Portfolio
_Each variant rebuilds alpha_score from the recorded tier components, then a top-5 monthly-rebalance portfolio is simulated._

| Variant | Spearman ρ | p-value | Q1 mean | Q5 mean | spread | Sharpe | max DD | Total |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 0.018 | 0.254 | 5.7% | 3.6% | 2.0% | 1.680 | -28.9% | 3273.0% |
| `no_narrative` | 0.018 | 0.254 | 5.7% | 3.6% | 2.0% | 1.680 | -28.9% | 3273.0% |
| `no_risk_penalty` | 0.037 | 0.018 | 5.7% | 3.2% | 2.5% | 1.663 | -35.2% | 3848.1% |
| `no_revenue` | 0.013 | 0.412 | 5.9% | 3.2% | 2.6% | 1.869 | -22.5% | 6522.3% |
| `no_sector_relative` | 0.018 | 0.254 | 5.7% | 3.6% | 2.0% | 1.680 | -28.9% | 3273.0% |
| `no_flow` | 0.014 | 0.355 | 5.5% | 3.8% | 1.7% | 1.761 | -26.6% | 3833.8% |
| `no_residual_alpha` | -0.019 | 0.232 | 4.0% | 4.1% | -0.1% | 1.474 | -22.8% | 1089.6% |
| `residual_alpha_only` | 0.010 | 0.519 | 5.8% | 3.5% | 2.2% | 1.897 | -24.1% | 5767.0% |
| `narrative_only` | — | — | 3.0% | 3.8% | -0.8% | 1.288 | -32.1% | 618.2% |
| `random` | 0.007 | 0.636 | 4.0% | 3.5% | 0.4% | 1.373 | -38.9% | 1201.0% |

> Interpretation: `random` is the noise floor. If a variant matches `random` Sharpe, those factors contribute no signal. If `no_<X>` is materially better than `full`, that factor is hurting; if worse, it is helping.

## 4. Risk-Penalty Attribution
_Does the risk_penalty improve drawdown control without killing alpha?_

| Variant | mean_monthly | Sharpe | max DD | total_return |
|:--|---:|---:|---:|---:|
| `with_risk_penalty` | 5.8% | 1.680 | -28.9% | 3273.0% |
| `without_risk_penalty` | 6.1% | 1.663 | -35.2% | 3848.1% |

> Risk penalty improves max DD (-28.9% vs -35.2%).

## 5. Narrative Noise Check
_Does narrative_score add value or just inject noise?_

| Variant | mean_monthly | Sharpe | max DD | total / rho | note |
|:--|---:|---:|---:|---:|:--|
| `with_narrative` | 5.8% | 1.680 | -28.9% | 3273.0% |  |
| `without_narrative` | 5.8% | 1.680 | -28.9% | 3273.0% |  |
| `narrative_score_alone_spearman` | — | — | — | ρ=`—` | rho=nan, p=nan |

## 6. Caveats
- Universe is 22 tickers, all manually curated — survivorship bias is reduced by the SURVIVORSHIP-TEST cohort but not eliminated.
- Institutional flow data only starts 2022-01; pre-2022 the `institutional_flow_score` factor is mostly zero. Treat pre-2022 ablation results with caution.
- News data starts mid-2025 in the current `news_events.csv`; pre-mid-2025 narrative_score is mostly zero. The narrative ablation is therefore mostly testing the recent ~6-12 months.
- 1-month forward return is close-to-close on month-end; ignores execution costs, slippage, and Taiwan T+2 settlement.
- Factor weights are *priors*, not optimized on this data. A separate weight sweep would be needed to claim 'optimal' weights.
- 5-quintile bucketing on a 22-name universe yields ~4 names per bucket — small samples.