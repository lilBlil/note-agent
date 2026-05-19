from queue import Queue
from threading import Thread

from note_agent.graph import graph
from note_agent.schemas import NoteAgentRequest, NoteAgentResponse
from note_agent.tools import set_event_handler, reset_event_handler


def run_note_agent(request: NoteAgentRequest) -> NoteAgentResponse:
    initial_state = {
        "raw_input": request.raw_input,
        "max_iterations": request.max_iterations,
        "iteration_count": 0,

        "llm_provider": request.llm_provider,
        "search_api": request.search_api,

        "note_type": "",
        "note_outline": [],
        "current_note": "",

        "search_queries": [],
        "used_search_queries": [],
        "search_results": [],
        "sources": [],

        "verification_report": "",

        "final_note": "",
        "saved_path": "",
    }

    result = graph.invoke(initial_state)

    return NoteAgentResponse(
        note_type=result["note_type"],
        final_note=result["final_note"],
        saved_path=result["saved_path"],
        sources=result["sources"],
        used_search_queries=result["used_search_queries"],
        iterations=result["iteration_count"],
    )


def stream_note_agent(request: NoteAgentRequest):
    initial_state = {
        "raw_input": request.raw_input,
        "max_iterations": request.max_iterations,
        "iteration_count": 0,

        "llm_provider": request.llm_provider,
        "search_api": request.search_api,

        "note_type": "",
        "note_outline": [],
        "current_note": "",

        "search_queries": [],
        "used_search_queries": [],
        "search_results": [],
        "sources": [],

        "verification_report": "",

        "final_note": "",
        "saved_path": "",
    }

    current_state = initial_state.copy()

    for event in graph.stream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            current_state.update(update)
            yield node_name, update, current_state

    yield "done", {}, current_state


def stream_note_agent_events(request: NoteAgentRequest):
    initial_state = {
        "raw_input": request.raw_input,
        "max_iterations": request.max_iterations,
        "iteration_count": 0,

        "llm_provider": request.llm_provider,
        "search_api": request.search_api,

        "note_type": "",
        "note_outline": [],
        "current_note": "",

        "search_queries": [],
        "used_search_queries": [],
        "search_results": [],
        "sources": [],

        "verification_report": "",

        "final_note": "",
        "saved_path": "",
    }

    q = Queue()

    def handler(event: dict):
        q.put(event)

    def run_graph():
        token = set_event_handler(handler)
        try:
            result = graph.invoke(initial_state)
            q.put({
                "type": "done",
                "state": result,
            })
        except Exception as e:
            q.put({
                "type": "error",
                "message": str(e),
            })
        finally:
            reset_event_handler(token)

    thread = Thread(target=run_graph, daemon=True)
    thread.start()

    while True:
        event = q.get()
        yield event

        if event["type"] in {"done", "error"}:
            break