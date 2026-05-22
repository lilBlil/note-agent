from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from note_agent.models import RunRecord, SearchResultItem, now_iso


RUNS_DIR = Path("runs")
CACHE_DIR = Path(".cache") / "search"
INTERMEDIATE_DIR = Path("notes") / "intermediate"

for directory in (RUNS_DIR, CACHE_DIR, INTERMEDIATE_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def _to_plain_data(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_to_plain_data(item) for item in value]
    if isinstance(value, tuple):
        return [_to_plain_data(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    return value


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_plain_data(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def get_run_dir(run_id: str) -> Path:
    path = RUNS_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def start_run(
    *,
    run_id: str,
    raw_input: str,
    llm_provider: str,
    search_api: str,
    max_iterations: int,
) -> None:
    record = RunRecord(
        run_id=run_id,
        status="running",
        raw_input_preview=raw_input[:300],
        llm_provider=llm_provider,
        search_api=search_api,
        max_iterations=max_iterations,
    )
    _write_json(get_run_dir(run_id) / "run.json", record)


def finish_run(
    *,
    run_id: str,
    status: str,
    saved_path: str = "",
    error: str = "",
) -> None:
    run_path = get_run_dir(run_id) / "run.json"
    data = _read_json(run_path) if run_path.exists() else {"run_id": run_id}

    data["status"] = status
    data["saved_path"] = saved_path
    data["error"] = error
    data["updated_at"] = now_iso()

    _write_json(run_path, data)


def append_event(run_id: str, event: dict[str, Any]) -> None:
    event_path = get_run_dir(run_id) / "events.jsonl"
    payload = {
        "created_at": now_iso(),
        **_to_plain_data(event),
    }
    with event_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "run_id",
        "note_type",
        "max_iterations",
        "iteration_count",
        "llm_provider",
        "search_api",
        "search_queries",
        "used_search_queries",
        "sources",
        "saved_path",
        "intermediate_paths",
    ]

    summary = {key: _to_plain_data(state.get(key)) for key in keys if key in state}

    for text_key in ("current_note", "verification_report", "final_note"):
        value = state.get(text_key, "")
        summary[text_key] = value[:1000] if isinstance(value, str) else value

    summary["search_results_count"] = len(state.get("search_results", []) or [])
    summary["evidence_items_count"] = len(state.get("evidence_items", []) or [])
    return summary


def save_state_snapshot(run_id: str, state: dict[str, Any], name: str = "final_state") -> str:
    path = get_run_dir(run_id) / f"{name}.json"
    _write_json(path, summarize_state(state))
    return str(path.resolve())


def save_intermediate_note(run_id: str, label: str, content: str) -> str:
    safe_label = "".join(ch for ch in label if ch.isalnum() or ch in {"_", "-"}).strip("_")
    safe_label = safe_label or "note"

    path = INTERMEDIATE_DIR / run_id / f"{safe_label}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")
    return str(path.resolve())


def _cache_key(search_api: str, query: str, max_results: int) -> str:
    raw = f"{search_api}::{query}::{max_results}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def load_search_cache(
    *,
    search_api: str,
    query: str,
    max_results: int,
) -> list[SearchResultItem] | None:
    path = CACHE_DIR / f"{_cache_key(search_api, query, max_results)}.json"

    if not path.exists():
        return None

    try:
        data = _read_json(path)
        return [SearchResultItem(**item) for item in data]
    except Exception:
        return None


def save_search_cache(
    *,
    search_api: str,
    query: str,
    max_results: int,
    results: list[SearchResultItem],
) -> None:
    path = CACHE_DIR / f"{_cache_key(search_api, query, max_results)}.json"
    _write_json(path, results)