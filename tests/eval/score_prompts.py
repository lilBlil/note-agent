#!/usr/bin/env python3
"""
Prompt quality scorer for the Note Agent.

This is the OPTIMIZATION loop the eval suite was missing. Instead of asking
"did the prompt change?" (snapshots) or "is the output structurally valid?"
(node logic), it asks the question you actually care about:

    "Does this prompt produce genuinely valuable learning notes?"

It does so by:
  1. Running the real generation prompts (infer_type → generate_initial_note)
     over a set of eval cases with real LLM calls.
  2. Scoring each note with an LLM-as-judge (tests/eval/judge.py) on the
     dimensions that make a learning note valuable.
  3. Averaging over N samples per case to damp LLM randomness.
  4. Aggregating per-dimension scores AND the judge's prompt-level feedback,
     so you know exactly what to change in prompts.py next.

Because it makes real LLM calls it is NOT run by default pytest. Invoke it
directly:

    # Score a quick 3-case subset, 1 sample each (cheap smoke test)
    python -m tests.eval.score_prompts --quick

    # Score the curated subset, 2 samples each
    python -m tests.eval.score_prompts --samples 2

    # Score specific cases
    python -m tests.eval.score_prompts --cases case_01_quantum,case_16_rust_ownership

    # Compare against a previous baseline report (to see if a prompt edit helped)
    python -m tests.eval.score_prompts --baseline reports/prompt_score_2026xxxx.json

    # Use a different provider for the judge than for generation (recommended:
    # a strong model as judge to reduce self-preference bias)
    python -m tests.eval.score_prompts --gen-provider deepseek --judge-provider openai
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from tests.eval.cases import EVAL_CASES
from tests.eval.judge import RUBRIC, judge_note

REPORTS_DIR = Path(__file__).parent / "reports"

# A cheap default subset covering diverse paths (math, code, English, vague, pure-text)
QUICK_IDS = ["case_04_closure", "case_18_vague_ai", "case_19_technical_debt"]
DEFAULT_IDS = [
    "case_01_quantum", "case_03_cap_theorem", "case_04_closure",
    "case_06_transformer", "case_16_rust_ownership", "case_19_technical_debt",
]


# ---------------------------------------------------------------------------
# Note generation — runs the real prompts (no full pipeline, just the two
# prompts that determine note quality: structure + initial draft).
# ---------------------------------------------------------------------------

def generate_note(raw_input: str, provider: str) -> tuple[str, str]:
    """Run infer_type_and_outline → generate_initial_note. Returns (note_type, note_md)."""
    from note_agent.config.llm import ask_llm
    from note_agent.agent.prompts import (
        generate_initial_note_prompt,
        infer_type_and_outline_prompt,
    )

    infer_raw = ask_llm(infer_type_and_outline_prompt(raw_input), provider=provider, stream=False)
    cleaned = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", infer_raw.strip(), flags=re.DOTALL)
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    data = json.loads(m.group()) if m else {"note_type": "学习笔记", "outline": []}
    note_type = data.get("note_type", "学习笔记")
    outline = json.dumps(data.get("outline", []), ensure_ascii=False)

    note = ask_llm(
        generate_initial_note_prompt(raw_input, note_type, outline),
        provider=provider,
        stream=False,
    )
    return note_type, note


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_case(
    case: dict[str, Any],
    samples: int,
    gen_provider: str,
    judge_provider: str,
) -> dict[str, Any]:
    """Generate + judge a case `samples` times; return averaged scores and
    collected qualitative feedback."""
    dim_sums: dict[str, float] = defaultdict(float)
    dim_counts: dict[str, int] = defaultdict(int)
    overalls: list[float] = []
    hallucinations: list[str] = []
    weaknesses: list[str] = []
    prompt_feedback: list[str] = []
    errors: list[str] = []

    for i in range(samples):
        try:
            note_type, note = generate_note(case["input"], gen_provider)
        except Exception as e:
            errors.append(f"sample {i}: generation failed: {e}")
            continue

        verdict = judge_note(case["input"], note, note_type, provider=judge_provider)
        if verdict.get("error"):
            errors.append(f"sample {i}: {verdict['error']}")
            continue

        overalls.append(verdict["overall"])
        for dim, val in verdict.get("scores", {}).items():
            if isinstance(val, (int, float)):
                dim_sums[dim] += float(val)
                dim_counts[dim] += 1
        hallucinations.extend(verdict.get("hallucinations", []))
        weaknesses.extend(verdict.get("weaknesses", []))
        prompt_feedback.extend(verdict.get("prompt_feedback", []))

    avg_dims = {d: round(dim_sums[d] / dim_counts[d], 3) for d in dim_sums if dim_counts[d]}
    avg_overall = round(sum(overalls) / len(overalls), 3) if overalls else 0.0

    return {
        "id": case["id"],
        "name": case["name"],
        "samples_ok": len(overalls),
        "avg_overall": avg_overall,
        "avg_dimensions": avg_dims,
        "hallucinations": hallucinations,
        "weaknesses": weaknesses,
        "prompt_feedback": prompt_feedback,
        "errors": errors,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll per-case results into a suite-level summary."""
    dim_sums: dict[str, float] = defaultdict(float)
    dim_counts: dict[str, int] = defaultdict(int)
    overalls = [r["avg_overall"] for r in results if r["samples_ok"]]

    all_feedback: list[str] = []
    all_hallucinations: list[str] = []
    for r in results:
        for dim, val in r["avg_dimensions"].items():
            dim_sums[dim] += val
            dim_counts[dim] += 1
        all_feedback.extend(r["prompt_feedback"])
        all_hallucinations.extend(r["hallucinations"])

    suite_dims = {d: round(dim_sums[d] / dim_counts[d], 3) for d in dim_sums if dim_counts[d]}
    suite_overall = round(sum(overalls) / len(overalls), 3) if overalls else 0.0

    # Weakest dimension first — that's where prompt work pays off most.
    ranked = sorted(suite_dims.items(), key=lambda kv: kv[1])

    return {
        "suite_overall": suite_overall,
        "suite_dimensions": suite_dims,
        "weakest_dimensions": ranked,
        "all_prompt_feedback": all_feedback,
        "all_hallucinations": all_hallucinations,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(summary: dict[str, Any], results: list[dict[str, Any]],
                 baseline: dict[str, Any] | None) -> None:
    print("\n" + "=" * 68)
    print("  PROMPT QUALITY REPORT")
    print("=" * 68)

    base_overall = baseline["summary"]["suite_overall"] if baseline else None
    delta = ""
    if base_overall is not None:
        d = summary["suite_overall"] - base_overall
        delta = f"   (baseline {base_overall} → Δ {d:+.3f})"
    print(f"\n  Overall quality: {summary['suite_overall']} / 5{delta}")

    print("\n  Per-dimension (weakest first — fix these in the prompt):")
    base_dims = baseline["summary"]["suite_dimensions"] if baseline else {}
    for dim, score in summary["weakest_dimensions"]:
        zh = RUBRIC.get(dim, {}).get("zh", dim)
        w = RUBRIC.get(dim, {}).get("weight", 0)
        bd = ""
        if dim in base_dims:
            bd = f"  (Δ {score - base_dims[dim]:+.2f})"
        print(f"    {score:.2f}  [{zh} · w={w}]  {dim}{bd}")

    print("\n  Per-case overall:")
    for r in sorted(results, key=lambda x: x["avg_overall"]):
        flag = "  ⚠ HALLUCINATION" if r["hallucinations"] else ""
        err = f"  (errors: {len(r['errors'])})" if r["errors"] else ""
        print(f"    {r['avg_overall']:.2f}  {r['id']} — {r['name']}{flag}{err}")

    if summary["all_hallucinations"]:
        print("\n  ⚠ Suspected hallucinations across the suite:")
        for h in summary["all_hallucinations"][:15]:
            print(f"    - {h}")

    print("\n  Top prompt-improvement suggestions (from the judge):")
    # Deduplicate near-identical feedback lines, keep most common signal first.
    freq: dict[str, int] = defaultdict(int)
    for fb in summary["all_prompt_feedback"]:
        freq[fb.strip()] += 1
    for fb, count in sorted(freq.items(), key=lambda kv: -kv[1])[:12]:
        tag = f" (x{count})" if count > 1 else ""
        print(f"    - {fb}{tag}")
    print()


def save_report(summary: dict[str, Any], results: list[dict[str, Any]],
                meta: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # Deterministic, sortable filename from the case set + sample count.
    # (No timestamp — Date.now-style calls are avoided; caller can rename.)
    stem = f"prompt_score_{meta['tag']}"
    path = REPORTS_DIR / f"{stem}.json"
    n = 1
    while path.exists():
        path = REPORTS_DIR / f"{stem}_{n}.json"
        n += 1
    path.write_text(
        json.dumps({"meta": meta, "summary": summary, "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def resolve_cases(args) -> list[dict[str, Any]]:
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        cases = [c for c in EVAL_CASES if c["id"] in wanted]
        missing = wanted - {c["id"] for c in cases}
        if missing:
            raise SystemExit(f"Unknown case ids: {sorted(missing)}")
        return cases
    ids = QUICK_IDS if args.quick else DEFAULT_IDS
    return [c for c in EVAL_CASES if c["id"] in ids]


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Note Agent prompt quality via LLM-as-judge")
    parser.add_argument("--quick", action="store_true", help="Cheap 3-case subset, 1 sample")
    parser.add_argument("--cases", type=str, default=None, help="Comma-separated case ids")
    parser.add_argument("--samples", type=int, default=1, help="Samples per case (avg to reduce noise)")
    parser.add_argument("--gen-provider", type=str, default="deepseek", help="Provider for generation")
    parser.add_argument("--judge-provider", type=str, default="deepseek", help="Provider for judging")
    parser.add_argument("--baseline", type=str, default=None, help="Path to a previous report JSON to diff against")
    parser.add_argument("--no-save", action="store_true", help="Do not write a report file")
    args = parser.parse_args()

    samples = 1 if args.quick else max(1, args.samples)
    cases = resolve_cases(args)

    baseline = None
    if args.baseline:
        bp = Path(args.baseline)
        if not bp.exists():
            raise SystemExit(f"Baseline not found: {bp}")
        baseline = json.loads(bp.read_text(encoding="utf-8"))

    print(f"\nScoring {len(cases)} case(s), {samples} sample(s) each")
    print(f"  generation provider: {args.gen_provider}")
    print(f"  judge provider:      {args.judge_provider}")
    if args.gen_provider == args.judge_provider:
        print("  note: same provider generates and judges — consider a different "
              "--judge-provider to reduce self-preference bias.")

    results: list[dict[str, Any]] = []
    for case in cases:
        print(f"  · {case['id']} ...", flush=True)
        results.append(score_case(case, samples, args.gen_provider, args.judge_provider))

    summary = aggregate(results)
    print_report(summary, results, baseline)

    if not args.no_save:
        tag = "quick" if args.quick else (args.cases.replace(",", "-")[:40] if args.cases else "default")
        meta = {
            "tag": tag,
            "samples": samples,
            "gen_provider": args.gen_provider,
            "judge_provider": args.judge_provider,
            "case_ids": [c["id"] for c in cases],
            "rubric_weights": {k: v["weight"] for k, v in RUBRIC.items()},
        }
        path = save_report(summary, results, meta)
        print(f"  report saved: {path}")


if __name__ == "__main__":
    main()
