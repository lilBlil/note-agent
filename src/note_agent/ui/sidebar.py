"""Sidebar: history (past runs) on top, all settings below.

Nothing here touches the workflow — settings are just collected into a dict
and history is read-only snapshot loading.
"""

from __future__ import annotations

import streamlit as st

from note_agent.ui import history
from note_agent.ui.state import set_view


# How many recent projects to show before collapsing the rest, so the
# settings below stay visible even with a long history.
_VISIBLE = 6


def _delete_project(rid: str, active: str | None) -> None:
    if history.delete_run(rid):
        if rid == active:
            set_view(None)
            st.session_state.pop("na_sel", None)
        st.rerun()


@st.dialog("删除项目", width="small")
def _confirm_delete_dialog(rid: str, name: str, active: str | None) -> None:
    st.write(f"确定要删除「{name}」吗？")
    st.caption("此操作会删除该项目的本地运行记录。")
    c_cancel, c_delete = st.columns(2)
    with c_cancel:
        if st.button("取消", key=f"na_delete_cancel_{rid}", use_container_width=True):
            st.rerun()
    with c_delete:
        if st.button("删除", key=f"na_delete_confirm_{rid}", use_container_width=True):
            _delete_project(rid, active)


@st.dialog("重命名项目", width="small")
def _rename_dialog(rid: str, name: str) -> None:
    new_name = st.text_input("项目名称", value=name, key=f"na_rename_dialog_input_{rid}")
    c_cancel, c_save = st.columns(2)
    with c_cancel:
        if st.button("取消", key=f"na_rename_cancel_{rid}", use_container_width=True):
            st.rerun()
    with c_save:
        if st.button("保存", key=f"na_rename_save_{rid}", use_container_width=True):
            if history.rename_run(rid, new_name):
                st.rerun()


def _project_actions(rid: str, name: str, active: str | None) -> None:
    if st.button("重命名", key=f"na_rename_{rid}", use_container_width=True):
        _rename_dialog(rid, name)
    if st.button("删除", key=f"na_delete_{rid}", use_container_width=True):
        _confirm_delete_dialog(rid, name, active)


def _project_row(r: dict, active: str | None) -> None:
    rid = r["run_id"]
    name = (r["preview"] or rid).strip() or rid
    label = name[:44]
    key_wrap = f"na_project_row_active_{rid}" if rid == active else f"na_project_row_{rid}"
    with st.container(key=key_wrap):
        if st.button(label, key=f"hist_{rid}", use_container_width=True):
            loaded = history.load_view(rid)
            if loaded:
                set_view(loaded)
                st.session_state["na_sel"] = rid
                st.rerun()
        with st.popover(" ", key=f"na_project_actions_{rid}", use_container_width=False):
            _project_actions(rid, name, active)


def _render_history() -> None:
    st.markdown("### 项目")
    with st.container(key="na_newproj"):
        if st.button("＋ 新项目", use_container_width=True):
            set_view(None)
            st.session_state.pop("na_sel", None)
            st.rerun()

    runs = history.list_runs()   # newest first, read fresh from runs/ each rerun
    if not runs:
        st.caption("暂无项目。")
        return

    active = st.session_state.get("na_sel")
    for r in runs[:_VISIBLE]:
        _project_row(r, active)

    rest = runs[_VISIBLE:]
    if rest:
        with st.expander("···", expanded=False):
            for r in rest:
                _project_row(r, active)


def _render_settings(mode: str) -> dict:
    st.markdown("### 设置")
    llm = st.selectbox(
        "LLM 供应商",
        ["deepseek", "openai", "anthropic", "qwen", "moonshot", "zhipu", "siliconflow"],
        index=0,
    )
    search = st.selectbox(
        "后端检索供应商",
        ["duckduckgo", "tavily", "perplexity", "searxng"],
        index=0,
    )
    if mode == "react":
        iters = st.number_input(
            "迭代建议预算", min_value=0, value=1, step=1,
            help="ReAct 软预算：作为 Agent 迭代次数参考，由其自主决定是否继续。0 = 建议单遍。",
        )
    else:
        iters = st.number_input(
            "迭代上限", min_value=0, value=1, step=1,
            help="固定工作流迭代上限：达到后强制最终化。0 = 单遍，不走核验循环。",
        )
    notion = st.checkbox("发布至 Notion", value=False)
    assets = st.checkbox("多资产生成", value=False,
                         help="公式 / 代码 / 图表 / 流程图")
    return {
        "llm": llm, "search": search, "iters": int(iters),
        "assets": assets, "notion": notion,
    }


def build_sidebar(mode: str = "fixed") -> dict:
    """Render the sidebar; return the collected settings dict.

    Product name + version now live in the workspace header (right side),
    so the sidebar leads straight into projects.
    """
    with st.sidebar:
        _render_history()
        st.divider()
        settings = _render_settings(mode)
    return settings
