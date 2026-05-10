#!/usr/bin/env python
"""Build residual alpha CSV."""
from __future__ import annotations

import sys

from capex_alpha.quant import residual_alpha as ra


def main() -> int:
    df = ra.run(write=True)
    print(f"residual_alpha rows: {len(df)}")
    if not df.empty:
        snap = ra.latest_snapshot(df)
        cols = [
            "ticker", "company_name", "theme",
            "beta_market", "beta_ai",
            "residual_momentum_60d", "residual_drawdown_60d",
            "alpha_quality_score",
        ]
        print(snap[cols].sort_values("alpha_quality_score", ascending=False).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
