"""Pure render helpers: task header, agent status, output canvas, details.

Every function draws from a RunView dict, so the same code paints live
(during streaming) and on later reruns.
"""

from __future__ import annotations

import re
import html

import streamlit as st

from note_agent import __version__
from note_agent.ui import theme

_MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
# Backend appends a "## Sources" section to the note body; we surface sources
# only in 详细信息, so strip that trailing section from the canvas + download.
_SOURCES_RE = re.compile(r"\n#{1,6}\s*(sources|参考(资料|文献)?|references)\s*\n.*$",
                         re.IGNORECASE | re.DOTALL)


def strip_sources(note: str) -> str:
    """Drop the trailing Sources/参考资料 section from a note body."""
    return _SOURCES_RE.sub("", note or "").rstrip() + "\n" if note else ""


def app_header() -> None:
    """Workspace header (right side, top): product name + version only."""
    st.markdown(
        f'<div class="na-appbar"><span class="name">Note Agent</span>'
        f'<span class="ver">v{__version__}</span></div>',
        unsafe_allow_html=True,
    )


def _mermaid(code: str, height: int = 420) -> None:
    import streamlit.components.v1 as components

    safe = code.replace("`", r"\`")
    components.html(
        f'<div class="mermaid">{safe}</div>'
        '<script type="module">'
        'import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";'
        'mermaid.initialize({ startOnLoad: true, theme: "dark", securityLevel: "loose" });'
        "</script>",
        height=height, scrolling=True,
    )


def _markdown_with_mermaid(note: str) -> None:
    """Render markdown, swapping fenced ```mermaid blocks for live diagrams."""
    parts = _MERMAID_RE.split(note)
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            if part.strip():
                st.markdown(part)
        elif part.strip():
            _mermaid(part.strip())


_MODE_LABEL = {"fixed": "固定流程", "react": "ReAct 自主"}


def task_header(view: dict) -> None:
    """The user's submitted task, preserved above the agent execution."""
    task = view.get("task", {})
    text = (task.get("text") or "").strip()
    st.markdown('<div class="na-eyebrow">用户任务</div>', unsafe_allow_html=True)
    with st.container():
        body = html.escape(text) if text else "<i>（无文本输入）</i>"
        chips = [f'<span class="na-chip">模式 · {_MODE_LABEL.get(view["mode"], view["mode"])}</span>']
        for f in task.get("files", []) or []:
            chips.append(f'<span class="na-chip">📎 {html.escape(str(f))}</span>')
        for u in task.get("urls", []) or []:
            chips.append(f'<span class="na-chip">🔗 {html.escape(str(u))}</span>')
        st.markdown(
            f'<div class="na-task-card"><div>{body}</div>'
            f'<div style="margin-top:.5rem">{"".join(chips)}</div></div>',
            unsafe_allow_html=True,
        )


_STEP_IC = {"done": "✓", "running": "●", "pending": "○"}
_STEP_WORD = {"done": "已完成 ", "running": "正在 ", "pending": ""}

# Strip decorative emoji / pictographs so labels read like a product panel,
# not a debug log. (Workflow-side labels still carry 🧭📚 etc.)
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "⬀-⯿←-⇿️✅✔✖❌✨]",
)


def _clean(s: str) -> str:
    return _EMOJI_RE.sub("", s or "").replace("  ", " ").strip(" :：·-")


def _fmt_tok(n: int) -> str:
    return f"{n/1000:.1f}K" if n >= 1000 else str(int(n))


def _run_stats(view: dict) -> tuple[float, int]:
    """(elapsed_seconds, total_tokens) for the bottom stat row."""
    import time
    total = sum((n.get("dur") or 0) for n in view.get("nodes", []))
    total += sum((s.get("dur") or 0) for s in view.get("react", []))
    if view.get("status") == "running" and view.get("_t0") is not None:
        total += max(0.0, time.monotonic() - view["_t0"])
    tok = int((view.get("usage") or {}).get("total_tokens") or 0)
    return total, tok


def _status_now(now_label: str) -> None:
    """Top block: quiet '当前状态' eyebrow + prominent '正在执行 xxx'."""
    st.markdown(
        '<div class="na-now"><div class="k">当前状态</div>'
        f'<div class="v">{html.escape(now_label)}</div></div>',
        unsafe_allow_html=True,
    )


def _status_stats(view: dict) -> None:
    """Bottom fixed block: 运行时间 + Token, plus Iteration as aux."""
    secs, tok = _run_stats(view)
    t_txt = f"{secs:.1f}s" if secs else "—"
    k_txt = _fmt_tok(tok) if tok else "—"
    st.markdown(
        '<div class="na-stats"><div><div class="k">运行时间</div>'
        f'<div class="v">{t_txt}</div></div>'
        f'<div><div class="k">Token</div><div class="v">{k_txt}</div></div></div>',
        unsafe_allow_html=True,
    )


def _render_fixed_status(view: dict) -> None:
    from note_agent.ui.state import PIPELINE, NODE_LABELS

    running = next((n["label"] for n in view["nodes"] if n["status"] == "running"), None)
    if view["status"] == "done":
        now = "已完成"
    elif view["status"] == "error":
        now = "运行出错"
    else:
        now = _clean(running) if running else "准备中"
    _status_now(now)

    st.markdown('<div class="na-eyebrow2">执行进度</div>', unsafe_allow_html=True)
    seen = {n["node"]: n["status"] for n in view["nodes"]}
    order = [k for k, _ in PIPELINE] + [
        n["node"] for n in view["nodes"] if n["node"] not in dict(PIPELINE)
    ]
    rows = []
    for node in dict.fromkeys(order):
        label = next((n["label"] for n in view["nodes"] if n["node"] == node), None)
        label = _clean(label or NODE_LABELS.get(node, node))
        status = seen.get(node, "pending")
        rows.append(
            f'<div class="na-step {status}"><span class="ic">{_STEP_IC[status]}</span>'
            f'<span>{_STEP_WORD[status]}{html.escape(label)}</span></div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)

    if view["max_iterations"]:
        st.markdown(
            f'<div class="na-aux">Iteration: {view["iteration"]} / {view["max_iterations"]}</div>',
            unsafe_allow_html=True,
        )
    _status_stats(view)


def _render_react_status(view: dict) -> None:
    steps = view["react"]
    if view["status"] == "done":
        now = "已完成"
    elif view["status"] == "error":
        now = "运行出错"
    elif not steps:
        now = "启动中"
    else:
        now = _clean(steps[-1].get("act") or steps[-1].get("think")) or "分析与决策"
    _status_now(now)

    last = steps[-1] if steps else {}
    action = _clean(last.get("act")) or "分析与决策中"
    # 最近决策: latest observation (outcome), else the reasoning phase.
    decision = ""
    for s in reversed(steps):
        if s.get("observe"):
            decision = _clean(s["observe"][-1])
            break
    decision = decision or _clean(last.get("think")) or "—"

    st.markdown(
        '<div class="na-field"><div class="k">当前动作</div>'
        f'<div class="t">{html.escape(action)}</div></div>'
        '<div class="na-field"><div class="k">最近决策</div>'
        f'<div class="t">{html.escape(decision)}</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="na-aux">Iteration: {view["iteration"]}</div>',
        unsafe_allow_html=True,
    )
    _status_stats(view)


def status_panel(placeholder, view: dict) -> None:
    """Repaint the fixed-height Agent Status pane. `placeholder` is st.empty()."""
    with placeholder.container(height=theme.STATUS_HEIGHT):
        st.markdown('<div class="na-eyebrow">Agent Status</div>', unsafe_allow_html=True)
        if view["mode"] == "react":
            _render_react_status(view)
        else:
            _render_fixed_status(view)


def output_canvas(placeholder, view: dict) -> None:
    """Repaint the Output canvas (Notion/ChatGPT-Canvas style, own scroll).

    The note body's trailing Sources section is stripped here — sources live
    only in 详细信息.
    """
    with placeholder.container(height=theme.PANE_HEIGHT):
        st.markdown('<div class="na-eyebrow">生成内容 · Output</div>', unsafe_allow_html=True)
        raw = view.get("final_note") or view.get("live_text") or ""
        note = strip_sources(raw)
        failed_urls = view.get("failed_urls") or []
        if view["status"] == "running" and view.get("agent_outputs"):
            _render_agent_outputs(view.get("agent_outputs") or [])
        elif note.strip():
            _markdown_with_mermaid(note)
        elif view["status"] == "running":
            if view["mode"] == "react":
                st.caption("Agent 自主推理中，最终笔记完成后在此呈现…")
            else:
                st.caption("生成中…")
        elif view["status"] == "error":
            st.error(view.get("error") or "运行出错")
        else:
            st.caption("研究结果将显示在这里。")
        if failed_urls:
            sample_items = []
            for item in failed_urls[:3]:
                if isinstance(item, dict):
                    sample_items.append(str(item.get("url") or item.get("link") or ""))
                else:
                    sample_items.append(str(item))
            sample = "、".join(sample_items)
            tail = "..." if len(failed_urls) > 3 else ""
            st.warning(f"部分 URL 抓取失败，已跳过 {len(failed_urls)} 个：{sample}{tail}")


def _usage_lines(usage: dict) -> list[str]:
    total = usage.get("total_tokens") or 0
    if total <= 0:
        return ["_暂无统计_"]
    lines = [
        f"**总计：** {usage['total_tokens']:,} tokens "
        f"（输入 {usage['total_input_tokens']:,} · 输出 {usage['total_output_tokens']:,}）"
    ]
    by_node = usage.get("by_node") or {}
    if by_node:
        rows = [
            f"| `{k}` | {v['calls']} | {v['input_tokens']:,} | {v['output_tokens']:,} | "
            f"{v['input_tokens'] + v['output_tokens']:,} |"
            for k, v in by_node.items()
        ]
        lines.append(
            "| 节点 | 调用 | 输入 | 输出 | 合计 |\n|---|---|---|---|---|\n" + "\n".join(rows)
        )
    return lines


def _note_filename(view: dict) -> str:
    saved = (view.get("_done_state") or {}).get("saved_path") or ""
    if saved:
        name = saved.replace("\\", "/").rsplit("/", 1)[-1]
        if name:
            return name
    base = view.get("run_id") or "note"
    return f"{base}.md"


def download_bar(view: dict) -> None:
    """A single compact download link for the finished note (no Sources tail)."""
    note = strip_sources(view.get("final_note") or "")
    if view.get("status") != "done" or not note.strip():
        return
    st.download_button(
        "⬇ 下载 Markdown",
        data=note.encode("utf-8"),
        file_name=_note_filename(view),
        mime="text/markdown",
        use_container_width=False,
        key=f"dl_{view.get('run_id') or 'note'}",
    )


def _render_trace(trace: list[dict]) -> None:
    if not trace:
        st.caption("暂无活动记录。")
        return
    rows = []
    for item in trace[-80:]:
        kind = item.get("type", "")
        node = item.get("node", "")
        text = _clean(str(item.get("text", "")))
        prefix = f"`{html.escape(node)}` " if node else ""
        rows.append(f"- **{html.escape(kind)}** {prefix}{html.escape(text)}")
    st.markdown("\n".join(rows))


def _render_queries(queries: list) -> None:
    if not queries:
        st.caption("暂无生成的检索查询。")
        return
    rows = []
    for q in queries:
        if isinstance(q, dict):
            query = str(q.get("query", ""))
            source_types = ", ".join(q.get("source_types", []) or [])
            reason = str(q.get("reason", ""))
        else:
            query, source_types, reason = str(q), "", ""
        suffix = f" `{html.escape(source_types)}`" if source_types else ""
        line = f"- {html.escape(query)}{suffix}"
        if reason:
            line += f"\n  \n  {html.escape(reason)}"
        rows.append(line)
    st.markdown("\n".join(rows))


def _source_text(source) -> str:
    if isinstance(source, dict):
        title = str(source.get("title") or source.get("name") or source.get("url") or source)
        url = str(source.get("url") or source.get("link") or source.get("href") or "")
        return f"[{title}]({url})" if url else title
    text = str(source)
    return f"<{text}>" if text.startswith(("http://", "https://")) else html.escape(text)


def _render_sources(sources: list) -> None:
    if not sources:
        st.caption("暂无来源。")
        return
    st.markdown("\n".join(f"- {_source_text(s)}" for s in sources))


def _latest_trace_match(view: dict, needles: tuple[str, ...]) -> str:
    for item in reversed(view.get("trace") or []):
        text = str(item.get("text", ""))
        if any(needle in text for needle in needles):
            return text
    return ""


def _render_retrieval_resources(view: dict) -> None:
    search_api = (view.get("settings") or {}).get("search", "") or "duckduckgo"
    queries = view.get("reference_queries") or []
    sources = view.get("sources") or []
    failures = view.get("failed_sources") or []
    failed_urls = view.get("failed_urls") or []
    summary = _latest_trace_match(view, ("Retrieval summary:", "Web backend ", "检索失败："))

    st.markdown(f"**检索后端**: `{html.escape(str(search_api))}`")
    if summary:
        st.caption(summary)
    st.markdown("**检索查询**")
    _render_queries(queries)
    st.markdown("**来源链接**")
    _render_sources(sources)
    if failures:
        st.markdown("**失败源**")
        _render_failures(failures)
    if failed_urls:
        st.markdown("**输入 URL 失败**")
        _render_failed_urls(failed_urls)


def _render_agent_outputs(outputs: list[dict]) -> None:
    if not outputs:
        st.caption("等待 Agent 输出…")
        return

    current = next((item for item in reversed(outputs) if item.get("status") == "running"), None)
    current = current or outputs[-1]
    recent = [item for item in outputs[-6:] if item is not current]
    visible = [current] + recent
    for idx, item in enumerate(visible):
        label = _clean(str(item.get("label", "") or item.get("node", "") or "Agent"))
        status = item.get("status", "")
        status_text = {"running": "进行中", "done": "已完成", "error": "出错"}.get(status, status)
        st.markdown(f"#### {html.escape(label)} · {html.escape(status_text)}")

        content = strip_sources(item.get("content") or "")
        if content.strip():
            preview = content if item.get("status") == "running" else content[:1600]
            _markdown_with_mermaid(preview)

        messages = [_clean(str(m)) for m in item.get("messages", []) if _clean(str(m))]
        if messages:
            st.markdown("\n".join(f"- {html.escape(m)}" for m in messages[-6:]))
        elif not content.strip():
            st.caption("正在等待该阶段返回结果…")

        if idx != len(visible) - 1:
            st.divider()


def _render_failures(failures: list[dict]) -> None:
    if not failures:
        st.caption("暂无失败源。")
        return
    rows = []
    for f in failures:
        query = str(f.get("query", ""))
        source = str(f.get("source_name", "") or f.get("source_type", ""))
        error = str(f.get("error", ""))
        rows.append(
            f"- **{html.escape(source)}** {html.escape(query)}\n  \n  {html.escape(error)}"
        )
    st.markdown("\n".join(rows))


def _render_failed_urls(failed_urls: list[dict]) -> None:
    if not failed_urls:
        return
    rows = []
    for item in failed_urls:
        if isinstance(item, dict):
            url = str(item.get("url") or item.get("link") or "")
            error = str(item.get("error") or "")
        else:
            url = str(item)
            error = ""
        line = f"- `{html.escape(url)}`"
        if error:
            line += f"\n  \n  {html.escape(error)}"
        rows.append(line)
    st.markdown("\n".join(rows))


def _render_artifacts(view: dict) -> None:
    items = []
    done_state = view.get("_done_state") or {}
    saved = view.get("saved_path") or done_state.get("saved_path") or ""
    if saved:
        items.append(f"- **最终 Markdown**: `{saved}`")
    for path in view.get("intermediate_paths") or []:
        items.append(f"- **中间稿**: `{path}`")
    for path in view.get("asset_paths") or []:
        items.append(f"- **资产**: `{path}`")
    notion_url = view.get("notion_url") or done_state.get("notion_url") or ""
    if notion_url:
        items.append(f"- **Notion**: {notion_url}")
    if items:
        st.markdown("\n".join(items))
    else:
        st.caption("暂无产物记录。")

    errors = view.get("asset_errors") or []
    if errors:
        st.markdown("**资产错误**")
        st.json(errors, expanded=False)


def details_panel(view: dict) -> None:
    """Collapsed-by-default panel for retrieval resources and token usage."""
    with st.expander("详细信息", expanded=False):
        with st.container(height=320):
            tabs = st.tabs(["检索资源", "Token 用量"])
            with tabs[0]:
                _render_retrieval_resources(view)
            with tabs[1]:
                st.markdown("\n\n".join(_usage_lines(view.get("usage") or {})))
