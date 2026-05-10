# v2 Walk-Forward Validation Report
_Window: 2020-06-30 → 2026-04-30, 71 monthly rebalances, 1562 (date, ticker) observations._

## 0. TL;DR
- **Full v2 top-5 portfolio**: total return `1798.6%`, Sharpe `1.494`, max DD `-40.8%`.
- **0050.TW benchmark**: total return `377.5%`, Sharpe `1.285`.
- **Spearman(alpha_score, fwd_return_1m)** = `0.061`, p=`0.016` → ✅ statistically significant.
- **Top-quintile minus bottom-quintile** monthly spread = `3.4%`.

## 1. Decision Zone Forward-Return Performance
_Pooled across all rebalance dates. If the gate is informative, Strong Candidate > Watchlist > Neutral > Avoid in mean fwd return._

| Zone | n_obs | n_tickers | mean_fwd_1m | median | hit_rate | std | min | max |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| Strong Candidate | 19 | 9 | 11.8% | 8.1% | 63.2% | 27.8% | -27.2% | 62.3% |
| Watchlist | 79 | 20 | 6.4% | 2.7% | 58.2% | 18.8% | -53.0% | 55.7% |
| Neutral | 270 | 22 | 3.8% | 1.3% | 57.0% | 15.7% | -27.4% | 82.0% |
| Avoid Chasing | 31 | 16 | 1.3% | 0.0% | 51.6% | 16.1% | -23.2% | 49.4% |
| Avoid | 1141 | 22 | 2.5% | 1.0% | 53.9% | 13.5% | -31.2% | 117.9% |

## 2. Alpha-Score Quintile Performance
_Per-rebalance-date quintile bucket. Q1 = highest alpha_score, Q5 = lowest._

| Bucket | n_obs | mean_fwd_1m | median | hit_rate |
|:--|---:|---:|---:|---:|
| Q1 | 350 | 4.9% | 1.6% | 57.1% |
| Q2 | 280 | 4.1% | 1.7% | 58.6% |
| Q3 | 280 | 3.6% | 1.7% | 55.7% |
| Q4 | 280 | 1.2% | 0.1% | 50.0% |
| Q5 | 350 | 1.4% | 0.4% | 52.3% |

## 3. Factor Ablation — Top-5 Long-Only Portfolio
_Each variant rebuilds alpha_score from the recorded tier components, then a top-5 monthly-rebalance portfolio is simulated._

| Variant | Spearman ρ | p-value | Q1 mean | Q5 mean | spread | Sharpe | max DD | Total |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 0.061 | 0.016 | 5.1% | 1.7% | 3.4% | 1.494 | -40.8% | 1798.6% |
| `no_narrative` | 0.060 | 0.019 | 5.1% | 1.5% | 3.5% | 1.493 | -40.8% | 1809.3% |
| `no_risk_penalty` | 0.049 | 0.055 | 5.2% | 1.9% | 3.3% | 1.218 | -48.2% | 1006.4% |
| `no_revenue` | 0.060 | 0.019 | 5.1% | 1.2% | 3.9% | 1.364 | -44.8% | 1662.0% |
| `no_sector_relative` | 0.064 | 0.012 | 5.2% | 1.6% | 3.5% | 1.602 | -33.7% | 2448.5% |
| `no_flow` | 0.061 | 0.017 | 5.1% | 1.6% | 3.5% | 1.478 | -40.9% | 1811.7% |
| `no_residual_alpha` | 0.063 | 0.013 | 5.2% | 1.1% | 4.1% | 1.566 | -35.3% | 1829.6% |
| `residual_alpha_only` | 0.058 | 0.024 | 5.0% | 1.9% | 3.1% | 1.610 | -37.0% | 2364.1% |
| `narrative_only` | 0.058 | 0.022 | 2.8% | 3.1% | -0.2% | 1.067 | -36.7% | 423.0% |
| `random` | -0.070 | 0.006 | 1.4% | 3.8% | -2.5% | 0.645 | -51.2% | 150.6% |

> Interpretation: `random` is the noise floor. If a variant matches `random` Sharpe, those factors contribute no signal. If `no_<X>` is materially better than `full`, that factor is hurting; if worse, it is helping.

## 4. Risk-Penalty Attribution
_Does the risk_penalty improve drawdown control without killing alpha?_

| Variant | mean_monthly | Sharpe | max DD | total_return |
|:--|---:|---:|---:|---:|
| `with_risk_penalty` | 4.9% | 1.494 | -40.8% | 1798.6% |
| `without_risk_penalty` | 4.1% | 1.218 | -48.2% | 1006.4% |

> Risk penalty improves max DD (-40.8% vs -48.2%).

## 5. Narrative Noise Check
_Does narrative_score add value or just inject noise?_

| Variant | mean_monthly | Sharpe | max DD | total / rho | note |
|:--|---:|---:|---:|---:|:--|
| `with_narrative` | 4.9% | 1.494 | -40.8% | 1798.6% |  |
| `without_narrative` | 4.9% | 1.493 | -40.8% | 1809.3% |  |
| `narrative_score_alone_spearman` | — | — | — | ρ=`0.058` | rho=0.058, p=0.022 |

## 6. Caveats
- Universe is 22 tickers, all manually curated — survivorship bias is reduced by the SURVIVORSHIP-TEST cohort but not eliminated.
- Institutional flow data only starts 2022-01; pre-2022 the `institutional_flow_score` factor is mostly zero. Treat pre-2022 ablation results with caution.
- News data starts mid-2025 in the current `news_events.csv`; pre-mid-2025 narrative_score is mostly zero. The narrative ablation is therefore mostly testing the recent ~6-12 months.
- 1-month forward return is close-to-close on month-end; ignores execution costs, slippage, and Taiwan T+2 settlement.
- Factor weights are *priors*, not optimized on this data. A separate weight sweep would be needed to claim 'optimal' weights.
- 5-quintile bucketing on a 22-name universe yields ~4 names per bucket — small samples.