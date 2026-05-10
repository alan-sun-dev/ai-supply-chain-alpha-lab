"""風險旗標頁 — 可篩選的 risk_flags 表。"""
from __future__ import annotations

import streamlit as st

from dashboard.components._columns import (
    style_severity,
    ticker_link_column,
    with_ticker_link,
)
from dashboard.services.data_loader import load_risk_flags

SEVERITY_PRIORITY = {"high": 0, "medium": 1, "low": 2}


def _column_config() -> dict:
    return {
        "ticker": ticker_link_column("代號"),
        "company_name": st.column_config.TextColumn("公司", width="medium"),
        "theme": st.column_config.TextColumn("題材", width="medium"),
        "risk_flag": st.column_config.TextColumn("風險類型"),
        "severity": st.column_config.TextColumn("嚴重度", width="small"),
        "description": st.column_config.TextColumn("說明"),
    }


def render() -> None:
    st.header("風險旗標")
    df = load_risk_flags()
    if df is None or df.empty:
        st.success("目前沒有任何風險旗標。")
        return

    with st.sidebar:
        st.markdown("### 風險篩選")
        sevs = (
            sorted(df["severity"].dropna().unique().tolist(),
                   key=lambda s: SEVERITY_PRIORITY.get(s, 99))
            if "severity" in df.columns else []
        )
        flags = sorted(df["risk_flag"].dropna().unique().tolist()) if "risk_flag" in df.columns else []
        themes = sorted(df["theme"].dropna().unique().tolist()) if "theme" in df.columns else []
        sev_sel = st.multiselect("嚴重度", sevs, default=sevs, key="risk_sev")
        flag_sel = st.multiselect("風險類型", flags, default=flags, key="risk_flag")
        theme_sel = st.multiselect("題材", themes, default=themes, key="risk_theme")
        ticker_q = st.text_input("代號包含", "", key="risk_ticker_q")

    view = df.copy()
    if sev_sel and "severity" in view.columns:
        view = view[view["severity"].isin(sev_sel)]
    if flag_sel and "risk_flag" in view.columns:
        view = view[view["risk_flag"].isin(flag_sel)]
    if theme_sel and "theme" in view.columns:
        view = view[view["theme"].isin(theme_sel)]
    if ticker_q and "ticker" in view.columns:
        view = view[view["ticker"].astype(str).str.contains(ticker_q, case=False, na=False)]

    n_high = int((view["severity"] == "high").sum()) if "severity" in view.columns else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("旗標總數", f"{len(df)}")
    c2.metric("篩選後", f"{len(view)}")
    c3.metric("高嚴重度", f"{n_high}")
    c4.metric("受影響公司數",
              f"{int(view['ticker'].nunique()) if 'ticker' in view.columns else 0}")

    if "severity" in view.columns:
        view = view.assign(
            _sev_order=view["severity"].map(lambda s: SEVERITY_PRIORITY.get(s, 99))
        ).sort_values(["_sev_order", "ticker"]).drop(columns=["_sev_order"])

    display = with_ticker_link(view, "ticker")
    styler = style_severity(display.style, "severity")
    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        column_config=_column_config(),
    )
