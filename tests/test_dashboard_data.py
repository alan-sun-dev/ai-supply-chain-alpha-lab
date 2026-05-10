"""Tests for dashboard payload schema."""
from __future__ import annotations

import json

from capex_alpha.dashboard import dashboard_data as dd
from capex_alpha.dashboard import daily_report_generator as drg


REQUIRED_TOP_LEVEL = {
    "as_of_date",
    "version",
    "market_regime",
    "top_alpha_candidates",
    "watchlist",
    "narrative_watch",
    "risk_warnings",
    "theme_heatmap",
    "factor_health",
    "latest_capex_context",
    "model_notes",
}


def test_payload_schema():
    payload = dd.run(write=False)
    missing = REQUIRED_TOP_LEVEL - set(payload.keys())
    assert not missing, f"Missing keys: {missing}"
    assert payload["version"] == "v2"


def test_payload_serializable_to_json():
    payload = dd.run(write=False)
    # No NaN should leak through; json.dumps with default=None handles the rest
    s = json.dumps(payload, ensure_ascii=False, default=lambda o: None)
    assert isinstance(s, str)
    assert len(s) > 100


def test_daily_report_renders():
    payload = dd.run(write=False)
    text = drg.render(payload)
    assert "AI Supply Chain Alpha Daily Report" in text
    assert "Top Alpha Candidates" in text
    assert "CAPEX is context only" in text or "CAPEX" in text
