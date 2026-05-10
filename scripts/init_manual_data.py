"""Initialise / verify manual data scaffolding.

Re-runs are safe — it never overwrites an existing file. Creates a stub
``monthly_revenue.csv`` if missing and reports row counts for the others.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `python scripts/init_manual_data.py` from project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capex_alpha.data_loader import load_capex_events, load_universe  # noqa: E402
from capex_alpha.revenue_tracker import write_revenue_template_if_missing  # noqa: E402
from capex_alpha.utils import ensure_dir, get_logger, resolve_path  # noqa: E402

logger = get_logger("init_manual_data")


def main() -> int:
    for d in [
        "data/raw",
        "data/processed",
        "data/output",
        "data/output/charts",
        "data/manual",
        "reports",
    ]:
        ensure_dir(d)

    # Universe + events should already exist (committed to repo); warn if missing.
    for label, rel in [
        ("universe", "data/manual/beneficiary_universe.csv"),
        ("capex_events", "data/manual/tsmc_capex_events.csv"),
    ]:
        path = resolve_path(rel)
        if path.exists():
            logger.info("OK %s present at %s", label, path)
        else:
            logger.error("MISSING %s — expected at %s", label, path)

    try:
        u = load_universe()
        logger.info("Universe loaded: %s rows, %s themes", len(u), u["theme"].nunique())
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not load universe: %s", exc)
        return 1

    try:
        ev = load_capex_events()
        logger.info("CAPEX events loaded: %s rows, range %s → %s",
                    len(ev),
                    ev["event_date"].min().date() if not ev.empty else "?",
                    ev["event_date"].max().date() if not ev.empty else "?")
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not load CAPEX events: %s", exc)
        return 1

    created = write_revenue_template_if_missing()
    if created:
        logger.info("Created revenue template: %s", created)
    else:
        logger.info("Revenue CSV already present.")

    logger.info("Init complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
