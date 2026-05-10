#!/usr/bin/env python
"""Run the regime filter."""
from __future__ import annotations

import sys

from capex_alpha.quant import regime_filter as rf


def main() -> int:
    df = rf.run(write=True)
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
