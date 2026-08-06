"""Read-only access to past runs under runs/ for the sidebar history."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from note_agent.ui.runner_ui import _norm_queries, _norm_sources

_RUNS = Path("runs")


def _run_dir(run_id: str) -> Path:
    if not run_id or Path(run_id).name != run_id:
        raise ValueError("Invalid run_id")
    return _RUNS / run_id


def _md_title(run_dir: Path) -> str:
    """First markdown H1 of the finished note, else ''."""
    snap_p = run_dir / "final_state.json"
    if not snap_p.exists():
        return ""
    try:
        snap = json.loads(snap_p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    note_title = (snap.get("note_title") or "").strip()
    if note_title:
        return note_title
    outline = snap.get("note_outline") or []
    if outline and isinstance(outline, list):
        first = outline[0]
        if isinstance(first, dict):
            title = str(first.get("title", "")).strip()
            if title:
                return title
    note = snap.get("final_note") or snap.get("current_note") or ""
    for line in note.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s.lstrip("#").strip()
    return ""


def _project_name(run_dir: Path, meta: dict) -> str:
    """Prefer the note's planned title; never expose raw input preview."""
    display_name = (meta.get("display_name") or "").strip()
    if display_name:
        return display_name
    title = _md_title(run_dir)
    if title:
        return title
    return "拟定笔记"


def _is_stale_running(meta: dict, *, minutes: int = 10) -> bool:
    if meta.get("status") != "running":
        return False
    updated_at = meta.get("updated_at") or meta.get("created_at") or ""
    if not updated_at:
        return False
    try:
        ts = datetime.fromisoformat(updated_at)
    except Exception:
        return False
    now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
    return now - ts > timedelta(minutes=minutes)


def _load_trace_and_queries(run_dir: Path) -> tuple[list[dict], list[dict]]:
    event_path = run_dir / "events.jsonl"
    if not event_path.exists():
        return [], []
    trace: list[dict] = []
    queries: list[dict] = []
    try:
        lines = event_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return [], []

    for line in lines:
        try:
            event = json.loads(line)
        except Exception:
            continue
        etype = event.get("type", "")
        if etype == "node_start":
            trace.append({
                "type": etype,
                "node": event.get("node_name", ""),
                "text": f"开始：{event.get('step_label', '')}",
            })
        elif etype in {"info", "warning", "error"}:
            trace.append({
                "type": etype,
                "node": event.get("node_name", ""),
                "text": event.get("text") or event.get("message") or "",
            })
        if event.get("reference_queries") is not None:
            queries.extend(_norm_queries(event.get("reference_queries") or []))
    return trace[-120:], _norm_queries(queries)


def _latest_intermediate_note(run_id: str) -> str:
    note_dir = Path("notes") / "intermediate" / run_id
    if not note_dir.exists():
        return ""
    try:
        paths = sorted(
            (p for p in note_dir.glob("*.md") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        return ""
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if text:
            return text
    return ""


def list_runs(limit: int = 40) -> list[dict]:
    """Recent runs, newest first. Each: {run_id, preview, status, mode?}."""
    if not _RUNS.exists():
        return []
    entries: list[dict] = []
    for d in _RUNS.iterdir():
        run_json = d / "run.json"
        if not d.is_dir() or not run_json.exists():
            continue
        try:
            meta = json.loads(run_json.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({
            "run_id": meta.get("run_id", d.name),
            "preview": _project_name(d, meta),
            "status": meta.get("status", "unknown"),
            "created_at": meta.get("created_at", ""),
        })
    entries.sort(key=lambda e: e["run_id"], reverse=True)
    return entries[:limit]


def load_view(run_id: str) -> dict | None:
    """Build a done, read-only RunView from a saved run snapshot."""
    run_dir = _run_dir(run_id)
    meta_p = run_dir / "run.json"
    if not meta_p.exists():
        return None
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    except Exception:
        return None

    snap = {}
    snap_p = run_dir / "final_state.json"
    if snap_p.exists():
        try:
            snap = json.loads(snap_p.read_text(encoding="utf-8"))
        except Exception:
            snap = {}

    # Snapshot note is a 1000-char preview; prefer the full saved markdown.
    note = snap.get("final_note", "") or snap.get("current_note", "")
    saved = meta.get("saved_path") or snap.get("saved_path") or ""
    if saved:
        try:
            note = Path(saved).read_text(encoding="utf-8") or note
        except Exception:
            pass
    if not note.strip():
        note = _latest_intermediate_note(run_id)

    trace, event_queries = _load_trace_and_queries(run_dir)
    snapshot_queries = snap.get("reference_queries", []) or snap.get("used_reference_queries", []) or []

    status = meta.get("status", "done")
    if status == "cancelled":
        status = "error"
    if _is_stale_running(meta):
        status = "error"

    return {
        "status": status,
        "mode": meta.get("mode", "fixed"),
        "task": {"text": meta.get("raw_input_preview", ""), "files": [], "urls": []},
        "params": {}, "settings": {
            "llm": meta.get("llm_provider", ""), "search": meta.get("search_api", ""),
            "iters": meta.get("max_iterations", 0),
            "assets": meta.get("enable_assets", False),
            "notion": meta.get("enable_notion", False),
        },
        "nodes": [], "react": [],
        "iteration": snap.get("iteration_count", 0),
        "max_iterations": meta.get("max_iterations", 0),
        "live_text": "", "final_note": note,
        "note_type": snap.get("note_type", ""),
        "note_outline": snap.get("note_outline", []) or [],
        "sources": _norm_sources(snap.get("sources", []) or []),
        "reference_queries": _norm_queries(event_queries + _norm_queries(snapshot_queries)),
        "failed_sources": snap.get("failed_sources", []) or [],
        "failed_urls": snap.get("failed_urls", []) or [],
        "intermediate_paths": snap.get("intermediate_paths", []) or [],
        "asset_paths": snap.get("asset_paths", []) or [],
        "asset_errors": snap.get("asset_errors", []) or [],
        "saved_path": saved,
        "notion_url": meta.get("notion_url", "") or snap.get("notion_url", ""),
        "usage": snap.get("usage", {}) or {}, "trace": trace,
        "agent_outputs": [],
        "run_id": run_id, "run_log_dir": str(run_dir.resolve()),
        "error": meta.get("error", ""), "readonly": True,
        "_current_output": None, "_output_seq": 0,
        "_done_state": {
            "saved_path": saved,
            "notion_url": meta.get("notion_url", "") or snap.get("notion_url", ""),
        },
    }


def rename_run(run_id: str, name: str) -> bool:
    """Persist a custom display name for a sidebar project."""
    clean = " ".join((name or "").split())
    if not clean:
        return False

    meta_p = _run_dir(run_id) / "run.json"
    if not meta_p.exists():
        return False

    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    except Exception:
        return False

    meta["display_name"] = clean[:120]
    meta["updated_at"] = datetime.now().replace(microsecond=0).isoformat()
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def delete_run(run_id: str) -> bool:
    """Delete a saved run from the sidebar history."""
    run_dir = _run_dir(run_id)
    if not run_dir.exists() or not run_dir.is_dir():
        return False
    shutil.rmtree(run_dir)
    return True
