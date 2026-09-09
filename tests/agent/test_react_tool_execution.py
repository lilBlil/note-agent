from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from note_agent.agent import graph_react
from note_agent.agent.tools import ALL_TOOLS


class _CapturingToolNode:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls = []

    def invoke(self, state):
        self.calls.append(state["messages"][-1].tool_calls[0])
        call = state["messages"][-1].tool_calls[0]
        return {
            "messages": [
                ToolMessage(
                    content=json.dumps(self.result, ensure_ascii=False),
                    tool_call_id=call["id"],
                )
            ]
        }


def _state_with_call(base_state, name: str, args: dict) -> dict:
    state = dict(base_state)
    state["messages"] = [
        AIMessage(
            content="",
            tool_calls=[{"name": name, "args": args, "id": "call_1"}],
        )
    ]
    return state


def test_runtime_injects_authoritative_state(base_state, monkeypatch) -> None:
    base_state["current_note"] = "# Current"
    base_state["reference_results"] = [{"url": "https://real.example"}]
    base_state["iteration_count"] = 2
    tool_node = _CapturingToolNode({"refined_note": "# Refined"})
    monkeypatch.setattr(graph_react, "_TOOL_NODE", tool_node)
    monkeypatch.setattr(graph_react, "emit_node_start", lambda *a, **k: None)

    state = _state_with_call(
        base_state,
        "refine_note_with_references",
        {
            "raw_input": "stale input",
            "current_note": "stale note",
            "reference_results": [],
            "iteration": 99,
            "llm_provider": "wrong-provider",
            "run_id": "wrong-run",
        },
    )

    result = graph_react.create_tool_node(state)
    args = tool_node.calls[0]["args"]

    assert args["raw_input"] == base_state["raw_input"]
    assert args["current_note"] == "# Current"
    assert args["reference_results"] == [{"url": "https://real.example"}]
    assert args["iteration"] == 2
    assert args["llm_provider"] == base_state["llm_provider"]
    assert args["run_id"] == base_state["run_id"]
    assert result["current_note"] == "# Refined"
    assert result["iteration_count"] == 3


def test_tool_node_injects_state_and_hides_it_from_model_schema(base_state, monkeypatch) -> None:
    class _FakeToolModel:
        def __init__(self) -> None:
            self.responses = iter([
                AIMessage(
                    content="infer",
                    tool_calls=[{
                        "name": "infer_note_structure",
                        "args": {"raw_input": "forged model input"},
                        "id": "call_infer",
                    }],
                ),
                AIMessage(content="stop"),
            ])

        def invoke(self, messages):
            return next(self.responses)

    base_state["raw_input"] = "authoritative input"
    captured_prompts = []
    model = _FakeToolModel()
    monkeypatch.setattr(graph_react, "emit_node_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(graph_react, "emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        graph_react,
        "_bound_tool_model",
        lambda provider: model,
    )
    monkeypatch.setattr(
        "note_agent.agent.tools.ask_llm",
        lambda prompt, **kwargs: captured_prompts.append(prompt) or (
            '{"note_type": "学习笔记", "outline": []}'
        ),
    )

    result = graph_react.build_react_graph().invoke(base_state)
    schemas = {tool.name: tool.tool_call_schema.model_json_schema() for tool in ALL_TOOLS}

    assert result["note_type"] == "学习笔记"
    assert "authoritative input" in captured_prompts[0]
    assert "forged model input" not in captured_prompts[0]
    assert "raw_input" not in schemas["infer_note_structure"]["properties"]
    assert "current_note" not in schemas["refine_note_with_references"]["properties"]
    assert "reference_results" not in schemas["refine_note_with_references"]["properties"]
    assert "iteration" not in schemas["refine_note_with_references"]["properties"]


def test_tool_exception_is_emitted_and_propagated(base_state, monkeypatch) -> None:
    class _FailingToolNode:
        def invoke(self, state):
            raise RuntimeError("tool backend failed")

    events = []
    monkeypatch.setattr(graph_react, "_TOOL_NODE", _FailingToolNode())
    monkeypatch.setattr(graph_react, "emit_node_start", lambda *a, **k: None)
    monkeypatch.setattr(
        graph_react,
        "emit_event",
        lambda event_type, **payload: events.append((event_type, payload)),
    )

    state = _state_with_call(base_state, "search_references", {})
    with pytest.raises(RuntimeError, match="tool backend failed"):
        graph_react.create_tool_node(state)

    assert any(
        event_type == "error" and "tool backend failed" in payload["message"]
        for event_type, payload in events
    )
