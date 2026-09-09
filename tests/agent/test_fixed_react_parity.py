from __future__ import annotations

from note_agent.agent.tools import ALL_TOOLS
from note_agent.domain.api import NoteAgentRequest
from note_agent.domain.models import build_base_state
from note_agent.agent.runner import build_initial_state
from note_agent.agent.runner_react import build_initial_state_react


def test_fixed_and_react_runners_share_state_shape() -> None:
    request = NoteAgentRequest(raw_input="test", max_iterations=1)
    fixed = build_initial_state(request, "run_fixed")
    react = build_initial_state_react(request, "run_react")

    assert set(fixed) == set(react)
    assert set(build_base_state(
        run_id="run_base",
        raw_input="test",
        max_iterations=1,
        llm_provider="deepseek",
        search_api="duckduckgo",
        enable_assets=False,
        enable_notion=False,
    )) == set(fixed)


def test_react_tool_registry_contains_required_control_points() -> None:
    names = {tool.name for tool in ALL_TOOLS}

    assert {
        "infer_note_structure",
        "generate_note_draft",
        "search_references",
        "refine_note_with_references",
        "finalize_note_content",
        "save_final_note",
        "publish_note_to_notion",
    }.issubset(names)
