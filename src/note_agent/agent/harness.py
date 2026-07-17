"""Shared run harness for graph-based note agent runners."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any

from note_agent.agent.tracker import reset_usage, summarize_usage
from note_agent.domain.api import NoteAgentRequest, NoteAgentResponse
from note_agent.domain.models import new_run_id
from note_agent.io.events import reset_event_handler, set_event_handler
from note_agent.io.storage import (
    append_event,
    finish_run,
    get_run_dir,
    save_state_snapshot,
    start_run,
)

GraphFactory = Callable[[], Any]
StateFactory = Callable[[NoteAgentRequest, str], dict[str, Any]]
ProgressEventFactory = Callable[[dict[str, Any]], dict[str, Any] | None]


def build_response(result: dict[str, Any]) -> NoteAgentResponse:
    """Build the public API response from final graph state."""
    return NoteAgentResponse(
        run_id=result["run_id"],
        note_type=result.get("note_type", ""),
        final_note=result.get("final_note", ""),
        saved_path=result.get("saved_path", ""),
        notion_url=result.get("notion_url", ""),
        sources=result.get("sources", []),
        used_reference_queries=result.get("used_reference_queries", []),
        iterations=result.get("iteration_count", 0),
        intermediate_paths=result.get("intermediate_paths", []),
        asset_paths=result.get("asset_paths", []),
        run_log_dir=str(get_run_dir(result["run_id"]).resolve()),
    )


def _start_request_run(request: NoteAgentRequest, run_id: str) -> None:
    start_run(
        run_id=run_id,
        raw_input=request.raw_input,
        llm_provider=request.llm_provider,
        search_api=request.search_api,
        max_iterations=request.max_iterations,
        enable_assets=request.enable_assets,
        enable_notion=request.enable_notion,
    )


def run_agent(
    request: NoteAgentRequest,
    *,
    graph_factory: GraphFactory,
    state_factory: StateFactory,
) -> NoteAgentResponse:
    """Run a graph synchronously and handle run bookkeeping."""
    reset_usage()
    run_id = new_run_id()
    initial_state = state_factory(request, run_id)
    _start_request_run(request, run_id)

    def handler(event: dict[str, Any]) -> None:
        if event.get("type") != "token":
            append_event(run_id, event)

    token = set_event_handler(handler)

    try:
        result = graph_factory().invoke(initial_state)
        save_state_snapshot(run_id, result)
        finish_run(
            run_id=run_id,
            status="success",
            saved_path=result.get("saved_path", ""),
            notion_url=result.get("notion_url", ""),
        )
        return build_response(result)
    except Exception as e:
        finish_run(run_id=run_id, status="error", error=str(e))
        raise
    finally:
        reset_event_handler(token)


def stream_agent_events(
    request: NoteAgentRequest,
    *,
    graph_factory: GraphFactory,
    state_factory: StateFactory,
    progress_event_factory: ProgressEventFactory | None = None,
) -> Iterator[dict[str, Any]]:
    """Run a graph in a worker thread and stream UI/CLI events."""
    run_id = new_run_id()
    initial_state = state_factory(request, run_id)
    _start_request_run(request, run_id)

    q: Queue[dict[str, Any]] = Queue()
    stop = Event()

    def handler(event: dict[str, Any]) -> None:
        if stop.is_set():
            return
        if event.get("type") != "token":
            append_event(run_id, event)
        if event.get("type") == "node_start":
            event = {**event, "usage": summarize_usage()}
        q.put(event)

    def run_graph() -> None:
        reset_usage()
        token = set_event_handler(handler)
        current_state = initial_state.copy()
        try:
            for node_update in graph_factory().stream(initial_state, stream_mode="updates"):
                if stop.is_set():
                    return
                for node_state in node_update.values():
                    current_state.update(node_state)

                if progress_event_factory:
                    progress_event = progress_event_factory(current_state)
                    if progress_event:
                        q.put(progress_event)

            if stop.is_set():
                return

            save_state_snapshot(run_id, current_state)
            finish_run(
                run_id=run_id,
                status="success",
                saved_path=current_state.get("saved_path", ""),
                notion_url=current_state.get("notion_url", ""),
            )
            q.put({
                "type": "done",
                "state": current_state,
                "run_id": run_id,
                "run_log_dir": str(get_run_dir(run_id).resolve()),
                "usage": summarize_usage(),
            })
        except Exception as e:
            if not stop.is_set():
                finish_run(run_id=run_id, status="error", error=str(e))
                q.put({
                    "type": "error",
                    "message": str(e),
                    "fatal": True,
                    "run_id": run_id,
                    "run_log_dir": str(get_run_dir(run_id).resolve()),
                })
        finally:
            reset_event_handler(token)

    thread = Thread(target=run_graph, daemon=True)
    thread.start()

    try:
        while True:
            try:
                event = q.get(timeout=1.0)
            except Empty:
                if not thread.is_alive():
                    break
                continue
            yield event
            if event["type"] in {"done", "error"}:
                break
    finally:
        stop.set()
