"""Fixed-workflow runner for note agent."""

from note_agent.agent.graph import get_graph
from note_agent.agent.harness import run_agent, stream_agent_events
from note_agent.domain.api import NoteAgentRequest, NoteAgentResponse
from note_agent.domain.models import build_base_state


def build_initial_state(request: NoteAgentRequest, run_id: str) -> dict:
    return build_base_state(
        run_id=run_id,
        raw_input=request.raw_input,
        max_iterations=request.max_iterations,
        llm_provider=request.llm_provider,
        search_api=request.search_api,
        enable_assets=request.enable_assets,
        enable_notion=request.enable_notion,
    )


def run_note_agent(request: NoteAgentRequest) -> NoteAgentResponse:
    return run_agent(
        request,
        graph_factory=get_graph,
        state_factory=build_initial_state,
    )


def stream_note_agent_events(request: NoteAgentRequest):
    yield from stream_agent_events(
        request,
        graph_factory=get_graph,
        state_factory=build_initial_state,
    )
