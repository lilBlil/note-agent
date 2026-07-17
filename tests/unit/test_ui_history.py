"""Tests for Streamlit sidebar history helpers."""

from __future__ import annotations

import json

from note_agent.ui import history


def _write_run(runs_dir, run_id: str, **extra) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    data = {
        "run_id": run_id,
        "status": "done",
        "raw_input_preview": "original topic",
        "created_at": "2026-01-01T00:00:00",
        **extra,
    }
    (run_dir / "run.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_list_runs_prefers_custom_display_name(tmp_path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(history, "_RUNS", runs_dir)
    _write_run(runs_dir, "run_2", display_name="Renamed project")

    runs = history.list_runs()

    assert runs[0]["preview"] == "Renamed project"


def test_rename_run_updates_run_json(tmp_path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(history, "_RUNS", runs_dir)
    _write_run(runs_dir, "run_1")

    assert history.rename_run("run_1", "  New   Name  ")

    meta = json.loads((runs_dir / "run_1" / "run.json").read_text(encoding="utf-8"))
    assert meta["display_name"] == "New Name"
    assert "updated_at" in meta


def test_delete_run_removes_only_target_run(tmp_path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(history, "_RUNS", runs_dir)
    _write_run(runs_dir, "run_1")
    _write_run(runs_dir, "run_2")

    assert history.delete_run("run_1")

    assert not (runs_dir / "run_1").exists()
    assert (runs_dir / "run_2").exists()
