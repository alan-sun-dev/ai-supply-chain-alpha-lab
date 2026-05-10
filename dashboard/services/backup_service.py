"""Backup the four paper-portfolio artefacts before any confirm-rebalance.

Files copied (when present):
- ``data/output/paper_portfolio/portfolio.csv``
- ``data/output/paper_portfolio/target_weights.csv``
- ``data/output/paper_portfolio/rebalance_log.csv``
- ``reports/paper_portfolio_report.md``

Backup destination:
``archive/dashboard_rebalance_backup/<YYYYMMDD_HHMMSS>/``

Returns the destination directory so the UI can surface it. Missing source
files are silently skipped — no source file is *required* to be present;
the backup is best-effort.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from capex_alpha.utils import ensure_dir, resolve_path

BACKUP_ROOT = "archive/dashboard_rebalance_backup"

PAPER_FILES: tuple[str, ...] = (
    "data/output/paper_portfolio/portfolio.csv",
    "data/output/paper_portfolio/target_weights.csv",
    "data/output/paper_portfolio/rebalance_log.csv",
    "reports/paper_portfolio_report.md",
)


def _timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d_%H%M%S")


def backup_paper_portfolio_files(
    now: datetime | None = None,
    files: tuple[str, ...] = PAPER_FILES,
    backup_root: str = BACKUP_ROOT,
) -> tuple[Path, list[Path]]:
    """Copy each file (when present) into a timestamped backup folder.

    Returns ``(destination_dir, copied_paths)``. ``copied_paths`` lists the
    *destination* paths actually written; an empty list means nothing was
    backed up because no source file existed yet (e.g. first-ever run).
    """
    dest_dir = resolve_path(backup_root) / _timestamp(now)
    ensure_dir(dest_dir)

    copied: list[Path] = []
    for rel in files:
        src = resolve_path(rel)
        if not src.exists():
            continue
        dst = dest_dir / src.name
        shutil.copy2(src, dst)
        copied.append(dst)
    return dest_dir, copied
