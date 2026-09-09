from __future__ import annotations

from langchain_core.messages import AIMessage

from note_agent.agent.graph_react import create_agent_node


class _SequenceModel:
    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = iter(responses)

    def invoke(self, messages):
        return next(self.responses)


def _tool_response(name: str) -> AIMessage:
    return AIMessage(
        content=f"call {name}",
        tool_calls=[{"name": name, "args": {}, "id": f"call_{name}"}],
    )


def test_react_routes_normal_tool_call_sequence(base_state, monkeypatch) -> None:
    names = [
        "infer_note_structure",
        "generate_note_draft",
        "search_references",
        "refine_note_with_references",
        "finalize_note_content",
        "save_final_note",
    ]
    model = _SequenceModel([_tool_response(name) for name in names])
    monkeypatch.setattr(
        "note_agent.agent.graph_react._bound_tool_model",
        lambda provider: model,
    )
    monkeypatch.setattr("note_agent.agent.graph_react.emit_node_start", lambda *a, **k: None)
    monkeypatch.setattr("note_agent.agent.graph_react.emit_event", lambda *a, **k: None)

    observed = []
    state = dict(base_state)
    for name in names:
        result = create_agent_node(state)
        response = result["messages"][0]
        observed.append(response.tool_calls[0]["name"])
        state["messages"] = list(state["messages"]) + [response]

        if name == "infer_note_structure":
            state["note_type"] = "学习笔记"
        elif name == "generate_note_draft":
            state["current_note"] = "# Draft"
        elif name == "refine_note_with_references":
            state["iteration_count"] = 1
        elif name == "finalize_note_content":
            state["final_note"] = "# Final"
        elif name == "save_final_note":
            state["saved_path"] = "notes/final.md"

    assert observed == names


def test_assets_are_not_routed_when_disabled(base_state, monkeypatch) -> None:
    base_state["final_note"] = "# Final"
    base_state["enable_assets"] = False
    response = _tool_response("plan_note_assets")
    model = _SequenceModel([response])

    monkeypatch.setattr(
        "note_agent.agent.graph_react._bound_tool_model",
        lambda provider: model,
    )
    monkeypatch.setattr("note_agent.agent.graph_react.emit_node_start", lambda *a, **k: None)
    monkeypatch.setattr("note_agent.agent.graph_react.emit_event", lambda *a, **k: None)

    result = create_agent_node(base_state)

    assert result["messages"][0].tool_calls[0]["name"] == "save_final_note"


def test_notion_fallback_is_routed_when_enabled(base_state, monkeypatch) -> None:
    base_state["final_note"] = "# Final"
    base_state["saved_path"] = "notes/final.md"
    base_state["enable_notion"] = True
    model = _SequenceModel([AIMessage(content="任务完成")])
    monkeypatch.setattr(
        "note_agent.agent.graph_react._bound_tool_model",
        lambda provider: model,
    )
    monkeypatch.setattr("note_agent.agent.graph_react.emit_node_start", lambda *a, **k: None)
    monkeypatch.setattr("note_agent.agent.graph_react.emit_event", lambda *a, **k: None)

    result = create_agent_node(base_state)

    assert result["messages"][0].tool_calls[0]["name"] == "publish_note_to_notion"


def test_no_tool_call_before_save_is_diagnostic(base_state, monkeypatch) -> None:
    base_state["current_note"] = "# Draft"
    model = _SequenceModel([AIMessage(content="I am done")])
    events = []
    monkeypatch.setattr(
        "note_agent.agent.graph_react._bound_tool_model",
        lambda provider: model,
    )
    monkeypatch.setattr("note_agent.agent.graph_react.emit_node_start", lambda *a, **k: None)
    monkeypatch.setattr(
        "note_agent.agent.graph_react.emit_event",
        lambda event_type, **payload: events.append((event_type, payload)),
    )

    result = create_agent_node(base_state)

    assert result["messages"][0].tool_calls == []
    assert result["completion_reason"] == "agent_stopped_before_save"
    assert any(event_type == "warning" for event_type, _ in events)
