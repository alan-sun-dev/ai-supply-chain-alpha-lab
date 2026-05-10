"""績效頁 — NAV / 回檔 / 月報酬率分頁。"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.services.data_loader import load_rebalance_log


NAV_COLS: list[tuple[str, str]] = [
    ("nav_paper", "紙上 (毛)"),
    ("nav_paper_25bps", "紙上 @ 25 bps"),
    ("nav_paper_50bps", "紙上 @ 50 bps"),
    ("nav_benchmark", "基準 (0050.TW)"),
]


def _kpi_row(df: pd.DataFrame) -> None:
    last = df.iloc[-1]
    nav_p = float(last["nav_paper"])
    nav_b = float(last["nav_benchmark"])
    excess = nav_p - nav_b
    dd = float(last["drawdown_paper"])
    n = int(len(df))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("最新紙上 NAV", f"{nav_p:.4f}", f"vs 基準 {excess:+.4f}")
    c2.metric("基準 NAV", f"{nav_b:.4f}")
    c3.metric("紙上回檔 (最新)", f"{dd*100:.2f}%")
    c4.metric("再平衡次數", f"{n}")


def _nav_chart(df: pd.DataFrame) -> None:
    nav_long = pd.concat(
        [
            df[["rebalance_date", col]]
            .rename(columns={col: "nav"})
            .assign(系列=label)
            for col, label in NAV_COLS
            if col in df.columns
        ],
        ignore_index=True,
    )
    if nav_long.empty:
        st.info("找不到任何 NAV 欄位。")
        return
    fig = px.line(
        nav_long,
        x="rebalance_date",
        y="nav",
        color="系列",
        labels={"rebalance_date": "再平衡日期", "nav": "NAV"},
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=420)
    st.plotly_chart(fig, use_container_width=True)


def _drawdown_chart(df: pd.DataFrame) -> None:
    if "drawdown_paper" not in df.columns:
        st.info("rebalance_log.csv 沒有 drawdown_paper 欄位。")
        return
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["rebalance_date"],
            y=df["drawdown_paper"] * 100,
            fill="tozeroy",
            name="回檔 (%)",
            line=dict(color="#d62728"),
        )
    )
    fig.update_layout(
        yaxis_title="回檔 (%)",
        xaxis_title="再平衡日期",
        margin=dict(l=10, r=10, t=10, b=10),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


def _period_table(df: pd.DataFrame) -> None:
    cols = [
        c for c in
        ("rebalance_date", "period_return", "period_return_25bps",
         "period_return_50bps", "benchmark_return", "excess_vs_benchmark",
         "base_turnover", "n_holdings", "notes")
        if c in df.columns
    ]
    view = df[cols].copy()
    pct_cols = [c for c in view.columns if c.endswith("return") or c == "excess_vs_benchmark"]
    for c in pct_cols:
        view[c] = view[c] * 100
    nc = st.column_config.NumberColumn
    column_config = {
        "rebalance_date": st.column_config.DatetimeColumn("再平衡日期", format="YYYY-MM-DD"),
        "period_return": nc("毛報酬", format="%.2f%%"),
        "period_return_25bps": nc("@25bps 報酬", format="%.2f%%"),
        "period_return_50bps": nc("@50bps 報酬", format="%.2f%%"),
        "benchmark_return": nc("基準報酬", format="%.2f%%"),
        "excess_vs_benchmark": nc("超額", format="%+.2f%%"),
        "base_turnover": nc("換手量", format="%.2f"),
        "n_holdings": nc("持股數", format="%d"),
        "notes": st.column_config.TextColumn("備註"),
    }
    st.dataframe(
        view.iloc[::-1].reset_index(drop=True),  # newest first
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )


def render() -> None:
    st.header("績效")
    log = load_rebalance_log()
    if log is None or log.empty:
        st.warning(
            "找不到 rebalance_log.csv 或內容為空。"
            "請先執行 `.venv/bin/python scripts/run_paper_portfolio.py --backfill`。"
        )
        return

    df = log.copy().sort_values("rebalance_date").reset_index(drop=True)
    df["rebalance_date"] = pd.to_datetime(df["rebalance_date"])

    _kpi_row(df)
    st.divider()

    tab_nav, tab_dd, tab_table = st.tabs(["NAV 走勢", "回檔曲線", "逐次明細"])
    with tab_nav:
        _nav_chart(df)
    with tab_dd:
        _drawdown_chart(df)
    with tab_table:
        _period_table(df)
