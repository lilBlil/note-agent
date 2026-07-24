"""Tests for Streamlit sidebar history helpers."""

from __future__ import annotations

import json

from note_agent.ui import history


def _write_run(runs_dir, run_id: str, **extra) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    data = {
        "run_id": run_id,
        "status": extra.pop("status", "done"),
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


def test_list_runs_prefers_planned_title_over_raw_input(tmp_path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(history, "_RUNS", runs_dir)
    _write_run(
        runs_dir,
        "run_3",
        status="running",
    )
    run_dir = runs_dir / "run_3"
    (run_dir / "final_state.json").write_text(
        json.dumps(
            {
                "run_id": "run_3",
                "note_outline": [{"title": "唐宋八大家散文研究"}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runs = history.list_runs()

    assert runs[0]["preview"] == "唐宋八大家散文研究"


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


def test_load_view_keeps_running_status_and_usage(tmp_path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(history, "_RUNS", runs_dir)
    _write_run(
        runs_dir,
        "run_1",
        status="running",
        updated_at="2099-07-24T15:11:48",
    )
    run_dir = runs_dir / "run_1"
    (run_dir / "final_state.json").write_text(
        json.dumps(
            {
                "run_id": "run_1",
                "current_note": "draft",
                "reference_queries": [{"query": "RAG", "source_types": ["web"], "reason": ""}],
                "usage": {"total_tokens": 123, "total_input_tokens": 45, "total_output_tokens": 78},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "type": "node_start",
                "node_name": "generate_reference_queries",
                "step_label": "正在分析信息缺口并生成统一检索请求",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    view = history.load_view("run_1")

    assert view is not None
    assert view["status"] == "running"
    assert view["usage"]["total_tokens"] == 123
    assert view["reference_queries"][0]["query"] == "RAG"
