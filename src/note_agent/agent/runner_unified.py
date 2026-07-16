"""Unified runner that supports both fixed workflow and ReAct mode."""

from note_agent.domain.api import NoteAgentRequest, NoteAgentResponse


def run_note_agent(request: NoteAgentRequest, mode: str = "fixed") -> NoteAgentResponse:
    """
    Run note agent with specified mode.

    Args:
        request: Note agent request
        mode: "fixed" for original fixed workflow, "react" for ReAct agent

    Returns:
        Note agent response
    """
    if mode == "react":
        from note_agent.agent.runner_react import run_note_agent_react
        return run_note_agent_react(request)
    else:
        from note_agent.agent.runner import run_note_agent as run_fixed
        return run_fixed(request)


def stream_note_agent_events(request: NoteAgentRequest, mode: str = "fixed"):
    """
    Stream note agent events with specified mode.

    Args:
        request: Note agent request
        mode: "fixed" for original fixed workflow, "react" for ReAct agent

    Yields:
        Event dicts
    """
    if mode == "react":
        from note_agent.agent.runner_react import stream_note_agent_events_react
        yield from stream_note_agent_events_react(request)
    else:
        from note_agent.agent.runner import stream_note_agent_events as stream_events_fixed
        yield from stream_events_fixed(request)
