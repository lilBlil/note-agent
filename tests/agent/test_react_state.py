from __future__ import annotations

import json

from langchain_core.messages import AIMessage, ToolMessage

from note_agent.agent import graph_react


class _ResultToolNode:
    def __init__(self, result: dict) -> None:
        self.result = result

    def invoke(self, state):
        call = state["messages"][-1].tool_calls[0]
        return {
            "messages": [
                ToolMessage(
                    content=json.dumps(self.result, ensure_ascii=False),
                    tool_call_id=call["id"],
                )
            ]
        }


def _call_state(base_state, name: str, call_id: str) -> dict:
    state = dict(base_state)
    state["messages"] = [
        AIMessage(
            content="",
            tool_calls=[{"name": name, "args": {}, "id": call_id}],
        )
    ]
    return state


def test_state_merge_deduplicates_research_metadata(base_state, monkeypatch) -> None:
    result = {
        "reference_results": [{"query": "q1", "url": "https://source.example"}],
        "new_queries": ["q1"],
        "sources": ["https://source.example", "https://source.example"],
        "failed_sources": [{"query": "q1", "error": "timeout"}],
        "intermediate_path": "/tmp/iteration.md",
    }
    monkeypatch.setattr(graph_react, "_TOOL_NODE", _ResultToolNode(result))
    monkeypatch.setattr(graph_react, "emit_node_start", lambda *a, **k: None)

    state = _call_state(base_state, "search_references", "call_1")
    first = graph_react.create_tool_node(state)
    state.update(first)
    state = _call_state(state, "search_references", "call_2")
    second = graph_react.create_tool_node(state)

    assert second["sources"] == ["https://source.example"]
    assert second["used_reference_queries"] == ["q1"]
    assert len(second["failed_sources"]) == 1
    assert second["intermediate_paths"] == ["/tmp/iteration.md"]
    assert len(second["evidence_items"]) == 1


def test_normal_tool_results_update_required_state_fields(base_state, monkeypatch) -> None:
    tool_results = [
        ("infer_note_structure", {"note_type": "学习笔记", "note_outline": [{"title": "概述"}]}),
        ("generate_note_draft", {"current_note": "# Draft"}),
        (
            "search_references",
            {
                "reference_results": [{"query": "q1", "url": "https://source.example"}],
                "new_queries": ["q1"],
                "sources": ["https://source.example"],
            },
        ),
        ("refine_note_with_references", {"refined_note": "# Refined"}),
        ("finalize_note_content", {"final_note": "# Final"}),
        ("save_final_note", {"saved_path": "notes/final.md"}),
    ]
    monkeypatch.setattr(graph_react, "emit_node_start", lambda *args, **kwargs: None)

    state = dict(base_state)
    for index, (tool_name, result) in enumerate(tool_results):
        monkeypatch.setattr(graph_react, "_TOOL_NODE", _ResultToolNode(result))
        update = graph_react.create_tool_node(
            _call_state(state, tool_name, f"call_{index}")
        )
        state.update(update)

    assert state["note_type"] == "学习笔记"
    assert state["current_note"] == "# Refined"
    assert state["reference_results"] == [{"query": "q1", "url": "https://source.example"}]
    assert state["iteration_count"] == 1
    assert state["final_note"] == "# Final"
    assert state["saved_path"] == "notes/final.md"
