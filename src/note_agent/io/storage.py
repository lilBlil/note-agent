"""Run management, state snapshots, intermediate notes, and generic JSON I/O."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from note_agent.domain.models import RunRecord, now_iso
from note_agent.utils import to_plain_data

RUNS_DIR = Path("runs")
INTERMEDIATE_DIR = Path("notes") / "intermediate"
ASSETS_DIR = Path("notes") / "assets"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_plain_data(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def get_run_dir(run_id: str) -> Path:
    path = RUNS_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_assets_dir(run_id: str) -> Path:
    path = ASSETS_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def start_run(
    *,
    run_id: str,
    raw_input: str,
    llm_provider: str,
    search_api: str,
    max_iterations: int,
    enable_assets: bool = False,
) -> None:
    record = RunRecord(
        run_id=run_id,
        status="running",
        raw_input_preview=raw_input[:300],
        llm_provider=llm_provider,
        search_api=search_api,
        max_iterations=max_iterations,
        enable_assets=enable_assets,
    )
    write_json(get_run_dir(run_id) / "run.json", record)


def finish_run(
    *,
    run_id: str,
    status: str,
    saved_path: str = "",
    error: str = "",
) -> None:
    run_path = get_run_dir(run_id) / "run.json"
    data = read_json(run_path) if run_path.exists() else {"run_id": run_id}
    data["status"] = status
    data["saved_path"] = saved_path
    data["error"] = error
    data["updated_at"] = now_iso()
    write_json(run_path, data)


def append_event(run_id: str, event: dict[str, Any]) -> None:
    event_path = get_run_dir(run_id) / "events.jsonl"
    payload = {"created_at": now_iso(), **to_plain_data(event)}
    with event_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


_SNAPSHOT_KEYS = (
    "run_id", "note_type", "max_iterations", "enable_assets",
    "iteration_count", "llm_provider", "search_api",
    "reference_queries", "used_reference_queries", "sources",
    "saved_path", "intermediate_paths", "asset_paths", "asset_plan",
)
_SNAPSHOT_TEXT_KEYS = ("current_note", "verification_report", "final_note")
_TEXT_PREVIEW_LIMIT = 1000


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    summary = {key: to_plain_data(state.get(key)) for key in _SNAPSHOT_KEYS if key in state}
    for text_key in _SNAPSHOT_TEXT_KEYS:
        value = state.get(text_key, "")
        summary[text_key] = value[:_TEXT_PREVIEW_LIMIT] if isinstance(value, str) else value
    summary["reference_results_count"] = len(state.get("reference_results") or [])
    summary["evidence_items_count"] = len(state.get("evidence_items") or [])
    summary["generated_assets"] = to_plain_data(state.get("generated_assets") or {})
    return summary


def save_state_snapshot(run_id: str, state: dict[str, Any], name: str = "final_state") -> str:
    path = get_run_dir(run_id) / f"{name}.json"
    write_json(path, summarize_state(state))
    return str(path.resolve())


def save_intermediate_note(run_id: str, label: str, content: str) -> str:
    safe_label = "".join(ch for ch in label if ch.isalnum() or ch in {"_", "-"}).strip("_")
    safe_label = safe_label or "note"
    path = INTERMEDIATE_DIR / run_id / f"{safe_label}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")
    return str(path.resolve())
