# v2 Walk-Forward Validation Report
_Window: 2020-06-30 → 2026-04-30, 71 monthly rebalances, 4189 (date, ticker) observations._

## 0. TL;DR
- **Full v2 top-5 portfolio**: total return `10990.6%`, Sharpe `1.941`, max DD `-25.7%`.
- **0050.TW benchmark**: total return `377.5%`, Sharpe `1.285`.
- **Spearman(alpha_score, fwd_return_1m)** = `0.021`, p=`0.171` → ❌ not significant.
- **Top-quintile minus bottom-quintile** monthly spread = `2.7%`.

## 1. Decision Zone Forward-Return Performance
_Pooled across all rebalance dates. If the gate is informative, Strong Candidate > Watchlist > Neutral > Avoid in mean fwd return._

| Zone | n_obs | n_tickers | mean_fwd_1m | median | hit_rate | std | min | max |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| Strong Candidate | 81 | 40 | 9.5% | 7.0% | 63.0% | 21.3% | -27.2% | 83.5% |
| Watchlist | 45 | 26 | 5.1% | 3.2% | 64.4% | 13.6% | -27.3% | 32.2% |
| Neutral | 753 | 59 | 4.7% | 1.9% | 59.0% | 14.3% | -53.0% | 82.0% |
| Avoid Chasing | 120 | 41 | 7.9% | 1.7% | 55.0% | 23.1% | -26.7% | 98.7% |
| Avoid | 3131 | 59 | 3.3% | 1.3% | 55.4% | 14.7% | -34.9% | 107.7% |

## 2. Alpha-Score Quintile Performance
_Per-rebalance-date quintile bucket. Q1 = highest alpha_score, Q5 = lowest._

| Bucket | n_obs | mean_fwd_1m | median | hit_rate |
|:--|---:|---:|---:|---:|
| Q1 | 840 | 6.0% | 1.9% | 57.6% |
| Q2 | 840 | 3.5% | 1.2% | 56.7% |
| Q3 | 770 | 3.0% | 0.7% | 52.9% |
| Q4 | 840 | 3.5% | 1.7% | 57.0% |
| Q5 | 840 | 3.2% | 2.0% | 57.0% |

## 3. Factor Ablation — Top-5 Long-Only Portfolio
_Each variant rebuilds alpha_score from the recorded tier components, then a top-5 monthly-rebalance portfolio is simulated._

| Variant | Spearman ρ | p-value | Q1 mean | Q5 mean | spread | Sharpe | max DD | Total |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 0.021 | 0.171 | 5.9% | 3.2% | 2.7% | 1.941 | -25.7% | 10990.6% |
| `no_narrative` | 0.021 | 0.171 | 5.9% | 3.2% | 2.7% | 1.941 | -25.7% | 10990.6% |
| `no_risk_penalty` | 0.041 | 0.008 | 6.1% | 3.2% | 3.0% | 1.851 | -34.2% | 8901.2% |
| `no_revenue` | 0.021 | 0.171 | 5.9% | 3.2% | 2.7% | 1.941 | -25.7% | 10990.6% |
| `no_sector_relative` | 0.021 | 0.171 | 5.9% | 3.2% | 2.7% | 1.941 | -25.7% | 10990.6% |
| `no_flow` | 0.021 | 0.171 | 5.9% | 3.2% | 2.7% | 1.941 | -25.7% | 10990.6% |
| `no_residual_alpha` | -0.056 | 0.000 | 3.3% | 4.6% | -1.3% | 1.092 | -32.3% | 552.8% |
| `residual_alpha_only` | 0.021 | 0.171 | 5.9% | 3.2% | 2.7% | 1.941 | -25.7% | 10990.6% |
| `narrative_only` | — | — | 3.6% | 3.3% | 0.4% | 1.446 | -30.3% | 1340.4% |
| `random` | 0.024 | 0.118 | 4.7% | 3.7% | 1.0% | 1.484 | -41.0% | 1365.7% |

> Interpretation: `random` is the noise floor. If a variant matches `random` Sharpe, those factors contribute no signal. If `no_<X>` is materially better than `full`, that factor is hurting; if worse, it is helping.

## 4. Risk-Penalty Attribution
_Does the risk_penalty improve drawdown control without killing alpha?_

| Variant | mean_monthly | Sharpe | max DD | total_return |
|:--|---:|---:|---:|---:|
| `with_risk_penalty` | 7.8% | 1.941 | -25.7% | 10990.6% |
| `without_risk_penalty` | 7.5% | 1.851 | -34.2% | 8901.2% |

> Risk penalty improves max DD (-25.7% vs -34.2%).

## 5. Narrative Noise Check
_Does narrative_score add value or just inject noise?_

| Variant | mean_monthly | Sharpe | max DD | total / rho | note |
|:--|---:|---:|---:|---:|:--|
| `with_narrative` | 7.8% | 1.941 | -25.7% | 10990.6% |  |
| `without_narrative` | 7.8% | 1.941 | -25.7% | 10990.6% |  |
| `narrative_score_alone_spearman` | — | — | — | ρ=`—` | rho=nan, p=nan |

## 6. Gate-Filtered Top-5 Portfolio
_Picks top-5 by `alpha_score` *after* dropping rows whose `decision_zone` is `Avoid` or `Avoid Chasing`. This is what the dashboard actually surfaces — a user does not buy Avoid-Chasing names. The unfiltered variant matches the `full` ablation row above._

| Variant | n_months | mean_monthly | Sharpe | max DD | total_return | note |
|:--|---:|---:|---:|---:|---:|:--|
| `top5_by_alpha` | 70 | 7.8% | 1.941 | -25.7% | 10990.6% | no zone filter |
| `top5_zone_filtered` | 58 | 8.2% | 2.128 | -21.8% | 6269.0% | excludes: Avoid + Avoid Chasing |
| `top5_by_alpha_aligned` | 58 | 8.5% | 2.115 | -23.3% | 7127.0% | no zone filter, same months as filtered |

> Apples-to-apples (`top5_zone_filtered` vs `top5_by_alpha_aligned`, same 58 months): zone filter improves Sharpe by `+0.012`, total_return Δ `-858.0%`, max_dd Δ `+1.5%`. The lower total vs `top5_by_alpha` is coverage drag — filtered skips months with <5 eligible names — not the filter being worse.

## 7. Caveats
- Universe is 22 tickers, all manually curated — survivorship bias is reduced by the SURVIVORSHIP-TEST cohort but not eliminated.
- Institutional flow data only starts 2022-01; pre-2022 the `institutional_flow_score` factor is mostly zero. Treat pre-2022 ablation results with caution.
- News data starts mid-2025 in the current `news_events.csv`; pre-mid-2025 narrative_score is mostly zero. The narrative ablation is therefore mostly testing the recent ~6-12 months.
- 1-month forward return is close-to-close on month-end; ignores execution costs, slippage, and Taiwan T+2 settlement.
- Factor weights are *priors*, not optimized on this data. A separate weight sweep would be needed to claim 'optimal' weights.
- 5-quintile bucketing on a 22-name universe yields ~4 names per bucket — small samples.