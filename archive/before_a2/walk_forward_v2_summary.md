# v2 Walk-Forward Validation Report
_Window: 2020-06-30 → 2026-04-30, 71 monthly rebalances, 1562 (date, ticker) observations._

## 0. TL;DR
- **Full v2 top-5 portfolio**: total return `2656.8%`, Sharpe `1.639`, max DD `-33.7%`.
- **0050.TW benchmark**: total return `377.5%`, Sharpe `1.285`.
- **Spearman(alpha_score, fwd_return_1m)** = `0.062`, p=`0.015` → ✅ statistically significant.
- **Top-quintile minus bottom-quintile** monthly spread = `3.6%`.

## 1. Decision Zone Forward-Return Performance
_Pooled across all rebalance dates. If the gate is informative, Strong Candidate > Watchlist > Neutral > Avoid in mean fwd return._

| Zone | n_obs | n_tickers | mean_fwd_1m | median | hit_rate | std | min | max |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| Strong Candidate | 5 | 2 | 4.7% | 12.6% | 80.0% | 18.8% | -27.2% | 21.2% |
| Watchlist | 52 | 15 | 9.5% | 5.6% | 57.7% | 21.2% | -25.2% | 62.3% |
| Neutral | 249 | 22 | 3.8% | 1.4% | 56.6% | 17.6% | -53.0% | 117.9% |
| Avoid Chasing | 16 | 11 | 3.4% | -2.5% | 50.0% | 19.9% | -20.6% | 49.4% |
| Avoid | 1218 | 22 | 2.6% | 1.0% | 54.2% | 13.4% | -31.2% | 71.5% |

## 2. Alpha-Score Quintile Performance
_Per-rebalance-date quintile bucket. Q1 = highest alpha_score, Q5 = lowest._

| Bucket | n_obs | mean_fwd_1m | median | hit_rate |
|:--|---:|---:|---:|---:|
| Q1 | 350 | 5.5% | 1.7% | 58.9% |
| Q2 | 280 | 3.0% | 1.4% | 55.4% |
| Q3 | 280 | 3.0% | 1.9% | 57.1% |
| Q4 | 280 | 2.1% | 0.2% | 50.7% |
| Q5 | 350 | 1.4% | 0.3% | 51.4% |

## 3. Factor Ablation — Top-5 Long-Only Portfolio
_Each variant rebuilds alpha_score from the recorded tier components, then a top-5 monthly-rebalance portfolio is simulated._

| Variant | Spearman ρ | p-value | Q1 mean | Q5 mean | spread | Sharpe | max DD | Total |
|:--|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 0.062 | 0.015 | 5.3% | 1.7% | 3.6% | 1.639 | -33.7% | 2656.8% |
| `no_narrative` | 0.062 | 0.015 | 5.3% | 1.7% | 3.6% | 1.639 | -33.7% | 2656.8% |
| `no_risk_penalty` | 0.057 | 0.026 | 4.6% | 1.7% | 2.9% | 1.630 | -37.5% | 3019.1% |
| `no_revenue` | 0.058 | 0.022 | 5.5% | 2.0% | 3.5% | 1.616 | -34.6% | 2414.6% |
| `no_sector_relative` | 0.062 | 0.015 | 5.3% | 1.7% | 3.6% | 1.639 | -33.7% | 2656.8% |
| `no_flow` | 0.063 | 0.014 | 5.4% | 1.8% | 3.6% | 1.667 | -35.4% | 2647.2% |
| `no_residual_alpha` | 0.051 | 0.044 | 3.8% | 1.7% | 2.1% | 1.562 | -18.1% | 1375.9% |
| `residual_alpha_only` | 0.058 | 0.024 | 5.0% | 1.9% | 3.1% | 1.610 | -37.0% | 2364.1% |
| `narrative_only` | — | — | 4.1% | 3.6% | 0.5% | 1.366 | -27.9% | 979.8% |
| `random` | -0.027 | 0.284 | 2.7% | 2.1% | 0.7% | 1.082 | -48.5% | 425.0% |

> Interpretation: `random` is the noise floor. If a variant matches `random` Sharpe, those factors contribute no signal. If `no_<X>` is materially better than `full`, that factor is hurting; if worse, it is helping.

## 4. Risk-Penalty Attribution
_Does the risk_penalty improve drawdown control without killing alpha?_

| Variant | mean_monthly | Sharpe | max DD | total_return |
|:--|---:|---:|---:|---:|
| `with_risk_penalty` | 5.5% | 1.639 | -33.7% | 2656.8% |
| `without_risk_penalty` | 5.7% | 1.630 | -37.5% | 3019.1% |

> Risk penalty improves max DD (-33.7% vs -37.5%).

## 5. Narrative Noise Check
_Does narrative_score add value or just inject noise?_

| Variant | mean_monthly | Sharpe | max DD | total / rho | note |
|:--|---:|---:|---:|---:|:--|
| `with_narrative` | 5.5% | 1.639 | -33.7% | 2656.8% |  |
| `without_narrative` | 5.5% | 1.639 | -33.7% | 2656.8% |  |
| `narrative_score_alone_spearman` | — | — | — | ρ=`—` | rho=nan, p=nan |

## 6. Caveats
- Universe is 22 tickers, all manually curated — survivorship bias is reduced by the SURVIVORSHIP-TEST cohort but not eliminated.
- Institutional flow data only starts 2022-01; pre-2022 the `institutional_flow_score` factor is mostly zero. Treat pre-2022 ablation results with caution.
- News data starts mid-2025 in the current `news_events.csv`; pre-mid-2025 narrative_score is mostly zero. The narrative ablation is therefore mostly testing the recent ~6-12 months.
- 1-month forward return is close-to-close on month-end; ignores execution costs, slippage, and Taiwan T+2 settlement.
- Factor weights are *priors*, not optimized on this data. A separate weight sweep would be needed to claim 'optimal' weights.
- 5-quintile bucketing on a 22-name universe yields ~4 names per bucket — small samples.