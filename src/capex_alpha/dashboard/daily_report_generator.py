"""Render the daily research report (Markdown) from the dashboard payload."""
from __future__ import annotations

from typing import Any

from ..utils import ensure_dir, get_logger, load_yaml, resolve_path
from . import dashboard_data as dd

logger = get_logger(__name__)


def _fmt(x: Any, decimals: int = 2) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, (int,)):
        return str(x)
    if isinstance(x, float):
        return f"{x:.{decimals}f}"
    return str(x)


def _fmt_pct(x: Any) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%"


def _candidate_block(c: dict) -> str:
    drivers_pos = c.get("main_positive_drivers") or "—"
    drivers_neg = c.get("main_negative_drivers") or "—"
    risks = c.get("risk_flags") or "—"
    return (
        f"### {c.get('rank','?')}. {c['ticker']} {c.get('company_name','')}\n"
        f"- Theme: `{c.get('theme','?')}`  |  Decision: **{c.get('decision_zone','?')}**\n"
        f"- Alpha: `{_fmt(c.get('alpha_score'))}`  |  Confidence: `{_fmt(c.get('confidence_score'))}`\n"
        f"- Tier1 (residual alpha): `{_fmt(c.get('residual_alpha_score'))}`  |  "
        f"Tier2 (revenue): `{_fmt(c.get('revenue_confirmation_score'))}`  |  "
        f"Tier3 (narrative): `{_fmt(c.get('narrative_score'))}`\n"
        f"- Why: {drivers_pos}\n"
        f"- Risks: {drivers_neg if drivers_neg != '—' else risks}\n"
        f"- Action: {c.get('suggested_action','—')}\n"
    )


def render(payload: dict) -> str:
    cfg = load_yaml("config/dashboard_config.yaml")["report"]
    title = cfg["title"]
    as_of = payload["as_of_date"]

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append(f"_As of {as_of}._\n")

    # 1. Executive Summary
    lines.append("## 1. Executive Summary")
    n_strong = sum(1 for c in payload["top_alpha_candidates"] if c.get("decision_zone") == "Strong Candidate")
    n_watch = len(payload["watchlist"])
    n_narr = len(payload["narrative_watch"])
    n_risk = len(payload["risk_warnings"])
    lines.append(f"- Strong Candidates today: **{n_strong}**")
    lines.append(f"- Watchlist names: **{n_watch}**")
    lines.append(f"- Narrative-only Watch: **{n_narr}**")
    lines.append(f"- Risk warnings: **{n_risk}**\n")

    # 2. Regime
    lines.append("## 2. Market / AI Regime")
    mr = payload.get("market_regime", {})
    if mr:
        lines.append(f"- Date: `{mr.get('date','—')}`")
        lines.append(f"- Market regime: **{mr.get('market_regime','?')}**")
        lines.append(f"- AI regime: **{mr.get('ai_regime','?')}**")
        lines.append(f"- Risk level: **{mr.get('risk_level','?')}**")
        lines.append(f"- Recommended gross exposure: **{_fmt_pct(mr.get('recommended_gross_exposure'))}**")
        lines.append(f"- Recommended top_n: **{mr.get('recommended_top_n','—')}**")
        lines.append(f"- Notes: {mr.get('notes','—')}\n")
    else:
        lines.append("_No regime data._\n")

    # 3. Top Alpha Candidates
    lines.append("## 3. Top Alpha Candidates")
    if payload["top_alpha_candidates"]:
        for c in payload["top_alpha_candidates"]:
            lines.append(_candidate_block(c))
    else:
        lines.append("_No candidates today._\n")

    # 4. Signal Breakdown summary
    lines.append("## 4. Signal Breakdown (top 10)")
    lines.append("| Rank | Ticker | Theme | Tier1 | Tier2 Rev | Tier3 Narr | Risk | Alpha |")
    lines.append("|---:|:--|:--|---:|---:|---:|---:|---:|")
    for c in payload["top_alpha_candidates"][:10]:
        lines.append(
            f"| {c.get('rank','?')} | {c['ticker']} | {c.get('theme','?')} | "
            f"{_fmt(c.get('residual_alpha_score'))} | {_fmt(c.get('revenue_confirmation_score'))} | "
            f"{_fmt(c.get('narrative_score'))} | {_fmt(c.get('risk_penalty'))} | "
            f"{_fmt(c.get('alpha_score'))} |"
        )
    lines.append("")

    # 5. Narrative Watch
    lines.append("## 5. Narrative Watch")
    if payload["narrative_watch"]:
        for c in payload["narrative_watch"]:
            lines.append(f"- **{c['ticker']}** {c.get('company_name','')} — {c.get('main_positive_drivers','—')}")
    else:
        lines.append("_None today — narrative signals not strong enough on their own._")
    lines.append("")

    # 6. Risk Warnings
    lines.append("## 6. Risk Warnings")
    if payload["risk_warnings"]:
        for c in payload["risk_warnings"]:
            lines.append(
                f"- **{c['ticker']}** {c.get('company_name','')} — risk_penalty `{_fmt(c.get('risk_penalty'))}` "
                f"flags: {c.get('risk_flags','—')}"
            )
    else:
        lines.append("_None._")
    lines.append("")

    # 7. Theme Heatmap
    lines.append("## 7. Theme Heatmap")
    lines.append("| Theme | 20d Mom | 60d Mom | DD | #Names |")
    lines.append("|:--|---:|---:|---:|---:|")
    for t in payload.get("theme_heatmap", []):
        lines.append(
            f"| {t['theme']} | {_fmt_pct(t.get('momentum_20d'))} | {_fmt_pct(t.get('momentum_60d'))} | "
            f"{_fmt_pct(t.get('drawdown'))} | {t.get('num_constituents','—')} |"
        )
    lines.append("")

    # 8. Latest CAPEX Context
    lines.append("## 8. Latest CAPEX Context (context only, NOT a trigger)")
    cc = payload.get("latest_capex_context", {})
    if cc:
        lines.append(f"- Event: `{cc.get('event_date','—')}`")
        lines.append(f"- Type: **{cc.get('context_type','—')}**")
        lines.append(f"- Themes: {cc.get('affected_themes','—')}")
        lines.append(f"- Score (capped ±0.5): `{_fmt(cc.get('context_score'))}`")
        lines.append(f"- Notes: {cc.get('notes','—')}")
    else:
        lines.append("_No recent CAPEX events._")
    lines.append("")

    # 9. Model Confidence / Factor Health
    lines.append("## 9. Model Confidence / Factor Health")
    fh = payload.get("factor_health", {})
    if fh:
        lines.append("| Factor | Non-null % | Mean | Max |")
        lines.append("|:--|---:|---:|---:|")
        for k, v in fh.items():
            lines.append(f"| {k} | {_fmt_pct(v.get('non_null_pct'))} | {_fmt(v.get('mean'))} | {_fmt(v.get('max'))} |")
    lines.append("")

    # 10. Suggested Next Actions
    lines.append("## 10. Suggested Next Actions")
    lines.append("- Review Strong Candidates against fundamentals before sizing.")
    lines.append("- Watch named Risk Warnings for potential exits / reductions.")
    lines.append("- Cross-check Narrative Watch names with quant for confirmation in the next 1–2 weeks.")
    lines.append("- CAPEX context is informational only — do not trigger trades from it.")
    lines.append("")

    # Reminder block
    lines.append("---")
    lines.append("_Reminders:_")
    for note in payload.get("model_notes", []):
        lines.append(f"- {note}")

    return "\n".join(lines)


def run(write: bool = True, payload: dict | None = None) -> str:
    if payload is None:
        payload = dd.run(write=False)

    text = render(payload)

    if write:
        cfg = load_yaml("config/dashboard_config.yaml")["output"]
        ensure_dir("reports")
        path = resolve_path(cfg["report_path"])
        path.write_text(text, encoding="utf-8")
        # Also drop a copy into data/output for convenience
        ensure_dir("data/output")
        resolve_path("data/output/daily_alpha_report.md").write_text(text, encoding="utf-8")
        logger.info("Wrote %s", path)

    return text
