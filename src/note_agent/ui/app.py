"""Note Agent workspace: sidebar + main workspace, ChatGPT-style pinned input.

Orchestrates the render layer and the run loop. Presentation only — the
LangGraph workflow is consumed through its public event stream, never edited.
"""

from __future__ import annotations

import re

import streamlit as st

from note_agent.ui import render, runner_ui, theme
from note_agent.ui import history
from note_agent.ui.sidebar import build_sidebar
from note_agent.ui.state import get_view, new_view, set_view

st.set_page_config(page_title="Note Agent", page_icon="📝", layout="wide")

_URL_RE = re.compile(r"https?://[^\s,、）)]+")


def _split_input(text: str) -> tuple[str, list[str]]:
    """Unified input: pull URLs out of pasted text; rest is the topic/text."""
    urls = _URL_RE.findall(text or "")
    remainder = _URL_RE.sub("", text or "").strip()
    return remainder, urls


def _build_and_set_view(text: str, files: list, mode: str, settings: dict) -> bool:
    """Build a pending RunView from composer input. Returns True if submitted."""
    text = text or ""
    files = files or []

    manual_text, urls = _split_input(text)
    file_texts = [(f.name, f.getvalue()) for f in files]
    file_names = [f.name for f in files]

    if not (manual_text or file_texts or urls):
        return False

    view = new_view(
        mode=mode,
        task={"text": manual_text, "files": file_names, "urls": urls},
        params={"manual_text": manual_text, "file_texts": file_texts, "urls": urls},
        settings=settings,
    )
    set_view(view)
    return True


def _render_workspace_static(view: dict) -> None:
    """Task header + Status(25%) | Output(75%) + download + details."""
    render.task_header(view)
    col_status, col_output = st.columns([1, 3], gap="medium")
    status_ph = col_status.empty()
    output_ph = col_output.empty()
    dl_col, _ = st.columns([1, 3])
    details_ph = st.empty()

    if view["status"] == "pending" and not view.get("readonly"):
        view["status"] = "running"
        with dl_col:
            render.download_bar(view)
        runner_ui.execute_stream(view, status_ph, output_ph, details_ph)
    else:
        render.status_panel(status_ph, view)
        render.output_canvas(output_ph, view)
        with dl_col:
            render.download_bar(view)
        with details_ph.container():
            render.details_panel(view)


def _render_workspace(view: dict) -> None:
    if view["status"] == "running" and view.get("run_id"):
        @st.fragment(run_every=2)
        def _running_workspace() -> None:
            latest = history.load_view(view["run_id"]) or view
            if latest.get("status") == "running":
                _render_workspace_static(latest)
            else:
                set_view(latest)
                st.rerun()

        _running_workspace()
        return

    _render_workspace_static(view)


def _render_empty_state() -> None:
    """Quiet welcome shown before the first task."""
    with st.container(height=theme.PANE_HEIGHT):
        st.markdown('<div class="na-eyebrow">工作区</div>', unsafe_allow_html=True)
        st.markdown(
            "#### 开始一次研究\n\n"
            "在下方输入主题、粘贴文本，或添加文件与网站。"
            "Agent 会分析需求、检索资料、核验并生成结构化研究笔记。\n\n"
            "左侧可切换 LLM、检索源、迭代设置与项目历史。"
        )


_MODE_LABELS = {"固定流程": "fixed", "ReAct 自主": "react"}


def _current_mode() -> str:
    """Resolve mode from the persisted selector key (before its widget runs)."""
    return _MODE_LABELS.get(st.session_state.get("na_mode_sel", "固定流程"), "fixed")


def _composer(settings: dict) -> None:
    """ChatGPT-style single-row pill: [+] upload · text · mode dropdown · [↑] send."""
    with st.container(key="na_composer"):
        with st.form(
            "na_composer_form",
            clear_on_submit=False,
            enter_to_submit=True,
            border=False,
        ):
            c_up, c_text, c_mode, c_send = st.columns(
                [1, 11, 3, 1], vertical_alignment="center")
            with c_up:
                with st.container(key="na_up"):
                    with st.popover("＋"):
                        st.file_uploader(
                            "添加文件（.txt / .md）", type=["txt", "md"],
                            accept_multiple_files=True, key="na_files",
                            label_visibility="collapsed",
                        )
                        st.caption("网站链接：直接粘贴到输入框，将自动识别。")
            with c_text:
                text = st.text_input(
                    "输入", key="na_text", label_visibility="collapsed",
                    placeholder="输入主题、粘贴文本，或添加文件与网站…",
                )
            with c_mode:
                with st.container(key="na_mode"):
                    st.session_state.setdefault("na_mode_sel", "固定流程")
                    st.selectbox(
                        "研究模式", list(_MODE_LABELS.keys()),
                        key="na_mode_sel", label_visibility="collapsed",
                    )
            with c_send:
                with st.container(key="na_send"):
                    send = st.form_submit_button("↑", help="开始研究")

    if send:
        mode = _MODE_LABELS.get(st.session_state.get("na_mode_sel", "固定流程"), "fixed")
        if _build_and_set_view(text, st.session_state.get("na_files") or [],
                               mode, settings):
            st.rerun()


def main() -> None:
    theme.inject()
    render.app_header()
    settings = build_sidebar(_current_mode())

    view = get_view()
    if view:
        _render_workspace(view)
    else:
        _render_empty_state()

    _composer(settings)


if __name__ == "__main__":
    main()
