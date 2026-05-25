from note_agent.agent import graph as graph_module
from note_agent.agent.service import build_initial_state, build_response
from note_agent.schemas import NoteAgentRequest


def test_route_after_initial_note_respects_zero_iterations():
    assert graph_module.route_after_initial_note({"max_iterations": 0}) == "finalize"
    assert graph_module.route_after_initial_note({"max_iterations": 1}) == "continue"


def test_route_iteration_uses_refinement_count():
    assert graph_module.route_iteration({"iteration_count": 2, "max_iterations": 2}) == "finalize"
    assert graph_module.route_iteration({"iteration_count": 1, "max_iterations": 2}) == "continue"


def test_generate_reference_queries_filters_duplicates_and_invalid_types(monkeypatch):
    payload = """
{
  "reference_queries": [
    {
      "query": "Already Used",
      "source_types": ["web"],
      "reason": "duplicate"
    },
    {
      "query": "LangGraph state graph",
      "source_types": ["web", "bad_type"],
      "reason": "docs"
    },
    {
      "query": "Fallback types",
      "source_types": ["bad_type"],
      "reason": "fallback"
    }
  ]
}
"""

    monkeypatch.setattr(graph_module, "ask_llm", lambda *args, **kwargs: payload)

    result = graph_module.generate_reference_queries(
        {
            "current_note": "# Note",
            "used_reference_queries": ["already   used"],
            "llm_provider": "deepseek",
        }
    )

    assert [item["query"] for item in result["reference_queries"]] == [
        "LangGraph state graph",
        "Fallback types",
    ]
    assert result["reference_queries"][0]["source_types"] == ["web"]
    assert result["reference_queries"][1]["source_types"] == ["web", "academic"]


def test_build_initial_state_contains_v4_runtime_fields():
    request = NoteAgentRequest(
        raw_input="topic",
        max_iterations=0,
        llm_provider="deepseek",
        search_api="duckduckgo",
    )

    state = build_initial_state(request, "run_test")

    assert state["run_id"] == "run_test"
    assert state["reference_queries"] == []
    assert state["used_reference_queries"] == []
    assert state["asset_plan"] == []
    assert state["asset_paths"] == []


def test_build_response_maps_optional_lists_and_run_dir(monkeypatch, tmp_path):
    import note_agent.agent.service as service

    monkeypatch.setattr(service, "get_run_dir", lambda run_id: tmp_path / run_id)

    response = build_response(
        {
            "run_id": "run_test",
            "note_type": "Research Note",
            "final_note": "# Note",
            "saved_path": "/tmp/note.md",
            "sources": ["https://example.com"],
            "used_reference_queries": ["query"],
            "iteration_count": 1,
            "intermediate_paths": ["/tmp/intermediate.md"],
            "asset_paths": ["/tmp/chart.png"],
        }
    )

    assert response.run_id == "run_test"
    assert response.iterations == 1
    assert response.sources == ["https://example.com"]
    assert response.run_log_dir == str((tmp_path / "run_test").resolve())
