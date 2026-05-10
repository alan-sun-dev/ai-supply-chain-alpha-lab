"""Markdown 報告檢視 — reports/paper_portfolio_report.md。"""
from __future__ import annotations

import streamlit as st

from dashboard.services.data_loader import clear_all_caches, load_paper_report_md
from dashboard.services.paper_portfolio_service import rerender_report


def render() -> None:
    st.header("紙上組合報告")

    cols = st.columns([1, 1, 4])
    if cols[0].button("重新產生報告", use_container_width=True):
        with st.spinner("正在重新產生 …"):
            r = rerender_report()
        if r.ok:
            st.success(f"報告已重產（returncode {r.returncode}）。")
        else:
            st.error(f"重產失敗（returncode {r.returncode}）。")
        if r.stderr:
            with st.expander("stderr"):
                st.code(r.stderr)
        clear_all_caches()

    md = load_paper_report_md()
    if md is None:
        st.info(
            "找不到 reports/paper_portfolio_report.md。"
            "請執行 `.venv/bin/python scripts/run_paper_portfolio.py --report` "
            "或先 backfill。"
        )
        return

    st.markdown(md)
