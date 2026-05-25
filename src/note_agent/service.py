from queue import Queue
from threading import Thread

from note_agent.graph import graph
from note_agent.schemas import NoteAgentRequest, NoteAgentResponse, new_run_id
from note_agent.storage import (
    append_event,
    finish_run,
    get_run_dir,
    save_state_snapshot,
    start_run,
)
from note_agent.utils.events import reset_event_handler, set_event_handler


def build_initial_state(request: NoteAgentRequest, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "raw_input": request.raw_input,
        "max_iterations": request.max_iterations,
        "iteration_count": 0,
        "llm_provider": request.llm_provider,
        "search_api": request.search_api,
        "enable_assets": request.enable_assets,
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
        "saved_path": "",
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
        sources=result.get("sources", []),
        used_reference_queries=result.get("used_reference_queries", []),
        iterations=result["iteration_count"],
        intermediate_paths=result.get("intermediate_paths", []),
        asset_paths=result.get("asset_paths", []),
        run_log_dir=str(get_run_dir(result["run_id"]).resolve()),
    )


def run_note_agent(request: NoteAgentRequest) -> NoteAgentResponse:
    run_id = new_run_id()
    initial_state = build_initial_state(request, run_id)

    start_run(
        run_id=run_id,
        raw_input=request.raw_input,
        llm_provider=request.llm_provider,
        search_api=request.search_api,
        max_iterations=request.max_iterations,
        enable_assets=request.enable_assets,
    )

    def handler(event: dict):
        if event.get("type") != "token":
            append_event(run_id, event)

    token = set_event_handler(handler)

    try:
        result = graph.invoke(initial_state)
        save_state_snapshot(run_id, result)
        finish_run(
            run_id=run_id,
            status="success",
            saved_path=result.get("saved_path", ""),
        )
        return build_response(result)
    except Exception as e:
        finish_run(run_id=run_id, status="error", error=str(e))
        raise
    finally:
        reset_event_handler(token)


def stream_note_agent(request: NoteAgentRequest):
    run_id = new_run_id()
    initial_state = build_initial_state(request, run_id)

    start_run(
        run_id=run_id,
        raw_input=request.raw_input,
        llm_provider=request.llm_provider,
        search_api=request.search_api,
        max_iterations=request.max_iterations,
        enable_assets=request.enable_assets,
    )

    current_state = initial_state.copy()

    try:
        for event in graph.stream(initial_state, stream_mode="updates"):
            for node_name, update in event.items():
                current_state.update(update)
                append_event(
                    run_id,
                    {
                        "type": "node_update",
                        "node_name": node_name,
                        "update_keys": list(update.keys()),
                    },
                )
                yield node_name, update, current_state

        save_state_snapshot(run_id, current_state)
        finish_run(
            run_id=run_id,
            status="success",
            saved_path=current_state.get("saved_path", ""),
        )
        yield "done", {}, current_state
    except Exception as e:
        finish_run(run_id=run_id, status="error", error=str(e))
        raise


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
    )

    q = Queue()

    def handler(event: dict):
        q.put(event)
        if event.get("type") != "token":
            append_event(run_id, event)

    def run_graph():
        token = set_event_handler(handler)
        try:
            result = graph.invoke(initial_state)
            save_state_snapshot(run_id, result)
            finish_run(
                run_id=run_id,
                status="success",
                saved_path=result.get("saved_path", ""),
            )
            q.put(
                {
                    "type": "done",
                    "state": result,
                    "run_id": run_id,
                    "run_log_dir": str(get_run_dir(run_id).resolve()),
                }
            )
        except Exception as e:
            finish_run(run_id=run_id, status="error", error=str(e))
            q.put(
                {
                    "type": "error",
                    "message": str(e),
                    "run_id": run_id,
                    "run_log_dir": str(get_run_dir(run_id).resolve()),
                }
            )
        finally:
            reset_event_handler(token)

    thread = Thread(target=run_graph, daemon=True)
    thread.start()

    while True:
        event = q.get()
        yield event

        if event["type"] in {"done", "error"}:
            break
