"""Two-step paper-portfolio rebalance flow used by the dashboard.

Step 1 — preview (pure):
    ``generate_preview()`` reads the latest ``alpha_ranking.csv`` and the
    current ``target_weights.csv``, then derives the proposed new top-N
    via the existing pure helpers in ``capex_alpha.paper_portfolio``.
    No filesystem writes. Returns a ``RebalancePreview`` dataclass with
    side-by-side weights + estimated costs + duplicate-date warning.

Step 2 — confirm (writes):
    ``confirm_rebalance()`` first backs up the four paper-portfolio files
    via ``backup_service``, then shells out to
    ``scripts/run_paper_portfolio.py --rebalance --date ... --notes ...``
    using ``sys.executable`` so the active venv is used. Stdout/stderr and
    return code are captured and returned in a ``ConfirmResult`` so the
    UI can surface them. Scoring logic is **never** reimplemented here.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from capex_alpha import paper_portfolio as pp
from capex_alpha.utils import resolve_path

from .backup_service import backup_paper_portfolio_files
from .data_loader import (
    get_theme_map,
    load_alpha_ranking,
    load_rebalance_log,
    load_target_weights,
)


REBALANCE_SCRIPT = "scripts/run_paper_portfolio.py"
CONFIRM_CHECKBOX_LABEL = (
    "我了解此為紙上組合再平衡，不會送出任何實單；現有檔案將先備份。"
)


# ---------------------------------------------------------------------------
# Preview


@dataclass
class RebalancePreview:
    rebalance_date: pd.Timestamp
    proposed: pd.DataFrame                  # columns from compute_target_holdings
    current: pd.DataFrame                   # current target_weights (may be empty)
    side_by_side: pd.DataFrame              # ticker, prev_weight, target_weight, weight_change
    est_cost_25bps: float
    est_cost_50bps: float
    base_turnover: float
    duplicate_date: bool
    duplicate_date_value: pd.Timestamp | None
    warnings: list[str] = field(default_factory=list)
    has_ranking: bool = True


def _to_weight_dict(df: pd.DataFrame | None) -> dict[str, float]:
    if df is None or df.empty or "ticker" not in df.columns or "target_weight" not in df.columns:
        return {}
    return {str(t): float(w) for t, w in zip(df["ticker"], df["target_weight"])}


def _build_side_by_side(
    proposed: pd.DataFrame, current: pd.DataFrame | None
) -> pd.DataFrame:
    new_w = _to_weight_dict(proposed)
    old_w = _to_weight_dict(current)
    tickers = sorted(set(new_w) | set(old_w))
    rows = []
    name_lookup: dict[str, str] = {}
    theme_lookup: dict[str, str] = {}
    for src in (proposed, current):
        if src is None or src.empty:
            continue
        if "company_name" in src.columns:
            for t, n in zip(src["ticker"], src["company_name"]):
                name_lookup.setdefault(str(t), str(n))
        if "theme" in src.columns:
            for t, th in zip(src["ticker"], src["theme"]):
                theme_lookup.setdefault(str(t), str(th))
    for t in tickers:
        prev_w = old_w.get(t, 0.0)
        tgt_w = new_w.get(t, 0.0)
        rows.append({
            "ticker": t,
            "company_name": name_lookup.get(t, ""),
            "theme": theme_lookup.get(t, ""),
            "prev_weight": prev_w,
            "target_weight": tgt_w,
            "weight_change": tgt_w - prev_w,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("target_weight", ascending=False).reset_index(drop=True)
    return out


def generate_preview(
    rebalance_date: pd.Timestamp | str | None = None,
    top_n: int = 5,
    max_per_theme: int = 2,
) -> RebalancePreview:
    """Pure preview: never touches the filesystem (only reads).

    Reads the same inputs the CLI does (alpha_ranking.csv +
    target_weights.csv + rebalance_log.csv) and returns the proposed
    top-N portfolio plus costs and a duplicate-date warning.
    """
    if rebalance_date is None:
        date = pd.Timestamp.today().normalize()
    else:
        date = pd.Timestamp(rebalance_date).normalize()

    ranking = load_alpha_ranking()
    current = load_target_weights()
    log = load_rebalance_log()

    warnings: list[str] = []

    if ranking is None or ranking.empty:
        warnings.append(
            "找不到 alpha_ranking.csv 或內容為空 — 請先執行 "
            "scripts/run_daily_pipeline.py。"
        )
        return RebalancePreview(
            rebalance_date=date,
            proposed=pd.DataFrame(),
            current=current if current is not None else pd.DataFrame(),
            side_by_side=pd.DataFrame(),
            est_cost_25bps=0.0,
            est_cost_50bps=0.0,
            base_turnover=0.0,
            duplicate_date=False,
            duplicate_date_value=None,
            warnings=warnings,
            has_ranking=False,
        )

    theme_map = get_theme_map()
    proposed = pp.compute_target_holdings(
        ranking=ranking,
        theme_map=theme_map,
        top_n=top_n,
        max_per_theme=max_per_theme,
    )

    new_w = _to_weight_dict(proposed)
    old_w = _to_weight_dict(current)
    base_turnover = sum(
        abs(new_w.get(t, 0.0) - old_w.get(t, 0.0))
        for t in set(new_w) | set(old_w)
    )
    est_25 = pp.estimate_one_way_cost(new_w, old_w, 25.0)
    est_50 = pp.estimate_one_way_cost(new_w, old_w, 50.0)

    duplicate_date = False
    duplicate_date_value: pd.Timestamp | None = None
    if log is not None and not log.empty:
        existing_dates = pd.to_datetime(log["rebalance_date"]).dt.normalize()
        if (existing_dates == date).any():
            duplicate_date = True
            duplicate_date_value = date
            warnings.append(
                f"{date.date()} 已存在於 rebalance_log.csv（重複日期）。"
                "重新執行將覆寫該筆。"
            )

    side = _build_side_by_side(proposed, current)

    return RebalancePreview(
        rebalance_date=date,
        proposed=proposed,
        current=current if current is not None else pd.DataFrame(),
        side_by_side=side,
        est_cost_25bps=float(est_25),
        est_cost_50bps=float(est_50),
        base_turnover=float(base_turnover),
        duplicate_date=duplicate_date,
        duplicate_date_value=duplicate_date_value,
        warnings=warnings,
        has_ranking=True,
    )


# ---------------------------------------------------------------------------
# Confirm (writes via subprocess wrapper)


@dataclass
class ConfirmResult:
    ok: bool
    backup_dir: Path | None
    backup_files: list[Path]
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str


def _build_rebalance_cmd(
    rebalance_date: pd.Timestamp,
    notes: str,
    script_path: str = REBALANCE_SCRIPT,
    python_executable: str | None = None,
) -> list[str]:
    py = python_executable or sys.executable
    return [
        py,
        str(resolve_path(script_path)),
        "--rebalance",
        "--date",
        rebalance_date.strftime("%Y-%m-%d"),
        "--notes",
        notes or "",
    ]


def _build_report_cmd(
    script_path: str = REBALANCE_SCRIPT,
    python_executable: str | None = None,
) -> list[str]:
    py = python_executable or sys.executable
    return [py, str(resolve_path(script_path)), "--report"]


def confirm_rebalance(
    rebalance_date: pd.Timestamp | str,
    notes: str = "",
    *,
    runner=subprocess.run,
    backup_fn=backup_paper_portfolio_files,
    python_executable: str | None = None,
    timeout: float | None = 600,
) -> ConfirmResult:
    """Backup the 4 files, then shell out to the existing CLI.

    ``runner`` and ``backup_fn`` are injectable for tests so the real
    subprocess + filesystem are not touched.
    """
    date = pd.Timestamp(rebalance_date).normalize()
    backup_dir, backup_files = backup_fn()
    cmd = _build_rebalance_cmd(date, notes, python_executable=python_executable)
    try:
        proc = runner(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return ConfirmResult(
            ok=False,
            backup_dir=backup_dir,
            backup_files=backup_files,
            cmd=cmd,
            returncode=-1,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
        )
    return ConfirmResult(
        ok=(proc.returncode == 0),
        backup_dir=backup_dir,
        backup_files=backup_files,
        cmd=cmd,
        returncode=int(proc.returncode),
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def rerender_report(
    *,
    runner=subprocess.run,
    python_executable: str | None = None,
    timeout: float | None = 120,
) -> ConfirmResult:
    """Re-render the markdown report from current state — no backup needed."""
    cmd = _build_report_cmd(python_executable=python_executable)
    try:
        proc = runner(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return ConfirmResult(
            ok=False,
            backup_dir=None,
            backup_files=[],
            cmd=cmd,
            returncode=-1,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
        )
    return ConfirmResult(
        ok=(proc.returncode == 0),
        backup_dir=None,
        backup_files=[],
        cmd=cmd,
        returncode=int(proc.returncode),
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )
