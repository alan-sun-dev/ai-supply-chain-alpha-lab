"""Alpha 排名頁 — 色碼決策區、Alpha 漸層、Goodinfo 連結、ProgressColumn。

Sidebar 篩選 + 表格放在 ``@st.fragment`` 裡，避免動 filter 時整個 app 重 render。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.components._columns import (
    ZONE_LABELS_ZH,
    style_alpha_gradient,
    style_residual_gradient,
    style_zones,
    ticker_link_column,
    translate_actions,
    translate_zones,
    with_ticker_link,
    zone_help_text,
)
from dashboard.services.data_loader import load_alpha_ranking

ZONE_PRIORITY = {
    "Strong Candidate": 0,
    "Watchlist": 1,
    "Narrative Watch": 2,
    "Neutral": 3,
    "Avoid Chasing": 4,
    "Avoid": 5,
}


def _ranking_column_config(view: pd.DataFrame) -> dict:
    nc = st.column_config.NumberColumn
    cfg: dict = {
        "rank": nc("排名", format="%d", width="small"),
        "ticker": ticker_link_column("代號"),
        "company_name": st.column_config.TextColumn("公司", width="medium"),
        "theme": st.column_config.TextColumn("題材", width="medium"),
        "alpha_score": nc("Alpha", format="%.3f"),
        "decision_zone": st.column_config.TextColumn(
            "決策區", width="medium", help=zone_help_text()
        ),
        "risk_severity": nc("風險嚴重度", format="%d"),
        "confidence_score": nc("信心分數", format="%.2f"),
        "data_quality": nc("資料品質", format="%.2f"),
        "main_positive_drivers": st.column_config.TextColumn("正向驅動"),
        "main_negative_drivers": st.column_config.TextColumn("負向驅動"),
        "risk_flags": st.column_config.TextColumn("風險旗標"),
        "suggested_action": st.column_config.TextColumn("建議動作"),
        "notes": st.column_config.TextColumn("備註"),
    }
    # ProgressColumn — 殘差 α 可正可負；用 -|max|, +|max| 對稱
    if "residual_alpha_score" in view.columns and not view["residual_alpha_score"].dropna().empty:
        rmax = float(view["residual_alpha_score"].abs().max())
        rmax = max(rmax, 0.001)
        cfg["residual_alpha_score"] = st.column_config.ProgressColumn(
            "殘差 α", format="%.3f", min_value=-rmax, max_value=rmax,
        )
    # 風險扣分 — 已知非負
    if "risk_penalty" in view.columns and not view["risk_penalty"].dropna().empty:
        pmax = float(view["risk_penalty"].max())
        pmax = max(pmax, 0.001)
        cfg["risk_penalty"] = st.column_config.ProgressColumn(
            "風險扣分", format="%.3f", min_value=0.0, max_value=pmax,
        )
    return cfg


@st.fragment
def _ranking_fragment(df: pd.DataFrame) -> None:
    # 篩選列（橫向）— st.fragment 不支援 sidebar，放頁面頂端反而更貼近資料
    with st.container(border=True):
        st.markdown("**篩選**")
        f1, f2, f3, f4 = st.columns([1, 2, 2, 1])
        ticker_q = f1.text_input("代號包含", "", key="rank_ticker_q")
        themes = sorted(df["theme"].dropna().unique().tolist()) if "theme" in df.columns else []
        theme_sel = f2.multiselect("題材", themes, default=themes, key="rank_theme_sel")
        zones = (
            sorted(
                df["decision_zone"].dropna().unique().tolist(),
                key=lambda z: ZONE_PRIORITY.get(z, 99),
            )
            if "decision_zone" in df.columns
            else []
        )
        zone_sel = f3.multiselect(
            "決策區", zones, default=zones, key="rank_zone_sel",
            format_func=lambda z: ZONE_LABELS_ZH.get(z, z),
        )
        max_risk = (
            int(df["risk_severity"].max())
            if "risk_severity" in df.columns and not df["risk_severity"].isna().all()
            else 0
        )
        risk_cap = f4.slider(
            "風險嚴重度上限",
            min_value=0,
            max_value=max(max_risk, 0),
            value=max(max_risk, 0),
            key="rank_risk_cap",
        )

    view = df.copy()
    if ticker_q:
        view = view[view["ticker"].astype(str).str.contains(ticker_q, case=False, na=False)]
    if theme_sel and "theme" in view.columns:
        view = view[view["theme"].isin(theme_sel)]
    if zone_sel and "decision_zone" in view.columns:
        view = view[view["decision_zone"].isin(zone_sel)]
    if "risk_severity" in view.columns:
        view = view[view["risk_severity"].fillna(0).astype(int) <= int(risk_cap)]

    # KPI strip — 隨篩選即時變動
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("候選總數", f"{len(df)}")
    c2.metric("篩選後", f"{len(view)}")
    if "alpha_score" in view.columns and not view.empty:
        c3.metric("Alpha 中位數", f"{view['alpha_score'].median():.3f}")
        c4.metric("Alpha 最大", f"{view['alpha_score'].max():.3f}")
    else:
        c3.metric("Alpha 中位數", "—")
        c4.metric("Alpha 最大", "—")

    if view.empty:
        st.info("沒有符合條件的列。")
        return

    # Ticker 改成 URL(為 LinkColumn)、決策區與建議動作翻成中文
    display = with_ticker_link(view, "ticker")
    display = translate_zones(display, "decision_zone")
    display = translate_actions(display, "suggested_action")

    # 套用 Styler:決策區色塊(ZONE_COLORS 含中英文 key) + Alpha / 殘差 α 漸層
    column_config = _ranking_column_config(display)
    styler = display.style
    styler = style_zones(styler, "decision_zone")
    styler = style_alpha_gradient(styler, "alpha_score")
    styler = style_residual_gradient(styler, "residual_alpha_score")

    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )


def render() -> None:
    st.header("Alpha 排名")
    df = load_alpha_ranking()
    if df is None or df.empty:
        st.warning(
            "找不到 alpha_ranking.csv 或內容為空。"
            "請執行 `.venv/bin/python scripts/run_alpha_ranking.py` "
            "或 `scripts/run_daily_pipeline.py` 重新產生。"
        )
        return
    _ranking_fragment(df)
