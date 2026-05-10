# Dashboard (Streamlit MVP)

Read-only research UI over the active baseline of `ai-supply-chain-alpha-lab` plus a two-step paper-portfolio rebalance flow.

**Not a trading system.** No broker integration, no live orders, no auto-schedule, no stop-loss.

## Run

```bash
cd ~/ai-supply-chain-alpha-lab
.venv/bin/streamlit run dashboard/app.py
```

Streamlit opens at <http://localhost:8501>.

## Localization

Decision-zone column and `suggested_action` column render in 繁體中文; CSV / JSON columns keep English keys for downstream consumers. Translation maps + the column-header help tooltip live in `dashboard/components/_columns.py` (`ZONE_LABELS_ZH`, `ACTION_LABELS_ZH`, `ZONE_DESCRIPTIONS_ZH`, `zone_help_text()`). The `決策區` column header shows a `?` icon — hover it to see all six zones explained at once. **When `_resolve_decision_zone` adds a new zone or wording (`fusion/scoring_model_v2.py:_resolve_decision_zone`), `ACTION_LABELS_ZH` must be updated to match exactly** — unmatched strings pass through unchanged so the UI never silently drops content, but they will appear in English.

## Pages

| Page | Source | Notes |
|---|---|---|
| Overview | `data/output/dashboard_data.json`, `paper_portfolio/rebalance_log.csv`, `risk_flags.csv` | NAV / DD / turnover / risk-count tiles + market regime |
| Alpha Ranking | `data/output/alpha_ranking.csv` | Ticker / theme / decision-zone / risk-severity filters |
| Current Portfolio | `paper_portfolio/target_weights.csv` | Table + theme exposure bar chart |
| Rebalance | `alpha_ranking.csv` + `target_weights.csv` + `rebalance_log.csv` | Two-step (preview → confirm) — see below |
| Performance | `paper_portfolio/rebalance_log.csv` | NAV multi-line + drawdown + per-period returns |
| Risk Flags | `risk_flags.csv` | Severity / flag / theme / ticker filters |
| Theme Exposure | `target_weights.csv` + `alpha_ranking.csv` + `risk_flags.csv` | Current weights, ranking-wide theme avg alpha, risk-flag counts |
| Report Viewer | `reports/paper_portfolio_report.md` | Markdown viewer with re-render button |

## Rebalance flow (paper)

The Rebalance page is a strict two-step state machine.

1. **Generate preview** — pure read. Uses `capex_alpha.paper_portfolio.compute_target_holdings()` and `estimate_one_way_cost()` to derive the proposed top-N. Shows side-by-side weights, base turnover, and estimated cost at 25 / 50 bps. **Never writes to disk.**
2. **Confirm** — gated by a checkbox stating "I understand this is a paper portfolio rebalance only…". When confirmed:
   1. Backs up the four files (`portfolio.csv`, `target_weights.csv`, `rebalance_log.csv`, `paper_portfolio_report.md`) into `archive/dashboard_rebalance_backup/<YYYYMMDD_HHMMSS>/`.
   2. Shells out to `scripts/run_paper_portfolio.py --rebalance --date <date> --notes "<notes>"` via `subprocess.run` using `sys.executable` (so it works under any venv).
   3. Captures stdout / stderr / returncode and surfaces them in the UI.
   4. Clears the data cache so the next page render reflects the new state.

If a rebalance for the chosen date already exists in `rebalance_log.csv`, a red duplicate-date warning is shown before the checkbox.

Subprocess errors are caught and displayed; the UI never crashes from a failing CLI run.

## Constraints (do not relax)

- No scoring, weight, or risk-logic changes live in `dashboard/`. All scoring stays in `src/capex_alpha/`.
- Preview never writes to disk.
- Confirm requires the checkbox **and** performs the backup before the subprocess call.
- No broker API, no live orders, no auto-schedule, no stop-loss.

## Tests

```bash
.venv/bin/python -m pytest -q tests/test_dashboard_data_loader.py tests/test_paper_portfolio_service.py
```

Both files mock the filesystem / subprocess so no live writes happen during the test run.
