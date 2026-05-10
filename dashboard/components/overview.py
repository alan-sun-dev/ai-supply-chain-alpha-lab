"""總覽頁 — KPI 卡 + 市場/AI regime 摘要。"""
from __future__ import annotations

import streamlit as st

from dashboard.services.data_loader import (
    load_dashboard_data,
    load_rebalance_log,
    load_risk_flags,
)


def _delta_str(value: float, decimals: int = 4) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.{decimals}f}"


def render() -> None:
    st.header("總覽")
    st.caption("最新一次紙上再平衡的快照與當前 alpha / regime 狀態。")

    log = load_rebalance_log()
    risk_flags = load_risk_flags()
    dash = load_dashboard_data()

    if log is None or log.empty:
        st.info(
            "尚無任何紙上再平衡紀錄。請執行 "
            "`.venv/bin/python scripts/run_paper_portfolio.py --backfill` "
            "或在「再平衡」頁建立第一筆。"
        )
    else:
        latest = log.iloc[-1]
        nav_paper = float(latest["nav_paper"])
        nav_25 = float(latest["nav_paper_25bps"])
        nav_50 = float(latest["nav_paper_50bps"])
        nav_bm = float(latest["nav_benchmark"])

        st.subheader("淨值 (NAV)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("紙上 (毛)", f"{nav_paper:.4f}",
                  _delta_str(nav_paper - nav_bm), delta_color="normal")
        c2.metric("紙上 @ 25 bps", f"{nav_25:.4f}",
                  _delta_str(nav_25 - nav_bm), delta_color="normal")
        c3.metric("紙上 @ 50 bps", f"{nav_50:.4f}",
                  _delta_str(nav_50 - nav_bm), delta_color="normal")
        c4.metric("基準 (0050.TW)", f"{nav_bm:.4f}")
        st.caption("Δ 為相對基準淨值。")

        st.subheader("組合狀態")
        c1, c2, c3, c4 = st.columns(4)
        dd = float(latest["drawdown_paper"])
        c1.metric("回檔 (紙上)", f"{dd*100:.2f}%")
        c2.metric("最近換手量", f"{float(latest['base_turnover']):.2f}")
        c3.metric("持股數", f"{int(latest['n_holdings'])}")
        risk_n = 0 if risk_flags is None else int(len(risk_flags))
        c4.metric("風險旗標總數", f"{risk_n}")

        st.caption(
            f"最近一次再平衡：**{latest['rebalance_date']}**　|　"
            f"累計再平衡次數：**{len(log)}**"
        )

    if dash is not None:
        regime = dash.get("market_regime") or {}
        if regime:
            st.divider()
            st.subheader("市場 Regime")
            cols = st.columns(4)
            cols[0].metric("大盤", str(regime.get("market_regime", "—")))
            cols[1].metric("AI 題材", str(regime.get("ai_regime", "—")))
            cols[2].metric("風險等級", str(regime.get("risk_level", "—")))
            cols[3].metric(
                "建議 Top-N",
                str(regime.get("recommended_top_n", "—")),
            )
            notes = regime.get("notes")
            if notes:
                with st.expander("Regime 說明"):
                    st.code(notes)
