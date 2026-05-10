# Phase A2 — Weight Grid Search Results
_Cells: 3360.  Train ≤ 2023-12-29 (43 months).  Test ≥ 2024-01-31 (28 months).  Robustness filter: test_sharpe ≥ 80% × train_sharpe.  Strong filter: ≥ 15 obs._

- Cells passing robustness filter: **3360** / 3360  (100.0%)
- Cells passing both filters:      **2300** / 3360  (68.5%)

## A1 baseline (recomputed from grid)
- Weights: ra=0.35, rev=0.20, flw=0.15, risk×=1.00, min_alpha=4.0
- Train: Sharpe `1.705`, max DD `-33.7%`, total `737.5%`
- Test:  Sharpe `1.535`, max DD `-14.7%`, total `229.2%`
- Robust ratio: `0.900`
- Strong: n=`6`, unique=`3`, hit=`66.7%`, mean=`3.5%`

## Top combos (passing all filters, ranked by train Sharpe)
| Rank | ra_w | rev_w | flw_w | risk× | min_α | train Sharpe | train DD | train Total | test Sharpe | test DD | test Total | robust | Strong n / unique / hit |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:--|
| 1 | 0.35 | 0.20 | 0.15 | 1.75 | 2.5 | 1.903 | -28.3% | 776.8% | 1.569 | -14.3% | 235.8% | 0.824 | 23 / 9 / 56.5% |
| 2 | 0.40 | 0.30 | 0.05 | 2.00 | 2.5 | 1.899 | -27.5% | 905.3% | 1.659 | -15.4% | 258.8% | 0.873 | 28 / 10 / 53.6% |
| 3 | 0.40 | 0.30 | 0.05 | 2.00 | 3.0 | 1.899 | -27.5% | 905.3% | 1.659 | -15.4% | 258.8% | 0.873 | 18 / 7 / 55.6% |
| 4 | 0.35 | 0.25 | 0.05 | 1.75 | 2.5 | 1.891 | -28.1% | 897.2% | 1.655 | -15.4% | 257.6% | 0.875 | 19 / 7 / 57.9% |
| 5 | 0.35 | 0.30 | 0.15 | 2.00 | 2.5 | 1.888 | -25.7% | 901.0% | 1.623 | -17.4% | 247.7% | 0.859 | 30 / 9 / 53.3% |
| 6 | 0.35 | 0.30 | 0.15 | 2.00 | 3.0 | 1.888 | -25.7% | 901.0% | 1.623 | -17.4% | 247.7% | 0.859 | 17 / 6 / 52.9% |
| 7 | 0.40 | 0.25 | 0.20 | 2.00 | 2.5 | 1.888 | -29.0% | 771.7% | 1.612 | -14.3% | 246.6% | 0.854 | 36 / 12 / 61.1% |
| 8 | 0.40 | 0.25 | 0.20 | 2.00 | 3.0 | 1.888 | -29.0% | 771.7% | 1.612 | -14.3% | 246.6% | 0.854 | 25 / 9 / 56.0% |
| 9 | 0.40 | 0.30 | 0.10 | 2.00 | 3.0 | 1.886 | -27.5% | 878.2% | 1.649 | -16.6% | 257.2% | 0.874 | 20 / 7 / 55.0% |
| 10 | 0.40 | 0.30 | 0.10 | 2.00 | 2.5 | 1.886 | -27.5% | 878.2% | 1.649 | -16.6% | 257.2% | 0.874 | 34 / 12 / 55.9% |

## Sensitivity per dimension (median of robust-passing cells)

**By `ra_w`:**

| value | cells | train Sharpe (med) | test Sharpe (med) | test total (med) | test DD (med) |
|---:|---:|---:|---:|---:|---:|
| 0.3 | 560 | 1.621 | 1.651 | 258.0% | -14.6% |
| 0.35 | 560 | 1.622 | 1.623 | 253.3% | -14.7% |
| 0.4 | 560 | 1.581 | 1.613 | 248.5% | -15.0% |
| 0.45 | 560 | 1.580 | 1.617 | 245.3% | -15.0% |
| 0.5 | 560 | 1.580 | 1.603 | 249.0% | -15.5% |
| 0.55 | 560 | 1.560 | 1.601 | 249.0% | -15.5% |

**By `rev_w`:**

| value | cells | train Sharpe (med) | test Sharpe (med) | test total (med) | test DD (med) |
|---:|---:|---:|---:|---:|---:|
| 0.1 | 672 | 1.562 | 1.564 | 237.5% | -15.5% |
| 0.15 | 672 | 1.581 | 1.578 | 238.9% | -15.5% |
| 0.2 | 672 | 1.596 | 1.611 | 248.7% | -15.3% |
| 0.25 | 672 | 1.612 | 1.654 | 257.9% | -14.7% |
| 0.3 | 672 | 1.595 | 1.716 | 271.2% | -14.5% |

**By `flw_w`:**

| value | cells | train Sharpe (med) | test Sharpe (med) | test total (med) | test DD (med) |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 840 | 1.592 | 1.642 | 253.4% | -14.4% |
| 0.1 | 840 | 1.587 | 1.633 | 251.9% | -14.7% |
| 0.15 | 840 | 1.580 | 1.599 | 246.4% | -15.7% |
| 0.2 | 840 | 1.587 | 1.588 | 248.3% | -16.3% |

**By `risk_mult`:**

| value | cells | train Sharpe (med) | test Sharpe (med) | test total (med) | test DD (med) |
|---:|---:|---:|---:|---:|---:|
| 0.5 | 480 | 1.507 | 1.698 | 274.5% | -15.0% |
| 0.75 | 480 | 1.600 | 1.600 | 252.6% | -15.5% |
| 1.0 | 480 | 1.625 | 1.616 | 252.7% | -15.5% |
| 1.25 | 480 | 1.587 | 1.630 | 255.7% | -15.5% |
| 1.5 | 480 | 1.583 | 1.613 | 251.0% | -14.7% |
| 1.75 | 480 | 1.577 | 1.589 | 242.9% | -15.0% |
| 2.0 | 480 | 1.628 | 1.587 | 237.8% | -14.6% |

**By `min_alpha`:**

| value | cells | train Sharpe (med) | test Sharpe (med) | test total (med) | test DD (med) |
|---:|---:|---:|---:|---:|---:|
| 2.5 | 840 | 1.585 | 1.617 | 250.5% | -15.0% |
| 3.0 | 840 | 1.585 | 1.617 | 250.5% | -15.0% |
| 3.5 | 840 | 1.585 | 1.617 | 250.5% | -15.0% |
| 4.0 | 840 | 1.585 | 1.617 | 250.5% | -15.0% |

## Recommendation
Best combo by train Sharpe (also passes both filters):
```yaml
tier_weights:
  residual_alpha_score:        0.35
  revenue_confirmation_score:  0.20
  sector_relative_score:       0.00   # Phase A1: removed
  institutional_flow_score:    0.15
  narrative_score:             0.00   # Phase A1: removed
  capex_context_score:         0.05
# risk_penalty multiplier (apply in scoring): 1.75
# decision_zones[Strong].min_alpha:           2.5
```

- Train: Sharpe `1.903` / DD `-28.3%` / total `776.8%`
- Test:  Sharpe `1.569` / DD `-14.3%` / total `235.8%`
- Robust ratio: `0.824` (>= 0.8)
- Strong Candidate: n=`23`, unique=`9`, hit=`56.5%`