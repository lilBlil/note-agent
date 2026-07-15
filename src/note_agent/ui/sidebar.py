"""Sidebar: history (past runs) on top, all settings below.

Nothing here touches the workflow — settings are just collected into a dict
and history is read-only snapshot loading.
"""

from __future__ import annotations

import streamlit as st

from note_agent import __version__
from note_agent.ui import history
from note_agent.ui.state import set_view

_STATUS_DOT = {"success": "🟢", "error": "🔴", "running": "🟡"}


def _render_history() -> None:
    st.markdown("### 历史记录")
    if st.button("＋ 新研究", use_container_width=True):
        set_view(None)
        st.session_state.pop("_history_sel", None)
        st.rerun()

    runs = history.list_runs()
    if not runs:
        st.caption("暂无历史任务。")
        return
    with st.container(height=240):
        for r in runs:
            dot = _STATUS_DOT.get(r["status"], "⚪")
            label = (r["preview"] or r["run_id"])[:42] or r["run_id"]
            if st.button(f"{dot}  {label}", key=f"hist_{r['run_id']}",
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
    with st.expander("Notion 发布", expanded=False):
        notion = st.checkbox("发布到 Notion", value=False)
    with st.expander("高级参数", expanded=False):
        assets = st.checkbox("生成多模态资产", value=False,
                             help="公式 / 代码 / 图表 / 流程图")
    return {
        "llm": llm, "search": search, "iters": int(iters),
        "assets": assets, "notion": notion,
    }


def build_sidebar(mode: str = "fixed") -> dict:
    """Render the sidebar; return the collected settings dict."""
    with st.sidebar:
        st.markdown("## Note Agent")
        st.caption(f"AI Research Workspace · v{__version__}")
        st.divider()
        _render_history()
        st.divider()
        settings = _render_settings(mode)
    return settings
