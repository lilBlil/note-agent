"""ReAct-based runner for note agent."""

from typing import Any

from langchain_core.messages import HumanMessage

from note_agent.agent.graph_react import get_react_graph
from note_agent.agent.harness import run_agent, stream_agent_events
from note_agent.domain.api import NoteAgentRequest, NoteAgentResponse
from note_agent.domain.models import build_base_state


def build_initial_state_react(request: NoteAgentRequest, run_id: str) -> dict:
    """Build initial state for ReAct agent."""
    return build_base_state(
        run_id=run_id,
        raw_input=request.raw_input,
        max_iterations=request.max_iterations,
        llm_provider=request.llm_provider,
        search_api=request.search_api,
        enable_assets=request.enable_assets,
        enable_notion=request.enable_notion,
        messages=[
            HumanMessage(
                content=(
                    "\u8bf7\u4e3a\u4ee5\u4e0b\u5185\u5bb9\u751f\u6210"
                    "\u9ad8\u8d28\u91cf\u7814\u7a76\u7b14\u8bb0\uff1a\n\n"
                    f"{request.raw_input}"
                )
            )
        ],
    )


def _react_progress_event(state: dict[str, Any]) -> dict[str, Any]:
    note_so_far = state.get("final_note") or state.get("current_note") or ""
    return {
        "type": "progress",
        "note": note_so_far,
        "iteration_count": state.get("iteration_count", 0),
    }


def run_note_agent_react(request: NoteAgentRequest) -> NoteAgentResponse:
    """Run note agent with ReAct architecture (blocking)."""
    return run_agent(
        request,
        graph_factory=get_react_graph,
        state_factory=build_initial_state_react,
    )


def stream_note_agent_events_react(request: NoteAgentRequest):
    """Stream note agent events with ReAct architecture."""
    yield from stream_agent_events(
        request,
        graph_factory=get_react_graph,
        state_factory=build_initial_state_react,
        progress_event_factory=_react_progress_event,
    )
