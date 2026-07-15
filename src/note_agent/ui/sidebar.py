"""Sidebar: history (past runs) on top, all settings below.

Nothing here touches the workflow — settings are just collected into a dict
and history is read-only snapshot loading.
"""

from __future__ import annotations

import streamlit as st

from note_agent.ui import history
from note_agent.ui.state import set_view


def _render_history() -> None:
    st.markdown("### 项目")
    if st.button("＋ 新项目", use_container_width=True):
        set_view(None)
        st.session_state.pop("_history_sel", None)
        st.rerun()

    runs = history.list_runs()
    if not runs:
        st.caption("暂无项目。")
        return
    with st.container(height=300):
        for r in runs:
            label = (r["preview"] or r["run_id"]).strip()[:44] or r["run_id"]
            if st.button(label, key=f"hist_{r['run_id']}",
                         use_container_width=True):
                loaded = history.load_view(r["run_id"])
                if loaded:
                    set_view(loaded)
                    st.rerun()


def _render_settings(mode: str) -> dict:
    st.markdown("### 设置")
    llm = st.selectbox(
        "LLM 模型",
        ["deepseek", "openai", "qwen", "moonshot", "zhipu", "siliconflow"],
        index=0,
    )
    search = st.selectbox(
        "Search Provider",
        ["duckduckgo", "tavily", "perplexity", "searxng"],
        index=0,
    )
    if mode == "react":
        iters = st.number_input(
            "Iteration 预算（建议）", min_value=0, value=1, step=1,
            help="ReAct 软预算：作为建议喂给 Agent，由其自主决定是否继续。0 = 建议单遍。",
        )
    else:
        iters = st.number_input(
            "最大 Iteration", min_value=0, value=1, step=1,
            help="固定流程硬上限：达到后强制最终化。0 = 单遍，不走核验循环。",
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
