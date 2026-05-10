#!/usr/bin/env python
"""Build the AI supply chain theme indices."""
from __future__ import annotations

import sys

from capex_alpha.quant import ai_factor_index as afi


def main() -> int:
    df = afi.run(write=True)
    print(f"AI factor index rows: {len(df)}")
    if not df.empty:
        latest = df.sort_values("date").groupby("theme").tail(1)
        cols = ["date", "theme", "theme_nav", "theme_momentum_20d", "theme_momentum_60d", "theme_drawdown", "num_constituents"]
        print(latest[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
