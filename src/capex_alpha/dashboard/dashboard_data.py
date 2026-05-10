"""Build the dashboard JSON payload — the single artifact every UI surface
(Streamlit, Grafana, OpenClaw, plain HTML) consumes.
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from ..fusion import alpha_ranking as ar
from ..fusion import scoring_model_v2 as sm
from ..narrative import capex_interpreter as ci
from ..quant import ai_factor_index as afi
from ..quant import regime_filter as rf
from ..utils import ensure_dir, get_logger, load_yaml, resolve_path

logger = get_logger(__name__)


def _to_jsonable(obj):
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if np.isnan(v) else v
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and np.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


def _records(df: pd.DataFrame, n: int | None = None) -> list[dict]:
    if df.empty:
        return []
    sub = df.head(n) if n is not None else df
    return [_to_jsonable(r) for r in sub.to_dict(orient="records")]


def build_payload(
    ranking: pd.DataFrame,
    regime: pd.DataFrame,
    ai_index: pd.DataFrame,
    capex_context: pd.DataFrame,
    cfg: dict,
) -> dict:
    display = cfg["display"]

    if not ranking.empty:
        ranking = ranking.copy()
        ranking["date"] = pd.to_datetime(ranking["date"])
        as_of = ranking["date"].max()
    else:
        as_of = pd.Timestamp.today().normalize()

    # Theme heatmap from the AI factor index
    theme_heatmap = []
    if not ai_index.empty:
        latest_per_theme = (
            ai_index.sort_values("date").groupby("theme").tail(1)
        )
        for _, row in latest_per_theme.iterrows():
            if row["theme"] not in display["theme_heatmap_themes"]:
                continue
            theme_heatmap.append(
                {
                    "theme": row["theme"],
                    "momentum_20d": _to_jsonable(row.get("theme_momentum_20d")),
                    "momentum_60d": _to_jsonable(row.get("theme_momentum_60d")),
                    "drawdown": _to_jsonable(row.get("theme_drawdown")),
                    "num_constituents": _to_jsonable(row.get("num_constituents")),
                }
            )

    # Latest CAPEX context summary (most recent event row)
    latest_capex = {}
    if not capex_context.empty:
        cc = capex_context.sort_values("event_date").tail(1).iloc[0]
        latest_capex = {
            "event_date": _to_jsonable(cc["event_date"]),
            "context_type": str(cc["context_type"]),
            "affected_themes": str(cc["affected_themes"]),
            "context_score": _to_jsonable(cc["context_score"]),
            "notes": str(cc.get("notes", "")),
        }

    # Factor health: how many tickers have non-null factors
    factor_health = {}
    if not ranking.empty:
        for col in [
            "residual_alpha_score",
            "revenue_confirmation_score",
            "sector_relative_score",
            "institutional_flow_score",
            "narrative_score",
        ]:
            if col in ranking.columns:
                factor_health[col] = {
                    "non_null_pct": float((ranking[col].fillna(0) != 0).mean()),
                    "mean": _to_jsonable(ranking[col].mean()),
                    "max": _to_jsonable(ranking[col].max()),
                }

    market_regime = {}
    if not regime.empty:
        r = regime.iloc[0]
        market_regime = {
            "date": _to_jsonable(r["date"]),
            "market_regime": str(r["market_regime"]),
            "ai_regime": str(r["ai_regime"]),
            "risk_level": str(r["risk_level"]),
            "recommended_gross_exposure": _to_jsonable(r["recommended_gross_exposure"]),
            "recommended_top_n": _to_jsonable(r["recommended_top_n"]),
            "notes": str(r.get("notes", "")),
        }

    payload = {
        "as_of_date": as_of.strftime("%Y-%m-%d"),
        "version": "v2",
        "market_regime": market_regime,
        "top_alpha_candidates": _records(
            ar.top_alpha_candidates(ranking, n=display["top_alpha_n"])
        ),
        "watchlist": _records(
            ranking[ranking["decision_zone"] == "Watchlist"], n=display["watchlist_n"]
        ),
        "narrative_watch": _records(
            ar.top_narrative_watch(ranking, n=display["narrative_watch_n"])
        ),
        "risk_warnings": _records(
            ranking[ranking["risk_penalty"] > 0].sort_values("risk_penalty", ascending=False),
            n=display["risk_warning_n"],
        ),
        "theme_heatmap": theme_heatmap,
        "factor_health": factor_health,
        "latest_capex_context": latest_capex,
        "model_notes": [
            "CAPEX is context only — never a trigger.",
            "Strong Candidate is research priority, not buy recommendation.",
            "Residual alpha is core; raw price momentum is excluded.",
        ],
    }
    return payload


def run(
    write: bool = True,
    ranking: pd.DataFrame | None = None,
    regime: pd.DataFrame | None = None,
    ai_index: pd.DataFrame | None = None,
    capex_context: pd.DataFrame | None = None,
) -> dict:
    cfg = load_yaml("config/dashboard_config.yaml")

    if ranking is None:
        ranking = sm.run(write=False)
    if regime is None:
        regime = rf.run(write=False)
    if ai_index is None:
        ai_index = afi.run(write=False)
    if capex_context is None:
        capex_context = ci.run(write=False)

    payload = build_payload(ranking, regime, ai_index, capex_context, cfg)

    if write:
        ensure_dir("data/output")
        path = resolve_path(cfg["output"]["json_path"])
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=_to_jsonable)
        logger.info("Wrote %s", path)

    return payload
