"""Tests for the institutional-flow pivot used by fetch_institutional_flow."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def fetch_module():
    """Import the script as a module without running ``main()``."""
    path = Path(__file__).resolve().parents[1] / "scripts" / "fetch_institutional_flow.py"
    spec = importlib.util.spec_from_file_location("fetch_institutional_flow", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def raw_finmind() -> pd.DataFrame:
    """Long-form payload that mimics what FinMind returns."""
    return pd.DataFrame(
        [
            {"date": "2025-01-02", "stock_id": "2404", "name": "Foreign_Investor",
             "buy": 1000000, "sell":  600000},
            {"date": "2025-01-02", "stock_id": "2404", "name": "Investment_Trust",
             "buy":  100000, "sell":  150000},
            {"date": "2025-01-02", "stock_id": "2404", "name": "Dealer_self",
             "buy":   50000, "sell":   30000},
            {"date": "2025-01-03", "stock_id": "2404", "name": "Foreign_Investor",
             "buy":  500000, "sell":  900000},
        ]
    )


def test_pivot_to_wide_aggregates_buckets(fetch_module, raw_finmind: pd.DataFrame) -> None:
    wide = fetch_module._pivot_to_wide(raw_finmind, "2404.TW")
    assert set(wide.columns) == {
        "ticker", "date",
        "foreign_buy", "foreign_sell", "foreign_net",
        "trust_net", "dealer_net", "total_net",
    }
    assert len(wide) == 2

    # 2025-01-02 row checks
    row = wide[wide["date"] == "2025-01-02"].iloc[0]
    assert row["foreign_net"] == 1_000_000 - 600_000      # 400 000
    assert row["trust_net"] == 100_000 - 150_000          # -50 000
    assert row["dealer_net"] == 50_000 - 30_000           # 20 000
    assert row["total_net"] == 400_000 - 50_000 + 20_000  # 370 000

    # 2025-01-03 → only foreign present, others must be 0
    row2 = wide[wide["date"] == "2025-01-03"].iloc[0]
    assert row2["foreign_net"] == 500_000 - 900_000
    assert row2["trust_net"] == 0
    assert row2["dealer_net"] == 0


def test_pivot_to_wide_handles_empty(fetch_module) -> None:
    out = fetch_module._pivot_to_wide(pd.DataFrame(), "2404.TW")
    assert out.empty
    assert "foreign_net" in out.columns


def test_bare_ticker(fetch_module) -> None:
    assert fetch_module._bare_ticker("2404.TW") == "2404"
    assert fetch_module._bare_ticker("3131.TWO") == "3131"
    assert fetch_module._bare_ticker(" 6196.TW ") == "6196"
