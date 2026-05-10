"""紙上組合再平衡 — 預覽 → 確認 dialog modal。

State machine：
    PREVIEW_KEY None    → 顯示產生預覽表單
    PREVIEW_KEY 有值     → 顯示權重對照、成本、警告
    按「打開確認對話框」 → 進入 ``@st.dialog`` modal，內含 checkbox + 執行 / 取消
    執行完              → 結果存入 RESULT_KEY，主頁顯示成敗、stdout、stderr

不在這裡實作任何 scoring。預覽絕不寫檔。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.services.data_loader import clear_all_caches
from dashboard.services.paper_portfolio_service import (
    CONFIRM_CHECKBOX_LABEL,
    confirm_rebalance,
    generate_preview,
    rerender_report,
)

PREVIEW_KEY = "rebalance_preview"
RESULT_KEY = "rebalance_last_result"
CHECKBOX_KEY = "rebalance_confirm_checkbox"


def _reset_preview() -> None:
    st.session_state.pop(PREVIEW_KEY, None)
    st.session_state.pop(CHECKBOX_KEY, None)


def _side_by_side_column_config() -> dict:
    nc = st.column_config.NumberColumn
    return {
        "ticker": st.column_config.TextColumn("代號", width="small"),
        "company_name": st.column_config.TextColumn("公司", width="medium"),
        "theme": st.column_config.TextColumn("題材"),
        "prev_weight": nc("目前權重", format="%.2f%%"),
        "target_weight": nc("提案權重", format="%.2f%%"),
        "weight_change": nc("變動", format="%+.2f%%"),
    }


@st.dialog("確認再平衡", width="large")
def _confirm_dialog(preview, notes: str) -> None:
    """Modal — checkbox 強制視線聚焦；執行後寫入 session_state 並 rerun。"""
    st.markdown(f"**再平衡日期**：`{preview.rebalance_date.date()}`")
    st.markdown(f"**備註**：{notes or '（無）'}")
    st.markdown(
        f"**換手量**：{preview.base_turnover:.2f}　|　"
        f"**預估成本**：25 bps `{preview.est_cost_25bps*100:.3f}%` "
        f"／ 50 bps `{preview.est_cost_50bps*100:.3f}%`"
    )

    if preview.duplicate_date:
        st.error(
            f"**重複日期警告** — {preview.duplicate_date_value.date()} 已存在於 "
            "rebalance_log.csv。執行將覆寫該筆。"
        )

    st.markdown("**將執行的子行程**")
    st.code(
        f"python scripts/run_paper_portfolio.py --rebalance "
        f"--date {preview.rebalance_date.strftime('%Y-%m-%d')} "
        f'--notes "{notes}"',
        language="bash",
    )
    st.caption("備份位置：`archive/dashboard_rebalance_backup/<時戳>/`（共 4 檔）")

    confirmed = st.checkbox(CONFIRM_CHECKBOX_LABEL, key="dlg_confirm_chk")

    cols = st.columns([1, 1])
    if cols[0].button("取消", use_container_width=True, key="dlg_cancel"):
        st.session_state.pop("dlg_confirm_chk", None)
        st.rerun()
    if cols[1].button(
        "執行再平衡",
        type="primary",
        use_container_width=True,
        disabled=not confirmed,
        key="dlg_execute",
    ):
        with st.spinner("正在備份 4 檔並呼叫 run_paper_portfolio.py …"):
            result = confirm_rebalance(
                rebalance_date=preview.rebalance_date,
                notes=notes,
            )
        st.session_state[RESULT_KEY] = result
        st.session_state.pop("dlg_confirm_chk", None)
        clear_all_caches()
        _reset_preview()
        st.rerun()


def _show_last_result() -> None:
    result = st.session_state.get(RESULT_KEY)
    if result is None:
        return
    st.divider()
    st.subheader("最近一次執行結果")
    if result.ok:
        st.success(f"再平衡已套用（returncode {result.returncode}）。")
    else:
        st.error(
            f"子行程失敗（returncode {result.returncode}）。"
            "現有檔案已備份至下方路徑。"
        )
    if result.backup_dir is not None:
        st.caption(f"備份資料夾：`{result.backup_dir}`")
        if result.backup_files:
            st.caption("已備份：" + "、".join(p.name for p in result.backup_files))
        else:
            st.caption("（無檔案存在 — 屬首次執行。）")
    st.code(" ".join(result.cmd), language="bash")
    if result.stdout:
        with st.expander("stdout"):
            st.code(result.stdout)
    if result.stderr:
        with st.expander("stderr"):
            st.code(result.stderr)
    if st.button("清除結果"):
        st.session_state.pop(RESULT_KEY, None)
        st.rerun()


def render() -> None:
    st.header("再平衡（紙上）")
    st.caption(
        "兩段式流程：**預覽**會計算提案的 top-N（不寫檔）；"
        "**確認對話框**會列出將執行的指令、要求勾選同意，再以子行程呼叫 "
        "`scripts/run_paper_portfolio.py --rebalance`。"
    )

    with st.form("rebalance_form", clear_on_submit=False):
        col_a, col_b, col_c = st.columns([2, 1, 1])
        date_input = col_a.date_input(
            "再平衡日期",
            value=pd.Timestamp.today().normalize().date(),
            key="rebalance_date_input",
        )
        top_n = col_b.number_input("Top N", min_value=1, max_value=20, value=5, step=1)
        max_per_theme = col_c.number_input(
            "每題材上限", min_value=1, max_value=10, value=2, step=1
        )
        notes = st.text_input(
            "備註（自由輸入，會寫入 rebalance_log.csv）",
            value="dashboard rebalance",
        )
        cols = st.columns([1, 1, 4])
        do_preview = cols[0].form_submit_button("產生預覽", type="primary")
        do_reset = cols[1].form_submit_button("重設")

    if do_reset:
        _reset_preview()
        st.info("已清除預覽。")

    if do_preview:
        preview = generate_preview(
            rebalance_date=pd.Timestamp(date_input),
            top_n=int(top_n),
            max_per_theme=int(max_per_theme),
        )
        st.session_state[PREVIEW_KEY] = preview
        st.session_state["rebalance_notes"] = notes

    preview = st.session_state.get(PREVIEW_KEY)
    if preview is None:
        _show_last_result()
        st.info("尚未產生預覽 — 填妥上方表單後按「產生預覽」。")
        return

    st.divider()
    st.subheader(f"預覽：{preview.rebalance_date.date()}")

    for w in preview.warnings:
        st.warning(w)
    if preview.duplicate_date:
        st.error(
            f"**重複日期警告** — {preview.duplicate_date_value.date()} 已存在於 "
            "rebalance_log.csv。確認後將覆寫該筆。"
        )
    if not preview.has_ranking:
        _show_last_result()
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("基本換手量 (Σ|Δw|)", f"{preview.base_turnover:.2f}")
    c2.metric("預估成本 @ 25 bps", f"{preview.est_cost_25bps*100:.3f}%")
    c3.metric("預估成本 @ 50 bps", f"{preview.est_cost_50bps*100:.3f}%")

    st.markdown("**權重對照**（目前 → 提案）")
    if preview.side_by_side.empty:
        st.info("無任何標的入選 — alpha_ranking 沒有合格列。")
    else:
        side_disp = preview.side_by_side.copy()
        for col in ("prev_weight", "target_weight", "weight_change"):
            if col in side_disp.columns:
                side_disp[col] = side_disp[col] * 100
        st.dataframe(
            side_disp,
            use_container_width=True,
            hide_index=True,
            column_config=_side_by_side_column_config(),
        )

    if not preview.proposed.empty:
        with st.expander("提案持股明細"):
            st.dataframe(preview.proposed, use_container_width=True, hide_index=True)
    if not preview.current.empty:
        with st.expander("目前 target_weights.csv"):
            st.dataframe(preview.current, use_container_width=True, hide_index=True)

    st.divider()
    notes_now = st.session_state.get("rebalance_notes", "")
    open_dialog = st.button(
        "打開確認對話框 …",
        type="primary",
        use_container_width=True,
        key="open_confirm_dialog",
    )
    if open_dialog:
        _confirm_dialog(preview, notes_now)

    st.divider()
    if st.button("僅重產 markdown 報告（不執行再平衡）"):
        with st.spinner("正在重新產生報告 …"):
            r = rerender_report()
        if r.ok:
            st.success(f"報告已重產（returncode {r.returncode}）。")
        else:
            st.error(f"重產失敗（returncode {r.returncode}）。")
        if r.stdout:
            with st.expander("stdout"):
                st.code(r.stdout)
        if r.stderr:
            with st.expander("stderr"):
                st.code(r.stderr)
        clear_all_caches()

    _show_last_result()
