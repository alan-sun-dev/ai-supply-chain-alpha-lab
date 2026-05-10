"""Scoring Model v2 — combines factor model + narrative + risk into a single
``alpha_score`` per ticker, plus a ``decision_zone`` derived through the
signal-hierarchy gates.

Inputs (from upstream modules; can be passed in or built fresh):
- factor_model_v2 long-format frame
- narrative_signals_aggregated frame
- risk_flags frame
- regime_status (single row)

Output: ``data/output/alpha_ranking.csv`` (one row per ticker).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data_loader import load_universe
from ..narrative import narrative_scorer as ns_mod
from ..quant import factor_model_v2 as fm
from ..quant import regime_filter as rf
from ..quant import residual_alpha as ra
from ..quant import risk_model as rm
from ..utils import ensure_dir, get_logger, load_yaml, resolve_path
from .signal_hierarchy import TierScores

logger = get_logger(__name__)


# ---------------------------------------------------------------------------

def _factor_pivot(factor_df: pd.DataFrame) -> pd.DataFrame:
    """Wide pivot keyed by ticker. Columns are factor_contribution by name."""
    if factor_df.empty:
        return pd.DataFrame()
    pivot = factor_df.pivot_table(
        index="ticker", columns="factor_name", values="factor_contribution", aggfunc="last"
    ).fillna(0.0)
    pivot.columns = [f"{c}_contrib" for c in pivot.columns]
    return pivot.reset_index()


def _residual_alpha_score(factor_pivot: pd.DataFrame) -> pd.Series:
    """Aggregate the residual-momentum + drawdown-recovery + vol-contraction
    pieces into a single Tier-1 score.
    """
    cols = [
        "residual_momentum_60d_contrib",
        "residual_momentum_20d_contrib",
        "drawdown_recovery_contrib",
        "volatility_contraction_contrib",
    ]
    have = [c for c in cols if c in factor_pivot.columns]
    if not have:
        return pd.Series(0.0, index=factor_pivot["ticker"])
    s = factor_pivot[have].sum(axis=1)
    s.index = factor_pivot["ticker"]
    return s


def _revenue_confirmation_score(factor_pivot: pd.DataFrame) -> pd.Series:
    cols = ["revenue_acceleration_contrib"]
    have = [c for c in cols if c in factor_pivot.columns]
    if not have:
        return pd.Series(0.0, index=factor_pivot["ticker"])
    s = factor_pivot[have].sum(axis=1)
    s.index = factor_pivot["ticker"]
    return s


def _sector_relative_score(factor_pivot: pd.DataFrame) -> pd.Series:
    if "sector_relative_strength_contrib" not in factor_pivot.columns:
        return pd.Series(0.0, index=factor_pivot["ticker"])
    s = factor_pivot["sector_relative_strength_contrib"]
    s.index = factor_pivot["ticker"]
    return s


def _institutional_flow_score(factor_pivot: pd.DataFrame) -> pd.Series:
    if "institutional_flow_score_contrib" not in factor_pivot.columns:
        return pd.Series(0.0, index=factor_pivot["ticker"])
    s = factor_pivot["institutional_flow_score_contrib"]
    s.index = factor_pivot["ticker"]
    return s


def _theme_strength_score(factor_pivot: pd.DataFrame) -> pd.Series:
    if "theme_strength_contrib" not in factor_pivot.columns:
        return pd.Series(0.0, index=factor_pivot["ticker"])
    s = factor_pivot["theme_strength_contrib"]
    s.index = factor_pivot["ticker"]
    return s


def _valuation_penalty(factor_pivot: pd.DataFrame) -> pd.Series:
    """Negative-weight factor → already a penalty in factor_contribution."""
    if "valuation_risk_score_contrib" not in factor_pivot.columns:
        return pd.Series(0.0, index=factor_pivot["ticker"])
    s = factor_pivot["valuation_risk_score_contrib"]
    s.index = factor_pivot["ticker"]
    return s


# ---------------------------------------------------------------------------

def _zone_threshold(cfg: dict, name: str, field: str, default):
    """Pull a threshold from cfg['scoring_v2']['decision_zones'] by zone name.

    Falls back to ``default`` if YAML omits the field, so older configs keep
    working unchanged. Returns ``default``'s type — no float coercion since
    fields like ``require_residual_positive`` are bool.
    """
    zones = cfg.get("scoring_v2", {}).get("decision_zones", []) or []
    for z in zones:
        if z.get("name") == name and field in z:
            v = z[field]
            if isinstance(default, bool):
                return bool(v)
            try:
                return float(v)
            except (TypeError, ValueError):
                return default
    return default


def _resolve_decision_zone(tiers: TierScores, alpha: float, confidence: float, cfg: dict) -> tuple[str, str]:
    """Apply hierarchy gates → (decision_zone, suggested_action).

    Gate-repair (2026-05-03) — gates redesigned to work under the
    Simplest-Robust active baseline (rev_w = flw_w = 0). All thresholds are
    YAML-driven (``scoring_v2.decision_zones``). Sensible defaults match the
    current model's distributions when YAML omits a field.

    Hierarchy (first match wins):
    - alpha < 0                                                              → Avoid
    - chasing setup (overbought OR valuation_extreme) AND high severity     → Avoid Chasing
    - strong: alpha + residual + risk caps + confidence + not blocked       → Strong Candidate
    - narrative-only path (legacy; no-op when narrative weight is 0)        → Narrative Watch
    - positive setup: alpha + positive residual + acceptable risk           → Watchlist
    - blocked by risk but otherwise watch-quality                            → Watchlist (capped)
    - default                                                                → Neutral
    """
    # --- Strong thresholds
    strong_alpha   = _zone_threshold(cfg, "Strong Candidate", "min_alpha", 2.5)
    strong_conf    = _zone_threshold(cfg, "Strong Candidate", "min_confidence", 2.5)
    strong_resid   = _zone_threshold(cfg, "Strong Candidate", "min_residual_alpha", 1.5)
    strong_max_rp  = _zone_threshold(cfg, "Strong Candidate", "max_risk_penalty", 2.0)

    # --- Watchlist thresholds
    watch_alpha   = _zone_threshold(cfg, "Watchlist", "min_alpha", 2.0)
    watch_conf    = _zone_threshold(cfg, "Watchlist", "min_confidence", 2.0)
    watch_max_rp  = _zone_threshold(cfg, "Watchlist", "max_risk_penalty", 4.0)
    watch_req_residual = _zone_threshold(cfg, "Watchlist", "require_residual_positive", True)

    # --- Avoid Chasing thresholds
    chase_min_severity   = _zone_threshold(cfg, "Avoid Chasing", "min_risk_severity", 5)
    chase_require_flag   = _zone_threshold(cfg, "Avoid Chasing",
                                           "require_overbought_or_valuation_extreme", True)

    # 1. Outright avoid: negative alpha
    if alpha < 0:
        return "Avoid", "Skip — negative residual alpha. Wait for setup change."

    # 2. Avoid Chasing: actual chasing-risk indicators (overbought / valuation_extreme + severity)
    if chase_require_flag:
        is_chasing = (
            (tiers.overbought_flag or tiers.valuation_extreme_flag)
            and tiers.tier4_risk_severity >= chase_min_severity
        )
    else:
        # Fall-back: severity-only chasing detection
        is_chasing = tiers.tier4_risk_severity >= chase_min_severity
    if is_chasing:
        return "Avoid Chasing", "Overbought or valuation-extreme + high risk severity — do not chase."

    # 3. Strong Candidate: high alpha, strong residual, risk under cap, not blocked
    if (
        alpha >= strong_alpha
        and confidence >= strong_conf
        and tiers.tier1_residual_alpha >= strong_resid
        and tiers.risk_penalty <= strong_max_rp
        and not tiers.tier4_blocking
    ):
        return "Strong Candidate", "Research priority — high residual alpha, low risk."

    # 4. Narrative Watch (legacy; no-op when narrative weight is 0)
    if tiers.narrative_only and tiers.tier3_narrative >= 1.5:
        return "Narrative Watch", "News flow positive but quant not confirming — track only."

    # 5. Watchlist: positive setup, acceptable risk
    watchlist_residual_ok = (not watch_req_residual) or tiers.tier1_positive
    if (
        alpha >= watch_alpha
        and confidence >= watch_conf
        and watchlist_residual_ok
        and tiers.risk_penalty <= watch_max_rp
        and not tiers.tier4_blocking
    ):
        return "Watchlist", "Positive alpha + residual + acceptable risk — track."

    # 6. Risk-blocked but otherwise watch-quality → cap at Watchlist
    if tiers.tier4_blocking and alpha >= watch_alpha and watchlist_residual_ok:
        return "Watchlist", "Capped by risk flags — do not size up."

    return "Neutral", "No urgency."


# ---------------------------------------------------------------------------

def run(
    write: bool = True,
    factor_df: pd.DataFrame | None = None,
    narrative_df: pd.DataFrame | None = None,
    risk_df: pd.DataFrame | None = None,
    regime_df: pd.DataFrame | None = None,
    residual_df: pd.DataFrame | None = None,
    as_of: pd.Timestamp | None = None,
    ai_index_df: pd.DataFrame | None = None,
    capex_context: pd.DataFrame | None = None,
    price_panel: pd.DataFrame | None = None,
    monthly_revenue: pd.DataFrame | None = None,
    institutional_flow: pd.DataFrame | None = None,
    valuation: pd.DataFrame | None = None,
    market_panel: pd.DataFrame | None = None,
) -> pd.DataFrame:
    cfg = load_yaml("config/alpha_model_v2.yaml")
    tier_weights = cfg["scoring_v2"]["tier_weights"]
    caps = cfg["scoring_v2"]["caps"]
    confidence_cfg = cfg["confidence"]
    # A2-adopt: risk_penalty_multiplier from YAML (default 1.0 if absent
    # to keep existing behaviour for older configs).
    risk_mult = float(cfg.get("scoring_v2", {})
                         .get("risk", {})
                         .get("penalty_multiplier", 1.0))

    # Build any missing inputs (allows independent CLI invocation)
    if residual_df is None:
        residual_df = ra.run(write=False, ai_index_df=ai_index_df)
    if factor_df is None:
        factor_df = fm.run(
            write=False,
            residual_df=residual_df,
            ai_index_df=ai_index_df,
            as_of=as_of,
            price_panel=price_panel,
            monthly_revenue=monthly_revenue,
            institutional_flow=institutional_flow,
            valuation=valuation,
        )
    if narrative_df is None:
        narrative_df = ns_mod.run(write=False, capex_context=capex_context, as_of=as_of)
    if risk_df is None:
        risk_df = rm.run(
            write=False,
            residual_df=residual_df,
            as_of=as_of,
            price_panel=price_panel,
            monthly_revenue=monthly_revenue,
            valuation=valuation,
        )
    if regime_df is None:
        regime_df = rf.run(
            write=False,
            ai_index_df=ai_index_df,
            as_of=as_of,
            market_panel=market_panel,
        )

    universe = load_universe()
    universe = universe[universe["ticker"] != "2330.TW"].set_index("ticker")

    pivot = _factor_pivot(factor_df)
    if pivot.empty:
        return pd.DataFrame()

    residual_alpha_score = _residual_alpha_score(pivot)
    revenue_score = _revenue_confirmation_score(pivot)
    sector_score = _sector_relative_score(pivot)
    flow_score = _institutional_flow_score(pivot)
    theme_score = _theme_strength_score(pivot)
    val_penalty = _valuation_penalty(pivot)

    narr_idx = narrative_df.set_index("ticker") if not narrative_df.empty else pd.DataFrame()

    rows: list[dict] = []
    snap = ra.latest_snapshot(residual_df, as_of=as_of)
    snap_idx = snap.set_index("ticker") if not snap.empty else pd.DataFrame()

    regime_row = regime_df.iloc[0] if not regime_df.empty else None
    regime_penalty = 0.0
    if regime_row is not None:
        regime_label = regime_row["notes"].split(";")[0].replace("regime=", "").strip()
        regime_penalty = float(confidence_cfg.get("regime_penalty", {}).get(regime_label, 0.0))

    for ticker in pivot["ticker"]:
        if ticker not in universe.index:
            continue
        u = universe.loc[ticker]

        ra_score = float(residual_alpha_score.get(ticker, 0.0))
        rev_score = float(revenue_score.get(ticker, 0.0))
        sec_score = float(sector_score.get(ticker, 0.0))
        flw_score = float(flow_score.get(ticker, 0.0))
        thm_score = float(theme_score.get(ticker, 0.0))
        v_pen = float(val_penalty.get(ticker, 0.0))

        if not narr_idx.empty and ticker in narr_idx.index:
            narrative_score = float(narr_idx.loc[ticker, "narrative_score"])
            narrative_confidence = float(narr_idx.loc[ticker, "narrative_confidence"])
            positive_drivers = str(narr_idx.loc[ticker, "positive_drivers"])
            negative_drivers = str(narr_idx.loc[ticker, "negative_drivers"])
        else:
            narrative_score = 0.0
            narrative_confidence = 0.0
            positive_drivers = ""
            negative_drivers = ""

        # Cap narrative contribution
        narrative_capped = float(np.clip(narrative_score, -2.0, 2.0))
        # CAPEX context already capped; pull from theme_strength as proxy for any
        # contextual lift (we keep capex_context_score itself at zero unless an
        # explicit override is supplied later).
        capex_ctx_score = 0.0

        # Tier-1 score: residual_alpha (already positive-leaning aggregate)
        # Multiply by 5 to bring into the same magnitude as a 0-5 score.
        # Z-scores in pivot are clipped to ±3; the *_contrib values therefore
        # land in roughly [-1, +1]. We rescale here so that a typical strong
        # name lands around alpha_score ≈ 4.
        SCALE = 5.0
        tier1 = ra_score * SCALE * tier_weights["residual_alpha_score"] / 0.35
        tier2_rev = rev_score * SCALE * tier_weights["revenue_confirmation_score"] / 0.20
        tier2_flw = flw_score * SCALE * tier_weights["institutional_flow_score"] / 0.15
        tier_sec = sec_score * SCALE * tier_weights["sector_relative_score"] / 0.15
        tier_narr = narrative_capped * tier_weights["narrative_score"]
        tier_capex = capex_ctx_score * tier_weights["capex_context_score"]

        risk_penalty = abs(v_pen) * SCALE  # negative-weight contrib; magnify a bit
        ticker_flag_rows = risk_df[risk_df["ticker"] == ticker] if not risk_df.empty else pd.DataFrame()
        risk_severity = rm.severity_score(ticker_flag_rows)
        risk_penalty += 0.3 * risk_severity
        risk_penalty *= risk_mult   # A2-adopt YAML knob (default 1.0)
        # Gate-repair: extract specific flag presence for the new gate logic
        if not ticker_flag_rows.empty:
            ticker_flag_set = set(ticker_flag_rows["risk_flag"].astype(str).tolist())
        else:
            ticker_flag_set = set()
        has_overbought = "overbought" in ticker_flag_set
        has_valuation_extreme = "valuation_extreme" in ticker_flag_set

        alpha_score = (
            tier1
            + tier2_rev
            + tier_sec
            + tier2_flw
            + tier_narr
            + tier_capex
            - risk_penalty
        )

        # Confidence
        data_quality = 0.0
        snap_row = snap_idx.loc[ticker] if ticker in snap_idx.index else None
        if snap_row is not None and pd.notna(snap_row.get("beta_market")):
            data_quality += 1.5
        if snap_row is not None and pd.notna(snap_row.get("residual_momentum_60d")):
            data_quality += 1.0
        signal_agreement = 0.0
        if tier1 > 0 and tier2_rev > 0:
            signal_agreement += 1.0
        if tier1 > 0 and tier_narr > 0:
            signal_agreement += 0.5
        confidence_score = (
            data_quality
            + signal_agreement
            + min(narrative_confidence, 2.0) * 0.5
            - regime_penalty
        )
        confidence_score = float(max(0.0, confidence_score))

        residual_mom_20d = float(snap_row["residual_momentum_20d"]) if (
            snap_row is not None and pd.notna(snap_row.get("residual_momentum_20d"))
        ) else 0.0

        tiers = TierScores(
            tier1_residual_alpha=tier1,
            tier2_revenue_confirmation=tier2_rev,
            tier2_institutional_flow=tier2_flw,
            tier3_narrative=tier_narr,
            tier3_capex_context=tier_capex,
            tier4_risk_severity=risk_severity,
            risk_penalty=risk_penalty,
            overbought_flag=has_overbought,
            valuation_extreme_flag=has_valuation_extreme,
            residual_momentum_20d=residual_mom_20d,
        )

        zone, action = _resolve_decision_zone(tiers, alpha_score, confidence_score, cfg)

        # Aggregate flags
        risk_flag_str = ""
        if not risk_df.empty:
            sub = risk_df[risk_df["ticker"] == ticker]
            if not sub.empty:
                risk_flag_str = "; ".join(
                    f"{r['risk_flag']}({r['severity']})" for _, r in sub.iterrows()
                )

        main_pos = positive_drivers
        main_neg = negative_drivers
        if tier1 > 0:
            main_pos = (main_pos + "; " if main_pos else "") + f"residual alpha +{tier1:.2f}"
        if tier2_rev > 0:
            main_pos = (main_pos + "; " if main_pos else "") + f"revenue accel +{tier2_rev:.2f}"
        if v_pen < 0:
            main_neg = (main_neg + "; " if main_neg else "") + f"valuation penalty {v_pen:.2f}"

        rows.append(
            {
                "date": pd.Timestamp(snap["date"].max()) if not snap.empty else pd.Timestamp.today().normalize(),
                "ticker": ticker,
                "company_name": u["company_name"],
                "theme": u["theme"],
                "alpha_score": round(alpha_score, 3),
                "confidence_score": round(confidence_score, 3),
                "decision_zone": zone,
                "suggested_action": action,
                "residual_alpha_score": round(tier1, 3),
                "revenue_confirmation_score": round(tier2_rev, 3),
                "sector_relative_score": round(tier_sec, 3),
                "institutional_flow_score": round(tier2_flw, 3),
                "narrative_score": round(tier_narr, 3),
                "capex_context_score": round(tier_capex, 3),
                "risk_penalty": round(risk_penalty, 3),
                "risk_severity": risk_severity,
                "main_positive_drivers": main_pos,
                "main_negative_drivers": main_neg,
                "risk_flags": risk_flag_str,
                "data_quality": round(data_quality, 2),
                "notes": "",
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values("alpha_score", ascending=False).reset_index(drop=True)
    out.insert(0, "rank", out.index + 1)

    if write:
        ensure_dir("data/output")
        path = resolve_path("data/output/alpha_ranking.csv")
        out.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(out))

        # Signal breakdown — one row per (ticker, factor) for diagnostics
        breakdown_cols = [
            "rank", "ticker", "company_name", "theme",
            "residual_alpha_score", "revenue_confirmation_score",
            "sector_relative_score", "institutional_flow_score",
            "narrative_score", "capex_context_score", "risk_penalty",
        ]
        out[breakdown_cols].to_csv(resolve_path("data/output/signal_breakdown.csv"), index=False)

    return out
