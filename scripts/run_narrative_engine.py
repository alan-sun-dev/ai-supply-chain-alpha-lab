#!/usr/bin/env python
"""Run news_parser → capex_interpreter → narrative_scorer."""
from __future__ import annotations

import sys

from capex_alpha.narrative import capex_interpreter as ci
from capex_alpha.narrative import narrative_scorer as ns
from capex_alpha.narrative import news_parser as np_mod


def main() -> int:
    news = np_mod.run(write=True)
    capex = ci.run(write=True)
    out = ns.run(write=True, news_signals=news, capex_context=capex)
    print(f"narrative rows: {len(out)}")
    cols = ["ticker", "theme", "narrative_score", "narrative_confidence", "narrative_summary"]
    print(out.sort_values("narrative_score", ascending=False).head(15)[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
