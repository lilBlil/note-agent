from queue import Queue, Empty
from threading import Thread, Event

from note_agent.agent.graph import get_graph
from note_agent.agent.tracker import reset_usage, summarize_usage
from note_agent.domain.models import new_run_id
from note_agent.domain.api import NoteAgentRequest, NoteAgentResponse
from note_agent.io.storage import (
    append_event,
    finish_run,
    get_run_dir,
    save_state_snapshot,
    start_run,
)
from note_agent.io.events import reset_event_handler, set_event_handler


def build_initial_state(request: NoteAgentRequest, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "raw_input": request.raw_input,
        "max_iterations": request.max_iterations,
        "iteration_count": 0,
        "llm_provider": request.llm_provider,
        "search_api": request.search_api,
        "enable_assets": request.enable_assets,
        "enable_notion": request.enable_notion,
        "note_type": "",
        "note_outline": [],
        "current_note": "",
        "reference_queries": [],
        "used_reference_queries": [],
        "reference_results": [],
        "evidence_items": [],
        "sources": [],
        "verification_report": "",
        "final_note": "",
        "note_title": "",
        "saved_path": "",
        "notion_url": "",
        "intermediate_paths": [],
        "asset_plan": [],
        "generated_assets": {},
        "asset_paths": [],
    }


def build_response(result: dict) -> NoteAgentResponse:
    return NoteAgentResponse(
        run_id=result["run_id"],
        note_type=result["note_type"],
        final_note=result["final_note"],
        saved_path=result["saved_path"],
        notion_url=result.get("notion_url", ""),
        sources=result.get("sources", []),
        used_reference_queries=result.get("used_reference_queries", []),
        iterations=result["iteration_count"],
        intermediate_paths=result.get("intermediate_paths", []),
        asset_paths=result.get("asset_paths", []),
        run_log_dir=str(get_run_dir(result["run_id"]).resolve()),
    )


def run_note_agent(request: NoteAgentRequest) -> NoteAgentResponse:
    reset_usage()
    run_id = new_run_id()
    initial_state = build_initial_state(request, run_id)

    start_run(
        run_id=run_id,
        raw_input=request.raw_input,
        llm_provider=request.llm_provider,
        search_api=request.search_api,
        max_iterations=request.max_iterations,
        enable_assets=request.enable_assets,
        enable_notion=request.enable_notion,
    )

    def handler(event: dict):
        if event.get("type") != "token":
            append_event(run_id, event)

    token = set_event_handler(handler)

    try:
        result = get_graph().invoke(initial_state)
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


def stream_note_agent_events(request: NoteAgentRequest):
    run_id = new_run_id()
    initial_state = build_initial_state(request, run_id)

    start_run(
        run_id=run_id,
        raw_input=request.raw_input,
        llm_provider=request.llm_provider,
        search_api=request.search_api,
        max_iterations=request.max_iterations,
        enable_assets=request.enable_assets,
        enable_notion=request.enable_notion,
    )

    q = Queue()
    stop = Event()

    def handler(event: dict):
        if stop.is_set():
            return
        if event.get("type") != "token":
            append_event(run_id, event)
        # Attach a cumulative token snapshot to structural events so the UI can
        # show live usage. record_usage() runs in this same worker thread, so
        # summarize_usage() reflects every LLM call completed so far.
        if event.get("type") == "node_start":
            event = {**event, "usage": summarize_usage()}
        q.put(event)

    def run_graph():
        reset_usage()
        token = set_event_handler(handler)
        current_state = initial_state.copy()
        try:
            # Use stream() so each node boundary is a checkpoint where we can bail out
            for node_update in get_graph().stream(initial_state, stream_mode="updates"):
                if stop.is_set():
                    return
                for node_state in node_update.values():
                    current_state.update(node_state)

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
