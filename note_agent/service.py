from note_agent.graph import graph
from note_agent.schemas import NoteAgentRequest, NoteAgentResponse


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