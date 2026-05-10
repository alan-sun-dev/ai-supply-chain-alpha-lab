"""當前組合頁 — 目標權重 + 題材曝險長條圖。"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components._columns import (
    ticker_link_column,
    translate_zones,
    with_ticker_link,
    zone_help_text,
)
from dashboard.services.data_loader import load_rebalance_log, load_target_weights


def _target_column_config() -> dict:
    nc = st.column_config.NumberColumn
    return {
        "ticker": ticker_link_column("代號"),
        "company_name": st.column_config.TextColumn("公司", width="medium"),
        "theme": st.column_config.TextColumn("題材", width="medium"),
        "target_weight": nc("目標權重", format="%.2f%%"),
        "alpha_score": nc("Alpha", format="%.3f"),
        "decision_zone": st.column_config.TextColumn("決策區", help=zone_help_text()),
        "risk_flags": st.column_config.TextColumn("風險旗標"),
        "notes": st.column_config.TextColumn("備註"),
    }


def render() -> None:
    st.header("當前組合")
    target = load_target_weights()
    log = load_rebalance_log()

    if target is None or target.empty:
        st.warning(
            "找不到 target_weights.csv 或內容為空。請先 backfill 或執行一次再平衡。"
        )
        return

    n_holdings = int(len(target))
    gross = float(target["target_weight"].sum()) if "target_weight" in target.columns else 0.0
    n_themes = int(target["theme"].nunique()) if "theme" in target.columns else 0
    last_date = "—"
    if log is not None and not log.empty:
        last_date = pd.to_datetime(log["rebalance_date"]).iloc[-1].strftime("%Y-%m-%d")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("持股數", f"{n_holdings}")
    c2.metric("總曝險", f"{gross*100:.0f}%")
    c3.metric("題材數", f"{n_themes}")
    c4.metric("最近再平衡", last_date)

    st.subheader("目標權重")
    display = target.copy()
    if "target_weight" in display.columns:
        display["target_weight"] = display["target_weight"] * 100  # for %.2f%% column format
    display = with_ticker_link(display, "ticker")
    display = translate_zones(display, "decision_zone")
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config=_target_column_config(),
    )

    if "theme" in target.columns and "target_weight" in target.columns:
        theme_w = (
            target.groupby("theme", as_index=False)["target_weight"]
            .sum()
            .sort_values("target_weight", ascending=True)  # ascending for horizontal bar
        )
        if not theme_w.empty:
            st.subheader("題材曝險")
            fig = px.bar(
                theme_w,
                x="target_weight",
                y="theme",
                orientation="h",
                text=theme_w["target_weight"].map(lambda x: f"{x:.0%}"),
                labels={"target_weight": "權重", "theme": "題材"},
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                xaxis_tickformat=".0%",
                margin=dict(l=10, r=30, t=10, b=10),
                height=max(220, 36 * len(theme_w) + 80),
            )
            st.plotly_chart(fig, use_container_width=True)
