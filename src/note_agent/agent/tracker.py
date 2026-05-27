"""Per-run LLM token usage tracker backed by a ContextVar."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_usage_records: ContextVar[list[dict[str, Any]]] = ContextVar("usage_records")


def reset_usage() -> None:
    _usage_records.set([])


def record_usage(
    *,
    node_name: str = "",
    step_label: str = "",
    provider: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    try:
        records = _usage_records.get()
    except LookupError:
        records = []
        _usage_records.set(records)
    records.append({
        "node_name": node_name,
        "step_label": step_label,
        "provider": provider,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    })


def summarize_usage() -> dict[str, Any]:
    try:
        records = _usage_records.get()
    except LookupError:
        records = []

    total_input = sum(r["input_tokens"] for r in records)
    total_output = sum(r["output_tokens"] for r in records)
    total = total_input + total_output

    by_node: dict[str, dict[str, int]] = {}
    for r in records:
        key = r["node_name"] or "unknown"
        if key not in by_node:
            by_node[key] = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
        by_node[key]["input_tokens"] += r["input_tokens"]
        by_node[key]["output_tokens"] += r["output_tokens"]
        by_node[key]["calls"] += 1

    return {
        "records": records,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total,
        "by_node": by_node,
    }
