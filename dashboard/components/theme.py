"""題材曝險頁 — 當前組合 vs 排名分布 vs 風險統計。"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.services.data_loader import (
    load_alpha_ranking,
    load_risk_flags,
    load_target_weights,
)


def _current_tab(target: pd.DataFrame | None) -> None:
    if target is None or target.empty or "theme" not in target.columns:
        st.info("尚無 target_weights，無法繪製。")
        return
    theme_w = (
        target.groupby("theme", as_index=False)["target_weight"]
        .sum()
        .sort_values("target_weight", ascending=True)
    )
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


def _ranking_tab(ranking: pd.DataFrame | None) -> None:
    if ranking is None or ranking.empty or "theme" not in ranking.columns:
        st.info("alpha_ranking.csv 為空。")
        return
    agg = (
        ranking.groupby("theme", as_index=False)
        .agg(
            n_tickers=("ticker", "count"),
            avg_alpha=("alpha_score", "mean"),
            max_alpha=("alpha_score", "max"),
        )
        .sort_values("avg_alpha", ascending=False)
    )
    nc = st.column_config.NumberColumn
    st.dataframe(
        agg,
        use_container_width=True,
        hide_index=True,
        column_config={
            "theme": st.column_config.TextColumn("題材"),
            "n_tickers": nc("候選數", format="%d"),
            "avg_alpha": nc("平均 Alpha", format="%.3f"),
            "max_alpha": nc("最大 Alpha", format="%.3f"),
        },
    )


def _risk_tab(risk: pd.DataFrame | None) -> None:
    if risk is None or risk.empty or "theme" not in risk.columns:
        st.success("目前各題材皆無風險旗標。")
        return
    rf = (
        risk.groupby("theme", as_index=False)
        .size()
        .rename(columns={"size": "n_flags"})
        .sort_values("n_flags", ascending=False)
    )
    st.dataframe(
        rf,
        use_container_width=True,
        hide_index=True,
        column_config={
            "theme": st.column_config.TextColumn("題材"),
            "n_flags": st.column_config.NumberColumn("旗標數", format="%d"),
        },
    )


def render() -> None:
    st.header("題材曝險")
    target = load_target_weights()
    ranking = load_alpha_ranking()
    risk = load_risk_flags()

    tab_cur, tab_rank, tab_risk = st.tabs([
        "當前組合題材分布", "排名題材統計", "題材風險統計",
    ])
    with tab_cur:
        _current_tab(target)
    with tab_rank:
        _ranking_tab(ranking)
    with tab_risk:
        _risk_tab(risk)
