"""Shared dataframe styling helpers — color tags、外部連結欄位、Alpha 漸層。

UI-only：不影響資料層。所有函式對缺欄安全（拿不到 col 直接回原物件）。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


# Goodinfo TW URL；fragment 部分用來讓 LinkColumn 的 display_text 抓回原 ticker 顯示
GOODINFO_TPL = "https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={code}#{ticker}"

ZONE_COLORS: dict[str, str] = {
    "Strong Candidate": "#16a34a",   # green-600
    "Watchlist":        "#2563eb",   # blue-600
    "Narrative Watch":  "#7c3aed",   # violet-600
    "Neutral":          "#64748b",   # slate-500
    "Avoid Chasing":    "#ea580c",   # orange-600
    "Avoid":            "#dc2626",   # red-600
    # 中文 alias — 顯示時翻譯成中文後 styler 仍能配色
    "強候選":   "#16a34a",
    "觀察名單": "#2563eb",
    "題材觀察": "#7c3aed",
    "中性":     "#64748b",
    "避免追高": "#ea580c",
    "避免":     "#dc2626",
}


# 英文決策區 → 中文顯示標籤
ZONE_LABELS_ZH: dict[str, str] = {
    "Strong Candidate": "強候選",
    "Watchlist":        "觀察名單",
    "Narrative Watch":  "題材觀察",
    "Neutral":          "中性",
    "Avoid Chasing":    "避免追高",
    "Avoid":            "避免",
}


# 每一個決策區的白話說明 — 用於欄位標題的 hover tooltip
ZONE_DESCRIPTIONS_ZH: dict[str, str] = {
    "強候選":   "Tier 1 殘差 α 強（≥1.5）、整體 alpha ≥2.5、風險扣分可控（≤2.0）、信心夠。研究優先順序最高,但**不是 buy 訊號**——需自行確認基本面與部位大小。",
    "觀察名單": "殘差 α 為正、整體 alpha ≥2.0,但有一項條件未到 Strong 標準(風險扣分較大或信心略低)。值得追蹤,等更好的進場點。",
    "題材觀察": "新聞流量強但量化指標沒確認(例如殘差 α 沒同步走強)。只當題材觀察、不下注。",
    "中性":     "沒有顯著訊號 — alpha 普通、殘差 α 沒明顯方向。沒事不需動作,有空再看。",
    "避免追高": "已經過熱:同時觸發 overbought 或 valuation_extreme 風險旗標,且風險嚴重度 ≥6。即使 alpha 高也**不要追**,等估值或技術面退溫。",
    "避免":     "殘差 α 為負(整體 alpha < 0)。跟大盤+AI 因子比起來表現偏弱,跳過,等 setup 改變。",
}


def zone_help_text() -> str:
    """Return a multi-line markdown string suitable for column-header `help=`.

    Streamlit renders this as a hover tooltip with the `?` icon next to the
    column header. Each zone gets one bullet so the user can read all six
    classifications at once.
    """
    lines = [
        "**決策區說明**(由優先順序排列)",
        "",
        "Strong Candidate / Watchlist / Narrative Watch 是研究優先順序;",
        "Avoid Chasing / Avoid 是「不要做」的標記。**全部都不是交易訊號**。",
        "",
    ]
    for zh, desc in ZONE_DESCRIPTIONS_ZH.items():
        lines.append(f"- **{zh}** — {desc}")
    return "\n".join(lines)


def translate_zones(df: pd.DataFrame, col: str = "decision_zone") -> pd.DataFrame:
    """Return a copy with ``col`` values mapped through ``ZONE_LABELS_ZH``."""
    if col not in df.columns:
        return df
    out = df.copy()
    out[col] = out[col].map(lambda v: ZONE_LABELS_ZH.get(v, v))
    return out


# `suggested_action` 字串 → 繁體中文。鍵必須與 `_resolve_decision_zone`
# (fusion/scoring_model_v2.py) 寫出的字串一字不差。新增 zone 時務必同步更新。
ACTION_LABELS_ZH: dict[str, str] = {
    "Skip — negative residual alpha. Wait for setup change.":
        "跳過 — 殘差 α 為負,等 setup 改變。",
    "Overbought or valuation-extreme + high risk severity — do not chase.":
        "過熱(超買或估值極端)+ 高風險嚴重度 — 不要追高。",
    "Research priority — high residual alpha, low risk.":
        "研究優先 — 殘差 α 強、風險可控。**不是 buy 訊號**。",
    "News flow positive but quant not confirming — track only.":
        "新聞題材正向但量化未確認 — 僅追蹤,不下注。",
    "Positive alpha + residual + acceptable risk — track.":
        "Alpha 與殘差 α 皆正、風險可接受 — 追蹤觀察。",
    "Capped by risk flags — do not size up.":
        "受風險旗標限制 — 追蹤但不要加碼。",
    "No urgency.":
        "不急,沒有顯著訊號。",
}


def translate_actions(df: pd.DataFrame, col: str = "suggested_action") -> pd.DataFrame:
    """Return a copy with ``col`` values mapped through ``ACTION_LABELS_ZH``.

    Unknown strings (e.g. future zones) pass through unchanged so the table
    never silently drops content.
    """
    if col not in df.columns:
        return df
    out = df.copy()
    out[col] = out[col].map(lambda v: ACTION_LABELS_ZH.get(v, v) if isinstance(v, str) else v)
    return out

SEVERITY_COLORS: dict[str, str] = {
    "high":   "#dc2626",
    "medium": "#ea580c",
    "low":    "#64748b",
}


# ---------------------------------------------------------------------------
# Ticker → 外部連結

def ticker_to_url(ticker) -> str:
    if not isinstance(ticker, str) or not ticker:
        return ""
    code = ticker.split(".")[0]
    return GOODINFO_TPL.format(code=code, ticker=ticker)


def with_ticker_link(df: pd.DataFrame, col: str = "ticker") -> pd.DataFrame:
    """Return a copy with ``col`` rewritten to a Goodinfo URL."""
    if col not in df.columns:
        return df
    out = df.copy()
    out[col] = out[col].astype(str).map(ticker_to_url)
    return out


def ticker_link_column(label: str = "代號"):
    """LinkColumn that displays the original ticker via the URL fragment."""
    return st.column_config.LinkColumn(
        label,
        display_text=r"#(.+)$",
        width="small",
        help="點擊開啟 Goodinfo 個股頁",
    )


# ---------------------------------------------------------------------------
# Styler helpers — 色塊與漸層

def _bg_color_factory(mapping: dict[str, str]):
    def _f(v):
        c = mapping.get(v, "")
        if not c:
            return ""
        return f"background-color: {c}; color: white; font-weight: 600"
    return _f


def style_zones(styler, col: str = "decision_zone"):
    if col not in styler.data.columns:
        return styler
    return styler.map(_bg_color_factory(ZONE_COLORS), subset=[col])


def style_severity(styler, col: str = "severity"):
    if col not in styler.data.columns:
        return styler
    return styler.map(_bg_color_factory(SEVERITY_COLORS), subset=[col])


def style_alpha_gradient(styler, col: str = "alpha_score", cmap: str = "RdYlGn"):
    if col not in styler.data.columns:
        return styler
    s = styler.data[col]
    if s.dropna().empty:
        return styler
    vmax = float(s.abs().max())
    return styler.background_gradient(
        subset=[col], cmap=cmap, vmin=-vmax, vmax=vmax
    )


def style_residual_gradient(styler, col: str = "residual_alpha_score",
                            cmap: str = "RdYlGn"):
    if col not in styler.data.columns:
        return styler
    s = styler.data[col]
    if s.dropna().empty:
        return styler
    vmax = float(s.abs().max())
    return styler.background_gradient(
        subset=[col], cmap=cmap, vmin=-vmax, vmax=vmax
    )
