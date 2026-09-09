from __future__ import annotations

from note_agent.agent import graph
from note_agent.agent import tools
from note_agent.agent.tools import ALL_TOOLS
from note_agent.domain.api import NoteAgentRequest
from note_agent.domain.models import build_base_state
from note_agent.agent.runner import build_initial_state
from note_agent.agent.runner_react import build_initial_state_react
from note_agent.services import research as research_service


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


def test_fixed_and_react_delegate_refinement_to_shared_service(base_state, monkeypatch) -> None:
    calls = []

    def fake_refine(**kwargs):
        calls.append(kwargs)
        return "# Refined", f"/tmp/{kwargs['intermediate_label']}.md"

    monkeypatch.setattr(research_service, "refine_note_content", fake_refine)
    monkeypatch.setattr(graph, "emit_node_start", lambda *args, **kwargs: None)
    base_state["current_note"] = "# Draft"
    base_state["reference_results"] = []

    fixed_result = graph.verify_and_refine(base_state)
    react_result = tools.refine_note_with_references.func(
        raw_input=base_state["raw_input"],
        current_note=base_state["current_note"],
        reference_results=[],
        iteration=base_state["iteration_count"],
        llm_provider=base_state["llm_provider"],
        run_id=base_state["run_id"],
    )

    assert fixed_result["current_note"] == "# Refined"
    assert react_result["refined_note"] == "# Refined"
    assert [call["intermediate_label"] for call in calls] == [
        "iteration_1_refined",
        "refined_iter_1",
    ]
