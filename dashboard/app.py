"""Streamlit 進入點 — 側邊導覽 + 8 個頁面。

啟動方式：
    .venv/bin/streamlit run dashboard/app.py

純讀取的研究儀表板，疊加兩段式紙上組合再平衡流程。
不會送任何實單；不會重新實作 scoring；確認再平衡會呼叫
``scripts/run_paper_portfolio.py`` 子行程。
"""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent
for p in (_ROOT, _ROOT / "src"):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

import streamlit as st  # noqa: E402

from dashboard.components import (  # noqa: E402
    overview,
    performance,
    portfolio,
    ranking,
    rebalance,
    report,
    risk,
    theme,
)
from dashboard.services.data_loader import load_dashboard_data  # noqa: E402

PAGES = {
    "總覽": overview.render,
    "Alpha 排名": ranking.render,
    "當前組合": portfolio.render,
    "再平衡": rebalance.render,
    "績效": performance.render,
    "風險旗標": risk.render,
    "題材曝險": theme.render,
    "報告檢視": report.render,
}


def main() -> None:
    st.set_page_config(
        page_title="AI 供應鏈 Alpha 研究台",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    with st.sidebar:
        st.title("AI 供應鏈 Alpha")
        st.caption("研究儀表板 — 紙上組合，無實單交易。")

        dash = load_dashboard_data()
        as_of = (dash or {}).get("as_of_date", "—")
        st.markdown(f"**資料日期**　`{as_of}`")
        st.divider()

        page = st.radio("頁面", list(PAGES.keys()), key="dashboard_page")

        st.divider()
        if st.button("清除資料快取", use_container_width=True):
            st.cache_data.clear()
            st.success("快取已清除。")
        st.caption(
            "提示：執行 `scripts/run_daily_pipeline.py` 後，"
            "若資料未更新可按上方按鈕清除 30 秒快取。"
        )

    PAGES[page]()


if __name__ == "__main__":
    main()
