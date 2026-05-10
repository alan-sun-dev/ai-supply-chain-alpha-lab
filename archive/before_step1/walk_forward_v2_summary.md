# v2 Walk-Forward Validation Report
_Window: 2020-06-30 → 2026-04-30, 71 monthly rebalances, 1562 (date, ticker) observations._

## 0. TL;DR
- **Full v2 top-5 portfolio**: total return `2526.5%`, Sharpe `1.681`, max DD `-31.4%`.
- **0050.TW benchmark**: total return `377.5%`, Sharpe `1.285`.
- **Spearman(alpha_score, fwd_return_1m)** = `0.065`, p=`0.011` → ✅ statistically significant.
- **Top-quintile minus bottom-quintile** monthly spread = `3.6%`.

## 1. Decision Zone Forward-Return Performance
_Pooled across all rebalance dates. If the gate is informative, Strong Candidate > Watchlist > Neutral > Avoid in mean fwd return._

| Zone | n_obs | n_tickers | mean_fwd_1m | median | hit_rate | std | min | max |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| Strong Candidate | 31 | 10 | 9.9% | 4.2% | 58.1% | 25.1% | -27.2% | 62.3% |
| Watchlist | 40 | 15 | 8.9% | 6.2% | 65.0% | 15.4% | -11.9% | 54.3% |
| Neutral | 265 | 22 | 3.7% | 1.3% | 55.8% | 17.4% | -53.0% | 117.9% |
| Avoid Chasing | 16 | 11 | 3.4% | -2.5% | 50.0% | 19.9% | -20.6% | 49.4% |
| Avoid | 1188 | 22 | 2.5% | 1.0% | 54.1% | 13.3% | -31.2% | 71.5% |

## 2. Alpha-Score Quintile Performance
_Per-rebalance-date quintile bucket. Q1 = highest alpha_score, Q5 = lowest._

| Bucket | n_obs | mean_fwd_1m | median | hit_rate |
|:--|---:|---:|---:|---:|
| Q1 | 350 | 5.3% | 1.7% | 59.1% |
| Q2 | 280 | 3.1% | 1.1% | 54.3% |
| Q3 | 280 | 2.5% | 1.7% | 55.7% |
| Q4 | 280 | 2.6% | 0.3% | 51.1% |
| Q5 | 350 | 1.5% | 0.7% | 52.9% |

## 3. Factor Ablation — Top-5 Long-Only Portfolio
_Each variant rebuilds alpha_score from the recorded tier components, then a top-5 monthly-rebalance portfolio is simulated._

| Variant | Spearman ρ | p-value | Q1 mean | Q5 mean | spread | Sharpe | max DD | Total |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 0.065 | 0.011 | 5.6% | 2.0% | 3.6% | 1.681 | -31.4% | 2526.5% |
| `no_narrative` | 0.065 | 0.011 | 5.6% | 2.0% | 3.6% | 1.681 | -31.4% | 2526.5% |
| `no_risk_penalty` | 0.056 | 0.027 | 5.3% | 2.0% | 3.3% | 1.649 | -37.3% | 2588.5% |
| `no_revenue` | 0.059 | 0.022 | 5.5% | 2.1% | 3.4% | 1.619 | -38.4% | 2455.1% |
| `no_sector_relative` | 0.065 | 0.011 | 5.6% | 2.0% | 3.6% | 1.681 | -31.4% | 2526.5% |
| `no_flow` | 0.065 | 0.011 | 5.8% | 2.2% | 3.5% | 1.680 | -29.9% | 2624.2% |
| `no_residual_alpha` | 0.055 | 0.032 | 4.0% | 2.3% | 1.7% | 1.533 | -26.8% | 1235.0% |
| `residual_alpha_only` | 0.058 | 0.024 | 5.0% | 1.9% | 3.1% | 1.610 | -37.0% | 2364.1% |
| `narrative_only` | — | — | 4.0% | 3.9% | 0.1% | 1.405 | -28.2% | 910.2% |
| `random` | -0.036 | 0.153 | 3.1% | 2.9% | 0.1% | 1.061 | -54.3% | 413.7% |

> Interpretation: `random` is the noise floor. If a variant matches `random` Sharpe, those factors contribute no signal. If `no_<X>` is materially better than `full`, that factor is hurting; if worse, it is helping.

## 4. Risk-Penalty Attribution
_Does the risk_penalty improve drawdown control without killing alpha?_

| Variant | mean_monthly | Sharpe | max DD | total_return |
|:--|---:|---:|---:|---:|
| `with_risk_penalty` | 5.3% | 1.681 | -31.4% | 2526.5% |
| `without_risk_penalty` | 5.4% | 1.649 | -37.3% | 2588.5% |

> Risk penalty improves max DD (-31.4% vs -37.3%).

## 5. Narrative Noise Check
_Does narrative_score add value or just inject noise?_

| Variant | mean_monthly | Sharpe | max DD | total / rho | note |
|:--|---:|---:|---:|---:|:--|
| `with_narrative` | 5.3% | 1.681 | -31.4% | 2526.5% |  |
| `without_narrative` | 5.3% | 1.681 | -31.4% | 2526.5% |  |
| `narrative_score_alone_spearman` | — | — | — | ρ=`—` | rho=nan, p=nan |

## 6. Caveats
- Universe is 22 tickers, all manually curated — survivorship bias is reduced by the SURVIVORSHIP-TEST cohort but not eliminated.
- Institutional flow data only starts 2022-01; pre-2022 the `institutional_flow_score` factor is mostly zero. Treat pre-2022 ablation results with caution.
- News data starts mid-2025 in the current `news_events.csv`; pre-mid-2025 narrative_score is mostly zero. The narrative ablation is therefore mostly testing the recent ~6-12 months.
- 1-month forward return is close-to-close on month-end; ignores execution costs, slippage, and Taiwan T+2 settlement.
- Factor weights are *priors*, not optimized on this data. A separate weight sweep would be needed to claim 'optimal' weights.
- 5-quintile bucketing on a 22-name universe yields ~4 names per bucket — small samples.