"""Regression tests for the benchmark harness schema and report."""

from __future__ import annotations

import pytest

from tests.eval import benchmark


def test_loop_benchmark_aggregates_all_required_metrics(monkeypatch) -> None:
    cases = [
        {"id": "case-a", "input": "first"},
        {"id": "case-b", "input": "second"},
    ]

    def fake_run(case, max_iterations, provider):
        return {
            "final_note": f"note-{case['id']}-{max_iterations}",
            "note_type": "test",
            "iterations": max_iterations,
            "input_tokens": 10 + max_iterations,
            "output_tokens": 20 + max_iterations,
            "total_tokens": 30 + max_iterations,
            "latency_seconds": 0.1 + max_iterations / 100,
        }

    def fake_judge(raw_input, note, note_type, provider):
        iteration = int(note.rsplit("-", 1)[1])
        return {
            "overall": 3.0 + iteration,
            "scores": {
                "factual_accuracy": 2 + iteration,
                "depth_and_mechanism": 3,
            },
            "hallucinations": ["one"] if iteration == 0 else [],
        }

    monkeypatch.setattr(benchmark, "_run_pipeline_to_final", fake_run)
    monkeypatch.setattr("tests.eval.judge.judge_note", fake_judge)

    result = benchmark.study_loop(cases, [0, 1, 2], "deepseek")

    assert result["sample_size"] == 2
    assert result["provider"] == "deepseek"
    assert result["model"]
    assert set(result["aggregate"]) == {"0", "1", "2"}

    iteration_zero = result["aggregate"]["0"]
    assert iteration_zero["quality_score"] == 3.0
    assert iteration_zero["factual_accuracy"] == 2.0
    assert iteration_zero["avg_hallucinations"] == 1.0
    assert iteration_zero["avg_input_tokens"] == 10
    assert iteration_zero["avg_output_tokens"] == 20
    assert iteration_zero["avg_total_tokens"] == 30
    assert iteration_zero["avg_latency_seconds"] == 0.1

    row = result["per_case"][0]["by_iter"]["2"]
    assert row["quality_score"] == row["overall"] == 5.0
    assert row["hallucination_count"] == 0
    assert row["input_tokens"] == 12
    assert row["output_tokens"] == 22
    assert row["total_tokens"] == 32
    assert row["latency_seconds"] == pytest.approx(0.12)


def test_benchmark_report_states_sample_and_model_dependency() -> None:
    result = {
        "study": "loop",
        "n_cases": 8,
        "sample_size": 8,
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "iters": [0, 1, 2],
        "aggregate": {
            str(iteration): {
                "quality_score": 4.0,
                "factual_accuracy": 4.0,
                "depth": 4.0,
                "avg_hallucinations": 0.5,
                "avg_input_tokens": 100,
                "avg_output_tokens": 200,
                "avg_total_tokens": 300,
                "avg_latency_seconds": 1.25,
            }
            for iteration in (0, 1, 2)
        },
        "per_case": [],
    }

    report = benchmark.render_markdown([result])

    assert "n=8 cases" in report
    assert "Provider: `deepseek`" in report
    assert "Model: `deepseek-v4-flash`" in report
    assert "quality_score" in report
    assert "factual_accuracy" in report
    assert "avg_hallucinations" in report
    assert "avg_input_tokens" in report
    assert "avg_output_tokens" in report
    assert "avg_total_tokens" in report
    assert "avg_latency_seconds" in report
    assert "does not establish that any iteration count is universally best" in report


def test_default_benchmark_sample_size_is_at_least_eight() -> None:
    assert benchmark.DEFAULT_SAMPLE_SIZE >= 8
