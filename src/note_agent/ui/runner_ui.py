"""Bridge between the agent event stream and the RunView / render layer.

Consumes the public event stream (`stream_note_agent_events`) and folds each
event into the view, repainting the status + output placeholders live. The
workflow itself is never modified.
"""

from __future__ import annotations

from note_agent.ui import render, state


def build_combined_input(params: dict, view: dict):
    """Assemble the agent's raw_input from text + file bytes + fetched URLs."""
    from note_agent.io.input_loader import (
        build_combined_input as _combine,
        fetch_webpage_text,
        read_uploaded_text_file,
    )

    file_texts: list[tuple[str, str]] = []
    for name, data in params.get("file_texts", []):
        file_texts.append((name, read_uploaded_text_file(name, data)))

    webpage_texts: list[tuple[str, str]] = []
    for url in params.get("urls", []):
        try:
            webpage_texts.append((url, fetch_webpage_text(url)))
            view["trace"].append(f"抓取网页：{url}")
        except Exception as exc:  # non-fatal: skip the bad URL
            view["trace"].append(f"抓取失败 {url}：{exc}")

    return _combine(
        manual_text=params.get("manual_text", ""),
        file_texts=file_texts,
        webpage_texts=webpage_texts,
    )


def _fold_event(view: dict, event: dict) -> None:
    """Fold one agent event into the view (no rendering here)."""
    etype = event.get("type")
    mode = view["mode"]

    if etype == "node_start":
        node, label = event["node_name"], event["step_label"]
        if event.get("usage"):
            view["usage"] = event["usage"]
        view["trace"].append(label)
        if mode == "react":
            if node == "agent":
                state.start_react_step(view, label)
            else:
                state.set_react_act(view, label)
        else:
            state.start_stage(view, node, label)

    elif etype == "token":
        # Fixed mode streams draft/finalize tokens; show them live.
        view["live_text"] += event.get("text", "")

    elif etype in ("info", "warning"):
        text = event.get("text", "")
        if mode == "react" and text:
            state.add_react_observe(view, text)
        if text:
            view["trace"].append(("⚠ " if etype == "warning" else "") + text)

    elif etype == "done":
        st_ = event.get("state", {})
        view["final_note"] = st_.get("final_note", "") or view.get("final_note", "")
        view["sources"] = sorted(set(st_.get("sources", []) or []))
        view["usage"] = event.get("usage", {}) or view["usage"]
        view["run_id"] = event.get("run_id", "")
        view["run_log_dir"] = event.get("run_log_dir", "")
        view["_done_state"] = st_

    elif etype == "error":
        view["error"] = event.get("message") or event.get("text", "")


def execute_stream(view: dict, status_ph, output_ph) -> None:
    """Run the agent and repaint status/output placeholders as events arrive."""
    from note_agent.domain.api import NoteAgentRequest
    from note_agent.agent.runner_unified import stream_note_agent_events

    mode = view["mode"]
    settings = view["settings"]

    # Warm the graph for the chosen mode before streaming.
    if mode == "react":
        from note_agent.agent.graph_react import get_react_graph
        get_react_graph()
    else:
        from note_agent.agent.graph import get_graph
        get_graph()

    try:
        combined = build_combined_input(view["params"], view)
    except Exception as exc:
        view["error"] = f"输入处理失败：{exc}"
        state.finish(view, "error")
        render.status_panel(status_ph, view)
        render.output_canvas(output_ph, view)
        return

    if not (combined or "").strip():
        view["error"] = "没有可用的输入内容。请输入主题、粘贴文本，或添加文件与网站。"
        state.finish(view, "error")
        render.status_panel(status_ph, view)
        render.output_canvas(output_ph, view)
        return

    request = NoteAgentRequest(
        raw_input=combined,
        max_iterations=settings["iters"],
        llm_provider=settings["llm"],
        search_api=settings["search"],
        enable_assets=settings["assets"],
        enable_notion=settings["notion"],
    )

    render.status_panel(status_ph, view)
    render.output_canvas(output_ph, view)

    fatal = False
    try:
        for event in stream_note_agent_events(request, mode=mode):
            _fold_event(view, event)
            render.status_panel(status_ph, view)
            render.output_canvas(output_ph, view)
            if event.get("type") == "error" and event.get("fatal", True):
                fatal = True
                break
    except Exception as exc:
        view["error"] = f"运行异常：{exc}"
        fatal = True

    state.finish(view, "error" if (fatal or view.get("error")) else "done")
    render.status_panel(status_ph, view)
    render.output_canvas(output_ph, view)
