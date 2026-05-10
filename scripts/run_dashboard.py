#!/usr/bin/env python
"""Build the dashboard JSON + daily report from the latest ranking."""
from __future__ import annotations

import sys

from capex_alpha.dashboard import daily_report_generator as drg
from capex_alpha.dashboard import dashboard_data as dd


def main() -> int:
    payload = dd.run(write=True)
    drg.run(write=True, payload=payload)
    print("dashboard_data.json + daily_alpha_report.md written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
