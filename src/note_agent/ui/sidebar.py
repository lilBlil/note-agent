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


def _project_row(r: dict, active: str | None) -> None:
    rid = r["run_id"]
    label = (r["preview"] or rid).strip()[:44] or rid
    # Selected row: wrap in a keyed container so CSS keeps it highlighted.
    key_wrap = "na_active" if rid == active else f"na_row_{rid}"
    with st.container(key=key_wrap):
        if st.button(label, key=f"hist_{rid}", use_container_width=True):
            loaded = history.load_view(rid)
            if loaded:
                set_view(loaded)
                st.session_state["na_sel"] = rid
                st.rerun()


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
        ["deepseek", "openai", "qwen", "moonshot", "zhipu", "siliconflow"],
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
