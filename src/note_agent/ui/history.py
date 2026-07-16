"""Read-only access to past runs under runs/ for the sidebar history."""

from __future__ import annotations

import json
from pathlib import Path

from note_agent.ui.runner_ui import _norm_sources

_RUNS = Path("runs")


def _md_title(run_dir: Path) -> str:
    """First markdown H1 of the finished note, else ''."""
    snap_p = run_dir / "final_state.json"
    if not snap_p.exists():
        return ""
    try:
        snap = json.loads(snap_p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    note = snap.get("final_note") or snap.get("current_note") or ""
    for line in note.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s.lstrip("#").strip()
    return ""


def _project_name(run_dir: Path, meta: dict) -> str:
    """Prefer the note's H1 title; fall back to the first line of the input."""
    title = _md_title(run_dir)
    if title:
        return title
    raw = (meta.get("raw_input_preview") or "").strip()
    first = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    return first


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
    run_dir = _RUNS / run_id
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

    return {
        "status": "error" if meta.get("status") == "error" else "done",
        "mode": "fixed",
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
        "sources": _norm_sources(snap.get("sources", []) or []),
        "usage": {}, "trace": [],
        "run_id": run_id, "run_log_dir": str(run_dir.resolve()),
        "error": meta.get("error", ""), "readonly": True,
    }
