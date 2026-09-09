"""Runtime argument resolution for ReAct tools."""

from __future__ import annotations

from typing import Any


_STATE_ARGUMENTS: dict[str, dict[str, str]] = {
    "infer_note_structure": {"raw_input": "raw_input"},
    "generate_note_draft": {
        "raw_input": "raw_input",
        "note_type": "note_type",
        "note_outline": "note_outline",
    },
    "search_references": {
        "current_note": "current_note",
        "used_queries": "used_reference_queries",
    },
    "refine_note_with_references": {
        "raw_input": "raw_input",
        "current_note": "current_note",
        "reference_results": "reference_results",
    },
    "finalize_note_content": {
        "current_note": "current_note",
        "sources": "sources",
    },
    "plan_note_assets": {
        "final_note": "final_note",
        "note_type": "note_type",
    },
    "generate_note_assets": {
        "final_note": "final_note",
        "asset_plan": "asset_plan",
    },
    "assemble_final_note": {
        "final_note": "final_note",
        "generated_assets": "generated_assets",
        "asset_paths": "asset_paths",
    },
    "save_final_note": {
        "final_note": "final_note",
        "asset_paths": "asset_paths",
        "sources": "sources",
    },
    "publish_note_to_notion": {
        "final_note": "final_note",
        "note_title": "note_title",
    },
}

_COMMON_RUNTIME_ARGUMENTS = {
    "llm_provider": "llm_provider",
    "run_id": "run_id",
}


def resolve_tool_args(
    tool_name: str,
    llm_args: dict[str, Any] | None,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Resolve model decisions with authoritative values from graph state."""
    args = dict(llm_args or {})

    for argument, state_key in _COMMON_RUNTIME_ARGUMENTS.items():
        args[argument] = state[state_key]

    if tool_name == "search_references":
        args["search_api"] = state["search_api"]

    for argument, state_key in _STATE_ARGUMENTS.get(tool_name, {}).items():
        args[argument] = state[state_key]

    if tool_name == "refine_note_with_references":
        args["iteration"] = state["iteration_count"]

    return args
