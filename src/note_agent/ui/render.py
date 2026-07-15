"""Pure render helpers: task header, agent status, output canvas, details.

Every function draws from a RunView dict, so the same code paints live
(during streaming) and on later reruns.
"""

from __future__ import annotations

import re
import html

import streamlit as st

from note_agent.ui import theme

_MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


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


def _status_running_flag(view: dict) -> str:
    if view["status"] == "running":
        return '<span style="color:var(--na-run)">● 运行中</span>'
    if view["status"] == "error":
        return '<span style="color:var(--na-err)">● 出错</span>'
    return '<span style="color:var(--na-ok)">✓ 完成</span>'


def _render_fixed_status(view: dict) -> None:
    from note_agent.ui.state import PIPELINE

    it, mx = view["iteration"], view["max_iterations"]
    st.markdown(f"**固定流程**  ·  {_status_running_flag(view)}", unsafe_allow_html=True)
    st.caption(f"Iteration {it} / {mx}" if mx else "单遍生成（无核验循环）")

    seen = {n["node"]: n["status"] for n in view["nodes"]}
    order = [k for k, _ in PIPELINE] + [
        n["node"] for n in view["nodes"] if n["node"] not in dict(PIPELINE)
    ]
    rows = []
    for node in dict.fromkeys(order):
        label = next((n["label"] for n in view["nodes"] if n["node"] == node), None)
        from note_agent.ui.state import NODE_LABELS
        label = label or NODE_LABELS.get(node, node)
        status = seen.get(node, "pending")
        rows.append(
            f'<div class="na-step {status}"><span class="ic">{_STEP_IC[status]}</span>'
            f'<span>{html.escape(label)}</span></div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def _render_react_status(view: dict) -> None:
    st.markdown(f"**ReAct 自主**  ·  {_status_running_flag(view)}", unsafe_allow_html=True)
    st.caption(f"Iteration {view['iteration']}")
    if not view["react"]:
        st.caption("Agent 正在启动…")
        return
    for i, step in enumerate(view["react"], 1):
        blocks = [f'<div class="na-react-tag">Iteration {i}</div>']
        if step.get("think"):
            blocks.append(f'<div><span class="na-react-tag">Think</span><br>{html.escape(step["think"])}</div>')
        if step.get("act"):
            blocks.append(f'<div><span class="na-react-tag">Act</span><br>{html.escape(step["act"])}</div>')
        for obs in step.get("observe", []):
            blocks.append(f'<div><span class="na-react-tag">Observe</span><br>{html.escape(obs)}</div>')
        st.markdown(f'<div class="na-react-block">{"".join(blocks)}</div>', unsafe_allow_html=True)


def status_panel(placeholder, view: dict) -> None:
    """Repaint the fixed-height Agent Status pane. `placeholder` is st.empty()."""
    with placeholder.container(height=theme.STATUS_HEIGHT):
        st.markdown('<div class="na-eyebrow">Agent Status</div>', unsafe_allow_html=True)
        if view["mode"] == "react":
            _render_react_status(view)
        else:
            _render_fixed_status(view)


def output_canvas(placeholder, view: dict) -> None:
    """Repaint the Output canvas (Notion/ChatGPT-Canvas style, own scroll)."""
    with placeholder.container(height=theme.PANE_HEIGHT):
        st.markdown('<div class="na-eyebrow">生成内容 · Output</div>', unsafe_allow_html=True)
        note = view.get("final_note") or view.get("live_text") or ""
        if note:
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


def details_panel(view: dict) -> None:
    """Collapsed-by-default '详细信息': sources, token usage, execution trace."""
    with st.expander("详细信息", expanded=False):
        with st.container(height=300):
            tabs = st.tabs(["Sources", "Token Usage", "Execution Trace"])
            with tabs[0]:
                srcs = view.get("sources") or []
                if srcs:
                    st.markdown("\n".join(f"- {s}" for s in srcs))
                else:
                    st.caption("暂无来源。")
            with tabs[1]:
                st.markdown("\n\n".join(_usage_lines(view.get("usage") or {})))
            with tabs[2]:
                trace = view.get("trace") or []
                if trace:
                    st.markdown("\n".join(f"{i+1}. {t}" for i, t in enumerate(trace)))
                else:
                    st.caption("暂无执行记录。")
        meta = []
        if view.get("run_id"):
            meta.append(f"Run ID `{view['run_id']}`")
        if view.get("run_log_dir"):
            meta.append(f"日志 `{view['run_log_dir']}`")
        if meta:
            st.caption("  ·  ".join(meta))
