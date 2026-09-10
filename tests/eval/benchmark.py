#!/usr/bin/env python3
"""
Quantitative benchmark harness — turns the eval suite into resume-ready numbers.

Runs two ablation studies over the eval cases with REAL LLM calls:

  A. Retrieve-verify loop value
     For each case, generate a note at iterations = 0, 1, 2 and score every
     version with the LLM judge. Reports how factual_accuracy / overall rise
     and how hallucination count falls as the loop runs — plus token cost.

  B. PATCH vs full-rewrite token efficiency
     For the same (note, references) pair, run the incremental PATCH refine
     against a whole-note rewrite. Reports output-token savings at equal
     judge-measured quality.

Outputs machine-readable JSON + a human/markdown summary with the exact deltas
you can quote (e.g. "factual accuracy 3.8 -> 4.4, output tokens -47%").

Usage:
    python -m tests.eval.benchmark --study loop  --n 5 --iters 0,1,2
    python -m tests.eval.benchmark --study patch --n 5
    python -m tests.eval.benchmark --study all   --n 8 --provider deepseek
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "benchmark_results"
DEFAULT_SAMPLE_SIZE = 8


def _mean(xs: list[float], digits: int = 3) -> float:
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), digits) if xs else 0.0


def _model_name(provider: str) -> str:
    """Return the configured model name without making a provider call."""
    from note_agent.config.settings import MODEL_CONFIGS

    return str(MODEL_CONFIGS.get(provider, {}).get("model", "unknown"))


def _run_pipeline_to_final(case: dict, max_iterations: int, provider: str) -> dict:
    """Run the fixed graph end-to-end with real LLM calls but mocked disk I/O.

    Returns the final note, iteration count, token usage, and pipeline latency.
    Token usage comes from the per-run ContextVar tracker so we count only this
    case's generation spend.
    """
    from unittest.mock import patch
    from note_agent.agent.graph import get_graph
    from note_agent.agent.runner import build_initial_state
    from note_agent.agent.tracker import reset_usage, summarize_usage
    from note_agent.domain.models import new_run_id
    from note_agent.domain.api import NoteAgentRequest

    request = NoteAgentRequest(
        raw_input=case["input"],
        max_iterations=max_iterations,
        llm_provider=provider,
        enable_assets=False,
        enable_notion=False,
    )
    state = build_initial_state(request, new_run_id())
    reset_usage()

    # Register a no-op event handler so ask_llm's streaming path routes tokens
    # to the handler instead of printing to stdout (which crashes on Windows
    # GBK consoles for chars like superscripts). This mirrors how runner.py
    # always runs the graph with a handler set.
    from note_agent.io.events import set_event_handler, reset_event_handler
    _tok = set_event_handler(lambda ev: None)

    # Capture intermediate notes so we can inspect what each refine round did
    # (the pipeline normally writes these to disk; here we keep them in memory).
    captured: list[tuple[str, str]] = []

    def _capture(run_id, label, note):
        captured.append((label, note))
        return f"/tmp/{label}.md"

    try:
        with patch("note_agent.agent.graph.save_markdown", lambda t, c: "/tmp/x.md"), \
             patch("note_agent.agent.graph.save_intermediate_note", _capture), \
             patch("note_agent.agent.graph.append_event", lambda *a, **k: None):
            started = time.perf_counter()
            result = get_graph().invoke(state)
            latency_seconds = time.perf_counter() - started
    finally:
        reset_event_handler(_tok)

    usage = summarize_usage()
    # Persist captured intermediate notes for per-round inspection.
    if captured:
        dbg = RESULTS_DIR / "intermediates" / f"{case['id']}_iter{max_iterations}"
        dbg.mkdir(parents=True, exist_ok=True)
        for i, (label, note) in enumerate(captured):
            (dbg / f"{i:02d}_{label}.md").write_text(note, encoding="utf-8")

    return {
        "final_note": result.get("final_note", ""),
        "note_type": result.get("note_type", ""),
        "iterations": result.get("iteration_count", 0),
        "input_tokens": usage["total_input_tokens"],
        "output_tokens": usage["total_output_tokens"],
        "total_tokens": usage["total_tokens"],
        "latency_seconds": round(latency_seconds, 6),
    }


# ============================================================================
# Study A — retrieve-verify loop value
# ============================================================================

def study_loop(cases: list[dict], iters: list[int], provider: str) -> dict:
    from tests.eval.judge import judge_note

    per_case = []
    for case in cases:
        print(f"  [loop] {case['id']} ...", flush=True)
        row = {"id": case["id"], "by_iter": {}}
        for n in iters:
            run = _run_pipeline_to_final(case, n, provider)
            judged = judge_note(case["input"], run["final_note"],
                                run["note_type"], provider=provider)
            hallucination_count = len(judged.get("hallucinations", []))
            row["by_iter"][str(n)] = {
                "quality_score": judged["overall"],
                "overall": judged["overall"],
                "factual_accuracy": judged["scores"].get("factual_accuracy"),
                "depth": judged["scores"].get("depth_and_mechanism"),
                "hallucination_count": hallucination_count,
                "hallucinations": hallucination_count,
                "input_tokens": run["input_tokens"],
                "output_tokens": run["output_tokens"],
                "total_tokens": run["total_tokens"],
                "latency_seconds": run["latency_seconds"],
            }
            print(f"      iter={n}: quality={judged['overall']} "
                  f"halluc={hallucination_count} tok={run['total_tokens']} "
                  f"latency={run['latency_seconds']:.3f}s", flush=True)
        per_case.append(row)

    # Aggregate per iteration across all cases
    agg = {}
    for n in iters:
        key = str(n)
        agg[key] = {
            "quality_score": _mean([r["by_iter"][key]["quality_score"] for r in per_case]),
            "overall": _mean([r["by_iter"][key]["overall"] for r in per_case]),
            "factual_accuracy": _mean([r["by_iter"][key]["factual_accuracy"] for r in per_case]),
            "depth": _mean([r["by_iter"][key]["depth"] for r in per_case]),
            "avg_hallucinations": _mean([
                r["by_iter"][key]["hallucination_count"] for r in per_case
            ]),
            "hallucination_count": _mean([
                r["by_iter"][key]["hallucination_count"] for r in per_case
            ]),
            "avg_input_tokens": round(_mean([
                r["by_iter"][key]["input_tokens"] for r in per_case
            ])),
            "avg_output_tokens": round(_mean([
                r["by_iter"][key]["output_tokens"] for r in per_case
            ])),
            "avg_total_tokens": round(_mean([
                r["by_iter"][key]["total_tokens"] for r in per_case
            ])),
            "avg_tokens": round(_mean([r["by_iter"][key]["total_tokens"] for r in per_case])),
            "avg_latency_seconds": _mean([
                r["by_iter"][key]["latency_seconds"] for r in per_case
            ], digits=6),
        }
    return {
        "study": "loop",
        "n_cases": len(cases),
        "sample_size": len(cases),
        "iters": iters,
        "provider": provider,
        "model": _model_name(provider),
        "aggregate": agg,
        "per_case": per_case,
    }


# ============================================================================
# Study B — PATCH vs full-rewrite token efficiency
# ============================================================================

def _count_tokens(text: str) -> int:
    """Approximate token count (chars/2 for CJK-heavy text is a fair proxy when
    the provider doesn't return usage on a bare call). We instead use the real
    usage tracker, so this is only a fallback."""
    return max(1, len(text) // 2)


def study_patch(cases: list[dict], provider: str) -> dict:
    """For each case: build a draft + references, then refine two ways and
    compare output tokens at equal judge quality."""
    from note_agent.config.llm import ask_llm
    from note_agent.agent.graph import _apply_patches
    from note_agent.agent.prompts import verify_and_refine_prompt, rewrite_note_prompt
    from note_agent.agent.tracker import reset_usage, summarize_usage
    from tests.eval.judge import judge_note

    per_case = []
    for case in cases:
        print(f"  [patch] {case['id']} ...", flush=True)
        draft = _run_pipeline_to_final(case, 0, provider)  # iteration-0 note as the base
        note = draft["final_note"]
        refs = "无参考信息检索结果。"  # isolate the edit cost, not retrieval

        reset_usage()
        patch_text = ask_llm(verify_and_refine_prompt(case["input"], note, refs),
                             provider=provider, stream=False)
        patch_out = summarize_usage()["total_output_tokens"]
        patched = _apply_patches(note, patch_text)

        reset_usage()
        rewritten = ask_llm(rewrite_note_prompt(case["input"], note, refs),
                            provider=provider, stream=False)
        rewrite_out = summarize_usage()["total_output_tokens"]

        q_patch = judge_note(case["input"], patched, draft["note_type"], provider=provider)
        q_rewrite = judge_note(case["input"], rewritten, draft["note_type"], provider=provider)

        saving = round(1 - patch_out / rewrite_out, 3) if rewrite_out else 0.0
        per_case.append({
            "id": case["id"],
            "patch_output_tokens": patch_out,
            "rewrite_output_tokens": rewrite_out,
            "token_saving_ratio": saving,
            "patch_overall": q_patch["overall"],
            "rewrite_overall": q_rewrite["overall"],
        })
        print(f"      patch_tok={patch_out} rewrite_tok={rewrite_out} "
              f"saving={saving:.0%} q_patch={q_patch['overall']} "
              f"q_rewrite={q_rewrite['overall']}", flush=True)

    agg = {
        "avg_patch_output_tokens": round(_mean([r["patch_output_tokens"] for r in per_case])),
        "avg_rewrite_output_tokens": round(_mean([r["rewrite_output_tokens"] for r in per_case])),
        "avg_token_saving_ratio": _mean([r["token_saving_ratio"] for r in per_case]),
        "avg_quality_patch": _mean([r["patch_overall"] for r in per_case]),
        "avg_quality_rewrite": _mean([r["rewrite_overall"] for r in per_case]),
    }
    return {
        "study": "patch",
        "n_cases": len(cases),
        "sample_size": len(cases),
        "provider": provider,
        "model": _model_name(provider),
        "aggregate": agg,
        "per_case": per_case,
    }


# ============================================================================
# Reporting
# ============================================================================

def _render_markdown_legacy(results: list[dict]) -> str:
    lines = ["# Benchmark Results\n"]
    for res in results:
        if res["study"] == "loop":
            agg = res["aggregate"]
            iters = res["iters"]
            lines.append(f"## A. Retrieve-verify loop value (n={res['n_cases']} cases)\n")
            lines.append("| iterations | overall | factual_accuracy | depth | avg_hallucinations | avg_tokens |")
            lines.append("|---|---|---|---|---|---|")
            for n in iters:
                a = agg[str(n)]
                lines.append(f"| {n} | {a['overall']} | {a['factual_accuracy']} | "
                             f"{a['depth']} | {a['avg_hallucinations']} | {a['avg_tokens']} |")
            lo, hi = str(iters[0]), str(iters[-1])
            fa0, fa1 = agg[lo]["factual_accuracy"], agg[hi]["factual_accuracy"]
            h0, h1 = agg[lo]["avg_hallucinations"], agg[hi]["avg_hallucinations"]
            lines.append(f"\n**结论**：迭代 {lo}→{hi} 轮，事实准确性 {fa0}→{fa1}，"
                         f"平均幻觉数 {h0}→{h1}。\n")
        elif res["study"] == "patch":
            a = res["aggregate"]
            lines.append(f"## B. PATCH vs full-rewrite (n={res['n_cases']} cases)\n")
            lines.append("| metric | PATCH | full-rewrite |")
            lines.append("|---|---|---|")
            lines.append(f"| avg output tokens | {a['avg_patch_output_tokens']} | {a['avg_rewrite_output_tokens']} |")
            lines.append(f"| avg quality (1-5) | {a['avg_quality_patch']} | {a['avg_quality_rewrite']} |")
            lines.append(f"\n**结论**：PATCH 相比整篇重写平均节省输出 token "
                         f"{a['avg_token_saving_ratio']:.0%}，质量差 "
                         f"{round(a['avg_quality_patch'] - a['avg_quality_rewrite'], 2)} 分。\n")
    return "\n".join(lines)


def render_markdown(results: list[dict]) -> str:
    """Render benchmark metrics with explicit scope and model metadata."""
    lines = ["# Benchmark Results\n"]
    for res in results:
        provider = res.get("provider", "unknown")
        model = res.get("model", "unknown")
        sample_size = res.get("sample_size", res.get("n_cases", 0))

        if res["study"] == "loop":
            agg = res["aggregate"]
            iters = res["iters"]
            lines.append(
                f"## A. Retrieve-verify loop value (n={sample_size} cases)\n"
            )
            lines.append(f"- Provider: `{provider}`\n- Model: `{model}`")
            lines.append(
                "- Token and latency metrics cover generation pipeline calls; "
                "LLM-as-judge calls are excluded.\n"
            )
            lines.append(
                "| iterations | quality_score | factual_accuracy | depth | "
                "avg_hallucinations | avg_input_tokens | avg_output_tokens | "
                "avg_total_tokens | avg_latency_seconds |"
            )
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for n in iters:
                a = agg[str(n)]
                lines.append(
                    f"| {n} | {a['quality_score']} | {a['factual_accuracy']} | "
                    f"{a['depth']} | {a['avg_hallucinations']} | "
                    f"{a['avg_input_tokens']} | {a['avg_output_tokens']} | "
                    f"{a['avg_total_tokens']} | {a['avg_latency_seconds']} |"
                )
            lines.append(
                "\n**Interpretation:** This is a descriptive result for the "
                f"current sample of {sample_size} cases and the `{provider}` / "
                f"`{model}` configuration. It is model- and judge-dependent "
                "and does not establish that any iteration count is universally best.\n"
            )
        elif res["study"] == "patch":
            aggregate = res["aggregate"]
            lines.append(f"## B. PATCH vs full-rewrite (n={sample_size} cases)\n")
            lines.append(f"- Provider: `{provider}`\n- Model: `{model}`\n")
            lines.append("| metric | PATCH | full-rewrite |")
            lines.append("|---|---|---|")
            lines.append(
                f"| avg output tokens | {aggregate['avg_patch_output_tokens']} | "
                f"{aggregate['avg_rewrite_output_tokens']} |"
            )
            lines.append(
                f"| avg quality (1-5) | {aggregate['avg_quality_patch']} | "
                f"{aggregate['avg_quality_rewrite']} |"
            )
            lines.append(
                "\n**Interpretation:** This comparison is limited to the "
                f"current sample of {sample_size} cases and the `{provider}` / "
                f"`{model}` configuration.\n"
            )
    return "\n".join(lines)


def main() -> None:
    from tests.eval.cases import EVAL_CASES

    parser = argparse.ArgumentParser(description="Quantitative benchmark harness")
    parser.add_argument("--study", choices=["loop", "patch", "all"], default="all")
    parser.add_argument(
        "--n", type=int, default=DEFAULT_SAMPLE_SIZE, help="number of cases to run"
    )
    parser.add_argument("--iters", type=str, default="0,1,2", help="loop iterations, e.g. 0,1,2")
    parser.add_argument("--provider", type=str, default="deepseek")
    args = parser.parse_args()

    cases = EVAL_CASES[: args.n]
    iters = [int(x) for x in args.iters.split(",") if x.strip().isdigit()]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    if args.study in ("loop", "all"):
        results.append(study_loop(cases, iters, args.provider))
    if args.study in ("patch", "all"):
        results.append(study_patch(cases, args.provider))

    (RESULTS_DIR / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report = render_markdown(results)
    (RESULTS_DIR / "REPORT.md").write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\nSaved: {RESULTS_DIR / 'results.json'}  and  {RESULTS_DIR / 'REPORT.md'}")


if __name__ == "__main__":
    main()
