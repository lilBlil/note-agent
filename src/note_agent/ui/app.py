"""Note Agent workspace: sidebar + main workspace, ChatGPT-style pinned input.

Orchestrates the render layer and the run loop. Presentation only — the
LangGraph workflow is consumed through its public event stream, never edited.
"""

from __future__ import annotations

import re

import streamlit as st

from note_agent.ui import render, runner_ui, theme
from note_agent.ui.sidebar import build_sidebar
from note_agent.ui.state import get_view, new_view, set_view

st.set_page_config(page_title="Note Agent", page_icon="📝", layout="wide")

_URL_RE = re.compile(r"https?://[^\s,、）)]+")


def _split_input(text: str) -> tuple[str, list[str]]:
    """Unified input: pull URLs out of pasted text; rest is the topic/text."""
    urls = _URL_RE.findall(text or "")
    remainder = _URL_RE.sub("", text or "").strip()
    return remainder, urls


def _handle_submission(submitted, mode: str, settings: dict) -> None:
    """Turn a chat_input submission into a pending RunView, then rerun."""
    if submitted is None:
        return
    # chat_input with accept_file returns a dict-like with .text and .files
    text = getattr(submitted, "text", None)
    files = getattr(submitted, "files", None)
    if text is None and files is None:  # plain string (no file support path)
        text, files = str(submitted), []
    text = text or ""
    files = files or []

    manual_text, urls = _split_input(text)
    file_texts = [(f.name, f.getvalue()) for f in files]
    file_names = [f.name for f in files]

    if not (manual_text or file_texts or urls):
        return

    view = new_view(
        mode=mode,
        task={"text": manual_text, "files": file_names, "urls": urls},
        params={"manual_text": manual_text, "file_texts": file_texts, "urls": urls},
        settings=settings,
    )
    set_view(view)
    st.rerun()


def _render_workspace(view: dict) -> None:
    """Task header + Status(25%) | Output(75%) + details, from a RunView."""
    render.task_header(view)
    col_status, col_output = st.columns([1, 3], gap="medium")
    status_ph = col_status.empty()
    output_ph = col_output.empty()

    if view["status"] == "pending" and not view.get("readonly"):
        view["status"] = "running"
        runner_ui.execute_stream(view, status_ph, output_ph)
    else:
        render.status_panel(status_ph, view)
        render.output_canvas(output_ph, view)

    render.details_panel(view)


def _render_empty_state() -> None:
    """Quiet welcome shown before the first task."""
    with st.container(height=theme.PANE_HEIGHT):
        st.markdown('<div class="na-eyebrow">工作区</div>', unsafe_allow_html=True)
        st.markdown(
            "#### 开始一次研究\n\n"
            "在下方输入主题、粘贴文本，或添加文件与网站。"
            "Agent 会分析需求、检索资料、核验并生成结构化研究笔记。\n\n"
            "左侧可切换 LLM、检索源、迭代设置与历史记录。"
        )


_MODE_LABELS = {"固定流程": "fixed", "ReAct 自主": "react"}


def _current_mode() -> str:
    """Resolve mode from the persisted selector key (before its widget runs)."""
    return _MODE_LABELS.get(st.session_state.get("mode_choice", "固定流程"), "fixed")


def _mode_selector() -> str:
    """Research-mode segmented control, sitting just above the input."""
    st.session_state.setdefault("mode_choice", "固定流程")
    choice = st.segmented_control(
        "研究模式", list(_MODE_LABELS.keys()),
        key="mode_choice", label_visibility="collapsed",
    )
    return _MODE_LABELS.get(choice, "fixed")


def main() -> None:
    theme.inject()
    mode = _current_mode()
    settings = build_sidebar(mode)

    view = get_view()
    if view:
        _render_workspace(view)
    else:
        _render_empty_state()

    # Research mode + pinned ChatGPT-style input, always visible at the bottom.
    mode = _mode_selector()
    submitted = st.chat_input(
        "输入主题、粘贴文本，或添加文件与网站…",
        accept_file="multiple",
        file_type=["txt", "md"],
    )
    _handle_submission(submitted, mode, settings)


if __name__ == "__main__":
    main()
