"""Tests for dashboard.services.paper_portfolio_service.

We verify three guarantees the dashboard depends on:
1. ``generate_preview()`` is pure — it never writes to the filesystem.
2. Duplicate-date detection fires when the chosen date already exists in
   ``rebalance_log.csv``.
3. ``confirm_rebalance()`` runs the backup *before* invoking the wrapped
   CLI, captures stdout/stderr/returncode, and never reimplements scoring.

Subprocess + filesystem effects are injected via the ``runner`` and
``backup_fn`` parameters so no real shell command runs.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from capex_alpha import utils as cap_utils
from dashboard.services import data_loader as dl
from dashboard.services import paper_portfolio_service as svc


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """Redirect ``project_root`` to ``tmp_path`` and clear caches."""
    monkeypatch.setattr(cap_utils, "project_root", lambda: tmp_path)
    try:
        import streamlit as st
        st.cache_data.clear()
    except ImportError:
        pass
    (tmp_path / "data" / "output" / "paper_portfolio").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write_csv(root: Path, rel: str, df: pd.DataFrame) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)


def _toy_ranking(date: str = "2026-04-30") -> pd.DataFrame:
    return pd.DataFrame({
        "rank": [1, 2, 3, 4, 5, 6],
        "date": [date] * 6,
        "ticker": ["AAA.TW", "BBB.TW", "CCC.TW", "DDD.TW", "EEE.TW", "FFF.TW"],
        "company_name": ["A", "B", "C", "D", "E", "F"],
        "theme": ["thermal", "thermal", "memory_hbm", "optical", "passive", "thermal"],
        "alpha_score": [3.0, 2.5, 2.0, 1.5, 1.0, 0.5],
        "decision_zone": ["Strong"] * 6,
        "residual_alpha_score": [2.5, 2.2, 1.8, 1.0, 0.5, 0.2],
        "risk_penalty": [0.5, 0.3, 0.2, 0.5, 0.5, 0.3],
    })


# ---------------------------------------------------------------------------
# Preview is pure


def _seed_universe(root: Path) -> None:
    """Write a minimal beneficiary_universe.csv so get_theme_map() works."""
    universe = pd.DataFrame({
        "ticker": ["AAA.TW", "BBB.TW", "CCC.TW", "DDD.TW", "EEE.TW", "FFF.TW"],
        "company_name": ["A", "B", "C", "D", "E", "F"],
        "theme": ["thermal", "thermal", "memory_hbm", "optical", "passive", "thermal"],
    })
    cfg_dir = root / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "universe.yaml").write_text(
        "manual_files:\n  beneficiary_universe: data/manual/beneficiary_universe.csv\n",
        encoding="utf-8",
    )
    udir = root / "data" / "manual"
    udir.mkdir(parents=True, exist_ok=True)
    universe.to_csv(udir / "beneficiary_universe.csv", index=False)


def test_preview_does_not_write_anything(tmp_project, monkeypatch):
    """generate_preview must NEVER touch the filesystem (write side)."""
    _write_csv(tmp_project, "data/output/alpha_ranking.csv", _toy_ranking())
    _seed_universe(tmp_project)
    # No target_weights or rebalance_log on disk yet.
    # Bypass the streamlit-cached universe loader so we get a deterministic
    # theme map regardless of what other tests cached earlier.
    monkeypatch.setattr(svc, "get_theme_map", lambda: {
        "AAA.TW": "thermal", "BBB.TW": "thermal", "CCC.TW": "memory_hbm",
        "DDD.TW": "optical", "EEE.TW": "passive", "FFF.TW": "thermal",
    })

    # monkey-patch `open` and `Path.write_text` to detect any write attempts
    import builtins as _b
    real_open = _b.open

    def guarded_open(file, mode="r", *args, **kwargs):
        # allow read-only modes
        if any(c in mode for c in ("w", "a", "x", "+")):
            raise AssertionError(f"unexpected write open: {file!r} mode={mode!r}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(_b, "open", guarded_open)

    real_write_text = Path.write_text
    real_write_bytes = Path.write_bytes

    def guard_write_text(self, *a, **kw):
        raise AssertionError(f"unexpected Path.write_text on {self}")

    def guard_write_bytes(self, *a, **kw):
        raise AssertionError(f"unexpected Path.write_bytes on {self}")

    monkeypatch.setattr(Path, "write_text", guard_write_text)
    monkeypatch.setattr(Path, "write_bytes", guard_write_bytes)

    try:
        preview = svc.generate_preview(rebalance_date="2026-04-30", top_n=5, max_per_theme=2)
    finally:
        monkeypatch.setattr(Path, "write_text", real_write_text)
        monkeypatch.setattr(Path, "write_bytes", real_write_bytes)

    assert preview.has_ranking is True
    assert not preview.proposed.empty
    # max_per_theme=2 ⇒ thermal capped at 2; expect 5 unique tickers
    assert len(preview.proposed) == 5
    assert preview.duplicate_date is False


def test_preview_handles_missing_ranking(tmp_project):
    preview = svc.generate_preview(rebalance_date="2026-04-30")
    assert preview.has_ranking is False
    assert preview.proposed.empty
    assert any("alpha_ranking.csv" in w for w in preview.warnings)


def test_preview_detects_duplicate_date(tmp_project):
    _write_csv(tmp_project, "data/output/alpha_ranking.csv", _toy_ranking())
    log = pd.DataFrame({
        "rebalance_date": ["2026-04-30"],
        "n_holdings": [5], "gross_exposure": [1.0],
        "base_turnover": [0.5], "est_cost_25bps": [0.0], "est_cost_50bps": [0.0],
        "slippage_placeholder": [0.0], "period_return": [0.0],
        "period_return_25bps": [0.0], "period_return_50bps": [0.0],
        "benchmark_return": [0.0], "excess_vs_benchmark": [0.0],
        "nav_paper": [1.0], "nav_paper_25bps": [1.0], "nav_paper_50bps": [1.0],
        "nav_benchmark": [1.0], "drawdown_paper": [0.0], "notes": [""],
    })
    _write_csv(tmp_project, "data/output/paper_portfolio/rebalance_log.csv", log)
    preview = svc.generate_preview(rebalance_date="2026-04-30")
    assert preview.duplicate_date is True
    assert preview.duplicate_date_value == pd.Timestamp("2026-04-30")
    assert any("重複日期" in w for w in preview.warnings)


def test_preview_costs_are_finite(tmp_project):
    _write_csv(tmp_project, "data/output/alpha_ranking.csv", _toy_ranking())
    target = pd.DataFrame({
        "ticker": ["AAA.TW", "ZZZ.TW"],
        "company_name": ["A", "Z"],
        "theme": ["thermal", "other"],
        "target_weight": [0.5, 0.5],
        "alpha_score": [3.0, 0.0],
        "decision_zone": ["Strong", "Avoid"],
        "risk_flags": ["", ""],
        "notes": ["", ""],
    })
    _write_csv(tmp_project, "data/output/paper_portfolio/target_weights.csv", target)
    preview = svc.generate_preview(rebalance_date="2026-04-30")
    assert preview.est_cost_25bps >= 0.0
    assert preview.est_cost_50bps >= preview.est_cost_25bps
    assert preview.base_turnover > 0.0
    # Side-by-side should include both new and old tickers
    tickers_in_side = set(preview.side_by_side["ticker"])
    assert "AAA.TW" in tickers_in_side and "ZZZ.TW" in tickers_in_side


# ---------------------------------------------------------------------------
# Confirm wires backup + subprocess


def test_confirm_calls_backup_then_subprocess(tmp_project):
    calls: dict[str, list] = {"backup": [], "runner": []}

    def fake_backup():
        calls["backup"].append("called")
        return Path("/tmp/fake_backup_dir"), [Path("/tmp/fake_backup_dir/portfolio.csv")]

    def fake_runner(cmd, **kwargs):
        calls["runner"].append((tuple(cmd), kwargs))
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    result = svc.confirm_rebalance(
        rebalance_date="2026-04-30",
        notes="unit test",
        runner=fake_runner,
        backup_fn=fake_backup,
        python_executable="/usr/bin/python3",
    )
    assert calls["backup"] == ["called"]
    assert len(calls["runner"]) == 1
    cmd, kwargs = calls["runner"][0]
    assert cmd[0] == "/usr/bin/python3"
    assert "--rebalance" in cmd
    assert "--date" in cmd and "2026-04-30" in cmd
    assert "--notes" in cmd and "unit test" in cmd
    assert kwargs.get("capture_output") is True
    assert kwargs.get("text") is True
    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout == "ok\n"
    assert result.backup_dir == Path("/tmp/fake_backup_dir")


def test_confirm_subprocess_failure_does_not_raise(tmp_project):
    def fake_backup():
        return Path("/tmp/x"), []

    def fake_runner(cmd, **kwargs):
        return SimpleNamespace(returncode=2, stdout="", stderr="boom\n")

    result = svc.confirm_rebalance(
        rebalance_date="2026-04-30",
        runner=fake_runner,
        backup_fn=fake_backup,
    )
    assert result.ok is False
    assert result.returncode == 2
    assert "boom" in result.stderr


def test_confirm_handles_runner_oserror(tmp_project):
    def fake_backup():
        return Path("/tmp/x"), []

    def explode_runner(cmd, **kwargs):
        raise FileNotFoundError("no python")

    result = svc.confirm_rebalance(
        rebalance_date="2026-04-30",
        runner=explode_runner,
        backup_fn=fake_backup,
    )
    assert result.ok is False
    assert "FileNotFoundError" in result.stderr


# ---------------------------------------------------------------------------
# Backup service creates a timestamped folder


def test_backup_service_creates_folder_and_copies_present_files(tmp_project):
    from dashboard.services.backup_service import backup_paper_portfolio_files

    # Seed two of the four files
    (tmp_project / "data" / "output" / "paper_portfolio" / "portfolio.csv").write_text("a,b\n1,2\n")
    (tmp_project / "reports").mkdir(exist_ok=True)
    (tmp_project / "reports" / "paper_portfolio_report.md").write_text("# r\n")

    dest_dir, copied = backup_paper_portfolio_files()
    assert dest_dir.exists()
    copied_names = {p.name for p in copied}
    assert copied_names == {"portfolio.csv", "paper_portfolio_report.md"}
    # The two missing files should NOT have been created
    assert not (dest_dir / "rebalance_log.csv").exists()
    assert not (dest_dir / "target_weights.csv").exists()


def test_backup_service_handles_zero_present_files(tmp_project):
    """First-ever run: nothing on disk to back up — should succeed silently."""
    from dashboard.services.backup_service import backup_paper_portfolio_files

    dest_dir, copied = backup_paper_portfolio_files()
    assert dest_dir.exists()
    assert copied == []


# ---------------------------------------------------------------------------
# Sanity: build_rebalance_cmd uses sys.executable by default


def test_default_python_executable_is_sys_executable(tmp_project):
    cmd = svc._build_rebalance_cmd(pd.Timestamp("2026-04-30"), "n")
    assert cmd[0] == sys.executable
