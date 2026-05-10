"""Paper Portfolio MVP — operational shadow-tracking layer.

This module is **not** part of the active scoring path. It reads the latest
``alpha_ranking.csv`` (or any walk-forward results frame) and computes a
top-N paper portfolio with the active theme cap. Persists three CSVs +
a Markdown research report.

Files (all under ``data/output/paper_portfolio/`` by default):
- ``portfolio.csv``      — long format: one row per (rebalance_date, ticker)
- ``target_weights.csv`` — latest rebalance's target holdings only
- ``rebalance_log.csv``  — one row per rebalance event (NAV, turnover, cost)

Report: ``reports/paper_portfolio_report.md``.

Workflows
---------
- ``backfill`` — replay all walk-forward rebalances as if we'd been running
  paper portfolio from start. Initializes NAV = 1.0; populates 70 months of
  history; useful for the user's first run.
- ``rebalance`` — at the next rebalance date, compute new targets from the
  current alpha_ranking + close out the previous period using observed
  prices since last rebalance. Operational monthly workflow.
- ``report`` — re-render the markdown report from current state.

NOT a trading system. No order execution. No live data feeds beyond the
existing yfinance-cached prices.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .data_loader import get_close_panel, load_universe
from .utils import ensure_dir, get_logger, resolve_path

logger = get_logger(__name__)


DEFAULT_PAPER_DIR = "data/output/paper_portfolio"
DEFAULT_REPORT_PATH = "reports/paper_portfolio_report.md"
COSTS_BPS_TRACKED: tuple[float, ...] = (25.0, 50.0)
BENCHMARK_TICKER = "0050.TW"


# ---------------------------------------------------------------------------
# State

PORTFOLIO_COLS = [
    "rebalance_date", "ticker", "company_name", "theme",
    "target_weight", "prev_weight", "weight_change",
    "alpha_score", "decision_zone", "residual_alpha_score",
    "risk_penalty", "fwd_return_1m", "notes",
]

LOG_COLS = [
    "rebalance_date", "n_holdings", "gross_exposure",
    "base_turnover", "est_cost_25bps", "est_cost_50bps",
    "slippage_placeholder", "period_return",
    "period_return_25bps", "period_return_50bps",
    "benchmark_return", "excess_vs_benchmark",
    "nav_paper", "nav_paper_25bps", "nav_paper_50bps",
    "nav_benchmark", "drawdown_paper", "notes",
]

TARGET_COLS = [
    "ticker", "company_name", "theme", "target_weight",
    "alpha_score", "decision_zone", "risk_flags", "notes",
]


@dataclass
class PaperPortfolioState:
    portfolio: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=PORTFOLIO_COLS))
    log: pd.DataFrame       = field(default_factory=lambda: pd.DataFrame(columns=LOG_COLS))
    target: pd.DataFrame    = field(default_factory=lambda: pd.DataFrame(columns=TARGET_COLS))

    @property
    def latest_rebalance_date(self) -> pd.Timestamp | None:
        if self.log.empty:
            return None
        return pd.Timestamp(self.log["rebalance_date"].max())

    @property
    def n_rebalances(self) -> int:
        return int(len(self.log))

    @property
    def latest_nav(self) -> float:
        if self.log.empty:
            return 1.0
        return float(self.log["nav_paper"].iloc[-1])


def _empty_state() -> PaperPortfolioState:
    return PaperPortfolioState()


def load_state(output_dir: str = DEFAULT_PAPER_DIR) -> PaperPortfolioState:
    """Load existing paper portfolio state from disk; returns empty if absent."""
    p_dir = resolve_path(output_dir)
    state = _empty_state()
    if not p_dir.exists():
        return state
    portfolio_p = p_dir / "portfolio.csv"
    log_p = p_dir / "rebalance_log.csv"
    target_p = p_dir / "target_weights.csv"
    if portfolio_p.exists():
        state.portfolio = pd.read_csv(portfolio_p, parse_dates=["rebalance_date"])
    if log_p.exists():
        state.log = pd.read_csv(log_p, parse_dates=["rebalance_date"])
    if target_p.exists():
        state.target = pd.read_csv(target_p)
    return state


def write_state(state: PaperPortfolioState,
                output_dir: str = DEFAULT_PAPER_DIR) -> None:
    """Persist state to disk (overwrites)."""
    p_dir = ensure_dir(output_dir)
    state.portfolio.sort_values(["rebalance_date", "target_weight"], ascending=[True, False]).to_csv(
        p_dir / "portfolio.csv", index=False)
    state.log.sort_values("rebalance_date").to_csv(p_dir / "rebalance_log.csv", index=False)
    state.target.to_csv(p_dir / "target_weights.csv", index=False)
    logger.info("Wrote paper portfolio state to %s/", p_dir)


# ---------------------------------------------------------------------------
# Target selection (mirrors active baseline: top-N EW with theme cap)

def compute_target_holdings(
    ranking: pd.DataFrame,
    theme_map: dict,
    top_n: int = 5,
    max_per_theme: int = 2,
) -> pd.DataFrame:
    """Greedy top-N selection respecting per-theme cap. Returns DataFrame
    with `ticker, target_weight, alpha_score, decision_zone, theme,
    company_name, residual_alpha_score, risk_penalty`."""
    if ranking.empty:
        return pd.DataFrame(columns=TARGET_COLS)
    df = ranking.dropna(subset=["alpha_score"]).sort_values("alpha_score", ascending=False)
    picks: list[str] = []
    theme_count: dict[str, int] = {}
    for _, r in df.iterrows():
        ticker = r["ticker"]
        theme = theme_map.get(ticker, "unknown")
        if theme_count.get(theme, 0) >= max_per_theme:
            continue
        picks.append(ticker)
        theme_count[theme] = theme_count.get(theme, 0) + 1
        if len(picks) >= top_n:
            break
    if not picks:
        return pd.DataFrame()
    selected = df[df["ticker"].isin(picks)].copy()
    selected["target_weight"] = 1.0 / len(picks)
    keep = ["ticker", "company_name", "theme", "target_weight", "alpha_score",
            "decision_zone", "residual_alpha_score", "risk_penalty"]
    have = [c for c in keep if c in selected.columns]
    return selected[have].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Cost + return helpers

def estimate_one_way_cost(
    new_weights: dict[str, float],
    prev_weights: dict[str, float],
    cost_bps: float,
) -> float:
    """One-way cost = 0.5 × Σ|w_new − w_old| × cost_bps / 10000.
    For a fully-invested portfolio this equals the fraction of NAV rotated."""
    all_tickers = set(new_weights) | set(prev_weights)
    delta_l1 = sum(abs(new_weights.get(t, 0.0) - prev_weights.get(t, 0.0)) for t in all_tickers)
    one_way_fraction = 0.5 * delta_l1
    return float(one_way_fraction * cost_bps / 10000.0)


def realized_period_return(
    weights: dict[str, float],
    from_date: pd.Timestamp,
    to_date: pd.Timestamp,
    price_panel: pd.DataFrame,
) -> float:
    """Σ_i w_i × (P_i(to) / P_i(from) - 1). Tickers with missing data → 0%."""
    if not weights or from_date is None or to_date is None:
        return 0.0
    total = 0.0
    for ticker, w in weights.items():
        ret = 0.0
        if ticker in price_panel.columns:
            s = price_panel[ticker]
            try:
                p_from = float(s.asof(from_date))
                p_to = float(s.asof(to_date))
                if pd.notna(p_from) and pd.notna(p_to) and p_from > 0:
                    ret = p_to / p_from - 1.0
            except Exception:
                ret = 0.0
        total += w * ret
    return float(total)


# ---------------------------------------------------------------------------
# Append a rebalance event

def append_rebalance(
    state: PaperPortfolioState,
    rebalance_date: pd.Timestamp,
    new_targets: pd.DataFrame,
    price_panel: pd.DataFrame,
    benchmark_panel: pd.DataFrame,
    risk_flags_df: pd.DataFrame | None = None,
    notes: str = "",
    overwrite_same_date: bool = True,
) -> PaperPortfolioState:
    """Append a new rebalance event. Computes period return from previous
    holdings (held from prev_date to rebalance_date). NAV / drawdown updated."""
    rebalance_date = pd.Timestamp(rebalance_date)

    # Handle duplicate date (overwrite)
    if overwrite_same_date and not state.log.empty:
        if (state.log["rebalance_date"] == rebalance_date).any():
            state.log = state.log[state.log["rebalance_date"] != rebalance_date]
            state.portfolio = state.portfolio[state.portfolio["rebalance_date"] != rebalance_date]

    # Previous state
    if state.log.empty:
        prev_weights: dict[str, float] = {}
        prev_date = None
        prev_nav = prev_nav_25 = prev_nav_50 = prev_nav_bench = 1.0
    else:
        prev_date = pd.Timestamp(state.log["rebalance_date"].max())
        prev_portfolio = state.portfolio[state.portfolio["rebalance_date"] == prev_date]
        prev_weights = dict(zip(prev_portfolio["ticker"], prev_portfolio["target_weight"]))
        prev_row = state.log.iloc[-1]
        prev_nav = float(prev_row["nav_paper"])
        prev_nav_25 = float(prev_row["nav_paper_25bps"])
        prev_nav_50 = float(prev_row["nav_paper_50bps"])
        prev_nav_bench = float(prev_row["nav_benchmark"])

    # Realized return from previous holdings
    if prev_date is not None and prev_weights:
        period_return = realized_period_return(prev_weights, prev_date, rebalance_date, price_panel)
        bench_period = realized_period_return(
            {BENCHMARK_TICKER: 1.0}, prev_date, rebalance_date, benchmark_panel
        )
    else:
        period_return = 0.0
        bench_period = 0.0

    # New target weights
    new_weights = dict(zip(new_targets["ticker"], new_targets["target_weight"])) if not new_targets.empty else {}

    # Costs
    cost_25 = estimate_one_way_cost(new_weights, prev_weights, 25.0)
    cost_50 = estimate_one_way_cost(new_weights, prev_weights, 50.0)

    # NAVs
    new_nav = prev_nav * (1.0 + period_return)
    new_nav_25 = prev_nav_25 * (1.0 + period_return - cost_25)
    new_nav_50 = prev_nav_50 * (1.0 + period_return - cost_50)
    new_nav_bench = prev_nav_bench * (1.0 + bench_period)

    # Drawdown computed against running peak of paper (gross) NAV
    if state.log.empty:
        running_peak = max(new_nav, 1.0)
    else:
        running_peak = max(float(state.log["nav_paper"].cummax().iloc[-1]), new_nav)
    drawdown = new_nav / running_peak - 1.0

    # Turnover (one-way)
    delta_l1 = sum(abs(new_weights.get(t, 0.0) - prev_weights.get(t, 0.0))
                   for t in set(new_weights) | set(prev_weights))
    base_turnover = 0.5 * delta_l1

    # Append log row
    log_row = {
        "rebalance_date":      rebalance_date,
        "n_holdings":          len(new_weights),
        "gross_exposure":      sum(new_weights.values()),
        "base_turnover":       base_turnover,
        "est_cost_25bps":      cost_25,
        "est_cost_50bps":      cost_50,
        "slippage_placeholder": 0.0,
        "period_return":       period_return,
        "period_return_25bps": period_return - cost_25,
        "period_return_50bps": period_return - cost_50,
        "benchmark_return":    bench_period,
        "excess_vs_benchmark": period_return - bench_period,
        "nav_paper":           new_nav,
        "nav_paper_25bps":     new_nav_25,
        "nav_paper_50bps":     new_nav_50,
        "nav_benchmark":       new_nav_bench,
        "drawdown_paper":      drawdown,
        "notes":               notes,
    }
    state.log = pd.concat([state.log, pd.DataFrame([log_row])[LOG_COLS]], ignore_index=True)

    # Append portfolio rows
    rows = []
    risk_flag_lookup: dict[str, str] = {}
    if risk_flags_df is not None and not risk_flags_df.empty:
        grouped = risk_flags_df.groupby("ticker")
        for t, g in grouped:
            risk_flag_lookup[t] = ";".join(
                f"{r['risk_flag']}({r['severity']})" for _, r in g.iterrows()
            )

    for _, r in new_targets.iterrows():
        ticker = r["ticker"]
        target_w = float(new_weights.get(ticker, 0.0))
        prev_w = float(prev_weights.get(ticker, 0.0))
        rows.append({
            "rebalance_date":       rebalance_date,
            "ticker":               ticker,
            "company_name":         r.get("company_name", ""),
            "theme":                r.get("theme", ""),
            "target_weight":        target_w,
            "prev_weight":          prev_w,
            "weight_change":        target_w - prev_w,
            "alpha_score":          float(r.get("alpha_score", float("nan"))),
            "decision_zone":        r.get("decision_zone", ""),
            "residual_alpha_score": float(r.get("residual_alpha_score", float("nan"))),
            "risk_penalty":         float(r.get("risk_penalty", float("nan"))),
            "fwd_return_1m":        float("nan"),  # back-filled at next rebalance
            "notes":                notes,
        })
    if rows:
        state.portfolio = pd.concat(
            [state.portfolio, pd.DataFrame(rows)[PORTFOLIO_COLS]], ignore_index=True
        )

    # Back-fill fwd_return_1m for the previous period's tickers
    if prev_date is not None and prev_weights:
        mask = state.portfolio["rebalance_date"] == prev_date
        for ticker, w in prev_weights.items():
            tmask = mask & (state.portfolio["ticker"] == ticker)
            if tmask.any() and ticker in price_panel.columns:
                s = price_panel[ticker]
                p_from = float(s.asof(prev_date))
                p_to = float(s.asof(rebalance_date))
                if pd.notna(p_from) and pd.notna(p_to) and p_from > 0:
                    state.portfolio.loc[tmask, "fwd_return_1m"] = float(p_to / p_from - 1.0)

    # Update target_weights (latest only)
    new_targets_for_state = new_targets.copy()
    new_targets_for_state["risk_flags"] = new_targets_for_state["ticker"].map(risk_flag_lookup).fillna("")
    new_targets_for_state["notes"] = notes
    keep = [c for c in TARGET_COLS if c in new_targets_for_state.columns]
    state.target = new_targets_for_state[keep].copy()

    return state


# ---------------------------------------------------------------------------
# Backfill from walk-forward

def backfill_from_walk_forward(
    walk_forward_df: pd.DataFrame,
    universe_df: pd.DataFrame | None = None,
    price_panel: pd.DataFrame | None = None,
    benchmark_panel: pd.DataFrame | None = None,
    risk_flags_df: pd.DataFrame | None = None,
    top_n: int = 5,
    max_per_theme: int = 2,
    output_dir: str = DEFAULT_PAPER_DIR,
    write: bool = True,
) -> PaperPortfolioState:
    """Replay all walk-forward rebalances as a paper portfolio. Starts NAV=1.0."""
    if universe_df is None:
        universe_df = load_universe()
    theme_map = universe_df.set_index("ticker")["theme"].to_dict()

    if price_panel is None:
        price_panel = get_close_panel(universe_df["ticker"].tolist())
    if benchmark_panel is None:
        benchmark_panel = get_close_panel([BENCHMARK_TICKER])

    state = _empty_state()
    rebalance_dates = sorted(walk_forward_df["rebalance_date"].unique())
    logger.info("Backfilling %d rebalance dates …", len(rebalance_dates))
    for rd in rebalance_dates:
        ranking = walk_forward_df[walk_forward_df["rebalance_date"] == rd]
        targets = compute_target_holdings(ranking, theme_map,
                                          top_n=top_n, max_per_theme=max_per_theme)
        if targets.empty:
            continue
        state = append_rebalance(
            state, pd.Timestamp(rd), targets,
            price_panel, benchmark_panel,
            risk_flags_df=risk_flags_df,
            notes="backfill",
        )

    if write:
        write_state(state, output_dir)
    return state


# ---------------------------------------------------------------------------
# Operational rebalance — appends ONE new rebalance to an existing state

def run_one_rebalance(
    rebalance_date: pd.Timestamp,
    ranking_csv: str = "data/output/alpha_ranking.csv",
    risk_flags_csv: str = "data/output/risk_flags.csv",
    output_dir: str = DEFAULT_PAPER_DIR,
    top_n: int = 5,
    max_per_theme: int = 2,
    notes: str = "",
    write: bool = True,
) -> PaperPortfolioState:
    state = load_state(output_dir)
    universe_df = load_universe()
    theme_map = universe_df.set_index("ticker")["theme"].to_dict()

    ranking = pd.read_csv(resolve_path(ranking_csv))
    risk_path = resolve_path(risk_flags_csv)
    risk_df = pd.read_csv(risk_path) if risk_path.exists() else None

    price_panel = get_close_panel(universe_df["ticker"].tolist())
    benchmark_panel = get_close_panel([BENCHMARK_TICKER])

    targets = compute_target_holdings(ranking, theme_map,
                                      top_n=top_n, max_per_theme=max_per_theme)
    state = append_rebalance(
        state, rebalance_date, targets,
        price_panel, benchmark_panel,
        risk_flags_df=risk_df, notes=notes,
    )
    if write:
        write_state(state, output_dir)
    return state


# ---------------------------------------------------------------------------
# Report rendering

def _fmt_pct(x: float, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{x * 100:.{decimals}f}%"


def _fmt(x, decimals: int = 3) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    return f"{float(x):.{decimals}f}"


def render_report(state: PaperPortfolioState,
                  output_path: str = DEFAULT_REPORT_PATH) -> str:
    if state.log.empty:
        text = "# Paper Portfolio Report\n\n_No rebalance history yet — run --backfill or --rebalance first._"
    else:
        text = _render(state)
    p = resolve_path(output_path)
    ensure_dir(p.parent)
    p.write_text(text, encoding="utf-8")
    logger.info("Wrote %s", p)
    return text


def _render(state: PaperPortfolioState) -> str:
    log = state.log
    portfolio = state.portfolio
    target = state.target
    latest = log.iloc[-1]
    latest_date = pd.Timestamp(latest["rebalance_date"])

    L: list[str] = []
    L.append("# Paper Portfolio Report")
    L.append(f"_As of rebalance {latest_date.strftime('%Y-%m-%d')}, {len(log)} rebalances tracked. "
             "Shadow tracking only — no real orders placed._\n")

    # ─── Section 1: NAV
    L.append("## 1. Portfolio NAV")
    L.append("| Variant | NAV | Total Return | vs Benchmark |")
    L.append("|---|---:|---:|---:|")
    for label, key in [("Paper (gross)", "nav_paper"),
                        ("Paper @ 25 bps", "nav_paper_25bps"),
                        ("Paper @ 50 bps", "nav_paper_50bps"),
                        ("0050.TW Benchmark", "nav_benchmark")]:
        nav = float(latest[key])
        bench_nav = float(latest["nav_benchmark"])
        L.append(f"| {label} | `{nav:.4f}` | `{(nav - 1.0) * 100:+.2f}%` | "
                 f"`{(nav - bench_nav) * 100:+.2f}%` |")
    L.append("")

    # ─── Section 2: Current holdings
    L.append("## 2. Current Holdings (target weights for next period)")
    if target.empty:
        L.append("_No current target — empty portfolio._\n")
    else:
        L.append("| Ticker | Company | Theme | Target | α | Zone | Risk Flags |")
        L.append("|---|---|---|---:|---:|---|---|")
        for _, r in target.iterrows():
            L.append(f"| {r['ticker']} | {r.get('company_name','')} | {r['theme']} | "
                     f"{r['target_weight']*100:.1f}% | {_fmt(r.get('alpha_score'), 2)} | "
                     f"{r.get('decision_zone','—')} | {r.get('risk_flags','—')} |")
        L.append("")

    # ─── Section 3: Changes vs previous rebalance
    if len(log) >= 2:
        prev_date = pd.Timestamp(log.iloc[-2]["rebalance_date"])
        prev_holdings = portfolio[portfolio["rebalance_date"] == prev_date]
        prev_set = set(prev_holdings["ticker"])
        curr_set = set(target["ticker"])
        new_buys = sorted(curr_set - prev_set)
        sells = sorted(prev_set - curr_set)
        unchanged = sorted(curr_set & prev_set)

        L.append("## 3. Changes vs Previous Rebalance")
        L.append(f"- **New buys ({len(new_buys)}):** {', '.join(new_buys) if new_buys else '—'}")
        L.append(f"- **Sells ({len(sells)}):** {', '.join(sells) if sells else '—'}")
        L.append(f"- **Unchanged ({len(unchanged)}):** {', '.join(unchanged) if unchanged else '—'}")
        L.append("")

        # Sell P&L
        if sells:
            L.append("## 3a. Realized P&L on Sold Names (held last period)")
            L.append("| Ticker | Theme | Period Return |")
            L.append("|---|---|---:|")
            for t in sells:
                row = prev_holdings[prev_holdings["ticker"] == t].iloc[0]
                fwd = row.get("fwd_return_1m", float("nan"))
                L.append(f"| {t} | {row.get('theme','')} | {_fmt_pct(fwd)} |")
            L.append("")

    # ─── Section 4: Top score drivers
    L.append("## 4. Top Score Drivers (current holdings)")
    if not target.empty:
        L.append("| Ticker | α | Residual α | Risk Penalty |")
        L.append("|---|---:|---:|---:|")
        # Need to look up residual_alpha_score and risk_penalty from portfolio (latest rebalance)
        latest_holdings = portfolio[portfolio["rebalance_date"] == latest_date]
        for _, r in latest_holdings.iterrows():
            L.append(f"| {r['ticker']} | {_fmt(r['alpha_score'], 2)} | "
                     f"{_fmt(r['residual_alpha_score'], 2)} | "
                     f"{_fmt(r['risk_penalty'], 2)} |")
        L.append("")

    # ─── Section 5: Theme exposure
    L.append("## 5. Theme Exposure")
    if not target.empty:
        L.append("| Theme | Weight | # Holdings |")
        L.append("|---|---:|---:|")
        for theme, sub in target.groupby("theme"):
            w_total = float(sub["target_weight"].sum())
            L.append(f"| {theme} | {w_total*100:.1f}% | {len(sub)} |")
        L.append("")

    # ─── Section 6: Latest rebalance stats
    L.append("## 6. Latest Rebalance Stats")
    L.append(f"- One-way turnover: `{_fmt_pct(latest['base_turnover'])}`")
    L.append(f"- Estimated cost @ 25 bps: `{_fmt_pct(latest['est_cost_25bps'], 3)}`")
    L.append(f"- Estimated cost @ 50 bps: `{_fmt_pct(latest['est_cost_50bps'], 3)}`")
    L.append(f"- Slippage placeholder: `{_fmt_pct(latest['slippage_placeholder'], 3)}` "
             "_(set to 0; populate manually after live observation)_")
    L.append(f"- Period return (gross): `{_fmt_pct(latest['period_return'])}`")
    L.append(f"- Benchmark period return: `{_fmt_pct(latest['benchmark_return'])}`")
    L.append(f"- **Excess vs 0050: `{_fmt_pct(latest['excess_vs_benchmark'])}`**")
    L.append(f"- Drawdown (paper, gross): `{_fmt_pct(latest['drawdown_paper'])}`")
    L.append("")

    # ─── Section 7: Cumulative performance
    L.append("## 7. Cumulative Performance Summary")
    n = len(log)
    nav_paper = float(latest["nav_paper"])
    nav_bench = float(latest["nav_benchmark"])
    if n > 1:
        years = (n - 1) / 12.0
        cagr_paper = (nav_paper ** (1.0 / years) - 1.0) if years > 0 else 0.0
        cagr_bench = (nav_bench ** (1.0 / years) - 1.0) if years > 0 else 0.0
        nav_series = log["nav_paper"]
        max_dd = float((nav_series / nav_series.cummax() - 1.0).min())
        ret_series = log["period_return"]
        positive = int((ret_series > 0).sum())
        L.append(f"- # rebalances: **{n}**")
        L.append(f"- Period covered: ~{years:.2f} years")
        L.append(f"- **CAGR (gross paper): `{_fmt_pct(cagr_paper)}`**")
        L.append(f"- CAGR (benchmark): `{_fmt_pct(cagr_bench)}`")
        L.append(f"- Excess CAGR vs benchmark: **`{_fmt_pct(cagr_paper - cagr_bench)}`**")
        L.append(f"- Max drawdown (paper, gross): `{_fmt_pct(max_dd)}`")
        L.append(f"- Positive months: {positive} / {n - 1}")
        L.append(f"- Cumulative cost @ 25 bps: `{_fmt_pct(log['est_cost_25bps'].sum())}`")
        L.append(f"- Cumulative cost @ 50 bps: `{_fmt_pct(log['est_cost_50bps'].sum())}`")
    L.append("")

    # ─── Section 8: Notes for manual review
    L.append("## 8. Notes for Manual Review")
    L.append("- Slippage column in `rebalance_log.csv` is a placeholder (0.0). After observing real fills, "
             "edit that column to capture realized slippage and re-run the report.")
    L.append("- `notes` column is free-form — append manual observations (e.g. order rejections, partial "
             "fills, market events) per rebalance date.")
    L.append("- Period return uses close-to-close prices on rebalance dates, NOT execution prices. "
             "Real-world fills may differ.")
    L.append("- No exposure scaling, no stop-loss, no cluster cap — reflects active baseline as of "
             "Phase A2-adopt + gate repair.")
    L.append("")
    L.append("---")
    L.append("_Generated by `paper_portfolio.render_report`. Active baseline: residual_alpha=0.50, "
             "rev=flw=narr=sec=0, capex_context=0.05, risk_penalty_multiplier=0.75, "
             "theme cap (max 2/theme), top-5 EW, no exposure scaling. "
             "Shadow only — not a trading system._")
    return "\n".join(L)
