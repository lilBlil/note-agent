"""Bridge between the agent event stream and the RunView / render layer.

Consumes the public event stream (`stream_note_agent_events`) and folds each
event into the view, repainting the status + output placeholders live. The
workflow itself is never modified.
"""

from __future__ import annotations

import time

from note_agent.ui import render, state


def _norm_sources(items: list) -> list:
    """Order-preserving dedupe tolerant of str OR dict sources."""
    seen: set[str] = set()
    out: list = []
    for it in items or []:
        key = (it.get("url") or it.get("link") or str(sorted(it.items()))
               if isinstance(it, dict) else str(it))
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _norm_queries(items: list) -> list:
    """Order-preserving dedupe for query dicts or plain query strings."""
    seen: set[str] = set()
    out: list = []
    for it in items or []:
        if isinstance(it, dict):
            query = str(it.get("query", "")).strip()
            source_types = it.get("source_types") or []
            reason = str(it.get("reason", "")).strip()
            key = query.lower()
            value = {
                "query": query,
                "source_types": list(source_types) if isinstance(source_types, list) else [str(source_types)],
                "reason": reason,
            }
        else:
            query = str(it).strip()
            key = query.lower()
            value = {"query": query, "source_types": [], "reason": ""}
        if query and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _append_trace(view: dict, event: dict, text: str) -> None:
    if not text:
        return
    trace = view.setdefault("trace", [])
    trace.append({
        "type": event.get("type", ""),
        "node": event.get("node_name", ""),
        "text": text,
    })
    del trace[:-120]


def _current_agent_output(view: dict) -> dict | None:
    output_id = view.get("_current_output")
    if output_id is None:
        return None
    return next((item for item in view.get("agent_outputs", []) if item.get("id") == output_id), None)


def _start_agent_output(view: dict, event: dict, label: str) -> None:
    for item in view.get("agent_outputs", []):
        if item.get("status") == "running":
            item["status"] = "done"

    outputs = view.setdefault("agent_outputs", [])
    output_id = view.get("_output_seq", 0)
    view["_output_seq"] = output_id + 1
    output = {
        "id": output_id,
        "node": event.get("node_name", ""),
        "label": label,
        "status": "running",
        "messages": [f"开始：{label}"],
        "content": "",
    }
    outputs.append(output)
    view["_current_output"] = output["id"]
    del outputs[:-30]


def _append_agent_message(view: dict, text: str) -> None:
    if not text:
        return
    output = _current_agent_output(view)
    if output is None:
        output_id = view.get("_output_seq", 0)
        view["_output_seq"] = output_id + 1
        output = {
            "id": output_id,
            "node": "",
            "label": "运行状态",
            "status": "running",
            "messages": [],
            "content": "",
        }
        view["agent_outputs"].append(output)
        view["_current_output"] = output["id"]
    output.setdefault("messages", []).append(text)
    del output["messages"][:-12]


def _append_agent_content(view: dict, text: str) -> None:
    if not text:
        return
    output = _current_agent_output(view)
    if output is None:
        _append_agent_message(view, "正在生成内容")
        output = _current_agent_output(view)
    if output is not None:
        output["content"] = (output.get("content") or "") + text


def _finish_agent_outputs(view: dict, status: str) -> None:
    for item in view.get("agent_outputs", []):
        if item.get("status") == "running":
            item["status"] = status


def _persist_failed_urls(view: dict) -> None:
    failed_urls = view.get("failed_urls") or []
    run_log_dir = view.get("run_log_dir") or ""
    if not failed_urls or not run_log_dir:
        return

    from pathlib import Path

    from note_agent.io.storage import read_json, write_json

    path = Path(run_log_dir) / "final_state.json"
    if not path.exists():
        return
    try:
        data = read_json(path)
    except Exception:
        return
    data["failed_urls"] = failed_urls
    write_json(path, data)


def build_combined_input(params: dict, view: dict):
    """Assemble the agent's raw_input from text + file bytes + fetched URLs."""
    from note_agent.io.input_loader import (
        build_combined_input as _combine,
        fetch_webpage_text,
        read_uploaded_text_file,
    )

    failed_urls: list[dict[str, str]] = []
    file_texts: list[tuple[str, str]] = []
    for name, data in params.get("file_texts", []):
        file_texts.append((name, read_uploaded_text_file(name, data)))

    webpage_texts: list[tuple[str, str]] = []
    for url in params.get("urls", []):
        try:
            webpage_texts.append((url, fetch_webpage_text(url)))
        except Exception as exc:  # non-fatal: skip the bad URL, but surface it
            failed_urls.append({"url": str(url), "error": str(exc)})

    view["failed_urls"] = failed_urls
    manual_text = str(params.get("manual_text", ""))
    if failed_urls and not (manual_text.strip() or file_texts or webpage_texts):
        sample = "; ".join(
            f"{item['url']}: {item['error']}" for item in failed_urls[:3]
        )
        raise ValueError(f"网页 URL 抓取失败，且没有其他可用输入：{sample}")

    return _combine(
        manual_text=manual_text,
        file_texts=file_texts,
        webpage_texts=webpage_texts,
    )


def _fold_event(view: dict, event: dict) -> None:
    """Fold one agent event into the view (no rendering here)."""
    etype = event.get("type")
    mode = view["mode"]
    if event.get("run_id"):
        view["run_id"] = event["run_id"]

    if etype == "node_start":
        node, label = event["node_name"], event["step_label"]
        _append_trace(view, event, f"开始：{label}")
        _start_agent_output(view, event, label)
        # Update cumulative usage BEFORE sealing the previous step so its
        # token delta is attributed correctly.
        if event.get("usage"):
            view["usage"] = event["usage"]
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
        _append_agent_content(view, event.get("text", ""))

    elif etype == "progress":
        # ReAct: whole note-so-far after each state; replace (not append).
        note = event.get("note") or ""
        if note:
            view["live_text"] = note
            output = _current_agent_output(view)
            if output is not None:
                output["content"] = note
        if event.get("iteration_count") is not None:
            view["iteration"] = event["iteration_count"]

    elif etype in ("info", "warning"):
        text = event.get("text", "")
        _append_trace(view, event, text)
        _append_agent_message(view, text)
        if event.get("reference_queries") is not None:
            current = view.get("reference_queries", [])
            current.extend(_norm_queries(event.get("reference_queries") or []))
            view["reference_queries"] = _norm_queries(current)
        if event.get("failed_source"):
            view.setdefault("failed_sources", []).append(event["failed_source"])
        if event.get("failed_sources"):
            view.setdefault("failed_sources", []).extend(event["failed_sources"] or [])
        if event.get("note_type"):
            view["note_type"] = event["note_type"]
        if event.get("note_outline") is not None:
            view["note_outline"] = event["note_outline"]
        if event.get("saved_path"):
            view["saved_path"] = event["saved_path"]
        if mode == "react" and text:
            state.add_react_observe(view, text)

    elif etype == "done":
        st_ = event.get("state", {})
        view["final_note"] = st_.get("final_note", "") or view.get("final_note", "")
        view["note_type"] = st_.get("note_type", "") or view.get("note_type", "")
        view["note_outline"] = st_.get("note_outline", []) or view.get("note_outline", [])
        view["sources"] = _norm_sources(st_.get("sources", []) or [])
        queries = st_.get("reference_queries", []) or st_.get("used_reference_queries", []) or []
        view["reference_queries"] = _norm_queries(
            (view.get("reference_queries") or []) + _norm_queries(queries)
        )
        view["failed_sources"] = st_.get("failed_sources", []) or view.get("failed_sources", [])
        view["failed_urls"] = st_.get("failed_urls", []) or view.get("failed_urls", [])
        view["intermediate_paths"] = st_.get("intermediate_paths", []) or []
        view["asset_paths"] = st_.get("asset_paths", []) or []
        view["asset_errors"] = st_.get("asset_errors", []) or []
        view["saved_path"] = st_.get("saved_path", "") or view.get("saved_path", "")
        view["notion_url"] = st_.get("notion_url", "") or view.get("notion_url", "")
        view["usage"] = event.get("usage", {}) or view["usage"]
        view["run_id"] = event.get("run_id", "")
        view["run_log_dir"] = event.get("run_log_dir", "")
        view["_done_state"] = st_
        _append_trace(view, event, "运行完成")
        _append_agent_message(view, "运行完成")
        _finish_agent_outputs(view, "done")

    elif etype == "error":
        view["error"] = event.get("message") or event.get("text", "")
        _append_trace(view, event, view["error"])
        _append_agent_message(view, view["error"])
        _finish_agent_outputs(view, "error")


def _render_details(details_ph, view: dict) -> None:
    if details_ph is None:
        return
    with details_ph.container():
        render.details_panel(view)


def execute_stream(view: dict, status_ph, output_ph, details_ph=None) -> None:
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
        _render_details(details_ph, view)
        return

    if not (combined or "").strip():
        view["error"] = "没有可用的输入内容。请输入主题、粘贴文本，或添加文件与网站。"
        state.finish(view, "error")
        render.status_panel(status_ph, view)
        render.output_canvas(output_ph, view)
        _render_details(details_ph, view)
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
    _render_details(details_ph, view)

    fatal = False
    last_token_render = 0.0
    pending_token_render = False
    try:
        for event in stream_note_agent_events(request, mode=mode):
            _fold_event(view, event)
            is_token = event.get("type") == "token"
            if is_token:
                pending_token_render = True
                now = time.monotonic()
                if now - last_token_render < 0.1:
                    continue

            render.status_panel(status_ph, view)
            render.output_canvas(output_ph, view)
            if not is_token:
                _render_details(details_ph, view)
            else:
                last_token_render = time.monotonic()
                pending_token_render = False
            if event.get("type") == "error" and event.get("fatal", True):
                fatal = True
                break
    except Exception as exc:
        view["error"] = f"运行异常：{exc}"
        fatal = True

    if pending_token_render:
        render.status_panel(status_ph, view)
        render.output_canvas(output_ph, view)

    state.finish(view, "error" if (fatal or view.get("error")) else "done")
    _finish_agent_outputs(view, "error" if (fatal or view.get("error")) else "done")
    _persist_failed_urls(view)
    render.status_panel(status_ph, view)
    render.output_canvas(output_ph, view)
    _render_details(details_ph, view)
