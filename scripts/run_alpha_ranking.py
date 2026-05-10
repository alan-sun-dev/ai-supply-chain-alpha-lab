#!/usr/bin/env python
"""Run scoring_model_v2 + alpha_ranking only (assumes upstream artifacts on disk)."""
from __future__ import annotations

import sys

from capex_alpha.fusion import alpha_ranking as ar


def main() -> int:
    out = ar.run(write=True)
    print(out["alpha_ranking"].head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
