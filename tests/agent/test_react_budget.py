from __future__ import annotations

from langchain_core.messages import AIMessage

from note_agent.agent.graph_react import create_agent_node


class _FakeToolModel:
    def __init__(self, response):
        self.response = response

    def invoke(self, messages):
        return self.response


def test_budget_blocks_search_and_refine_calls(base_state, monkeypatch) -> None:
    base_state["current_note"] = "# Draft"
    base_state["iteration_count"] = 2
    base_state["max_iterations"] = 2
    response = AIMessage(
        content="continue research",
        tool_calls=[
            {
                "name": "search_references",
                "args": {"current_note": "stale", "used_queries": []},
                "id": "call_search",
            },
            {
                "name": "refine_note_with_references",
                "args": {"current_note": "stale", "iteration": 99},
                "id": "call_refine",
            },
        ],
    )
    monkeypatch.setattr(
        "note_agent.agent.graph_react._bound_tool_model",
        lambda provider: _FakeToolModel(response),
    )
    monkeypatch.setattr("note_agent.agent.graph_react.emit_node_start", lambda *a, **k: None)
    monkeypatch.setattr("note_agent.agent.graph_react.emit_event", lambda *a, **k: None)

    result = create_agent_node(base_state)

    calls = result["messages"][0].tool_calls
    assert [call["name"] for call in calls] == ["finalize_note_content"]
    assert base_state["iteration_count"] == 2


def test_budget_finalize_call_does_not_copy_authoritative_state(base_state, monkeypatch) -> None:
    base_state["current_note"] = "# Draft"
    base_state["sources"] = ["https://source.example"]
    base_state["iteration_count"] = 1
    base_state["max_iterations"] = 1
    response = AIMessage(
        content="search again",
        tool_calls=[{
            "name": "search_references",
            "args": {"current_note": "stale"},
            "id": "call_search",
        }],
    )
    monkeypatch.setattr(
        "note_agent.agent.graph_react._bound_tool_model",
        lambda provider: _FakeToolModel(response),
    )
    monkeypatch.setattr("note_agent.agent.graph_react.emit_node_start", lambda *a, **k: None)
    monkeypatch.setattr("note_agent.agent.graph_react.emit_event", lambda *a, **k: None)

    result = create_agent_node(base_state)

    assert result["messages"][0].tool_calls[0]["args"] == {}
