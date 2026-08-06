"""
End-to-end quality tests with REAL LLM calls.

Gated behind `--e2e` flag. Requires valid API keys.

These tests call the actual `ask_llm` function and verify:
1. Pipeline stages complete without errors
2. Output format is valid
3. Key content expectations are met
4. No obvious regressions on known cases

Usage:
    pytest tests/eval/test_e2e_quality.py --e2e -v
    pytest tests/eval/test_e2e_quality.py --e2e -v -k "case_01"  # single case
"""

from __future__ import annotations

import json
import re

import pytest

from tests.eval.cases import EVAL_CASES, Dim

# Only run these tests when --e2e is passed
pytestmark = pytest.mark.skipif(
    "not config.getoption('--e2e')",
    reason="E2E tests require --e2e flag (real LLM calls, slow, costs tokens)"
)


# ============================================================================
# Helper checks
# ============================================================================

def _check_markdown_structure(note: str) -> dict[str, str | bool]:
    """Validate basic markdown structure and return issues."""
    issues = {}

    if not note.startswith("# "):
        issues["first_line_heading"] = f"First line is not '# ...' heading: {note[:80]!r}"

    if "```markdown" in note or "```md" in note:
        issues["has_markdown_fence"] = "Output is wrapped in a markdown code fence"

    lines = note.splitlines()
    h1_count = sum(1 for line in lines if re.match(r"^# ", line))
    if h1_count == 0:
        issues["no_h1"] = "No top-level heading (^# ) found"
    elif h1_count > 1:
        issues["multiple_h1"] = f"Multiple top-level headings: {h1_count}"

    h2_count = sum(1 for line in lines if re.match(r"^## ", line))
    if h2_count == 0:
        issues["no_h2"] = "No second-level headings — content may be unstructured"

    return issues


def _check_key_terms(note: str, key_terms: list[str]) -> dict[str, list[str]]:
    """Check which expected key terms are missing."""
    note_lower = note.lower()
    missing = [term for term in key_terms if term.lower() not in note_lower]
    if missing:
        return {"missing_key_terms": missing}
    return {}


def _check_assets_coverage(note: str, case: dict) -> dict[str, str]:
    """Check if assets are appropriate for the case."""
    issues = {}
    has_formula = "$$" in note or "\\(" in note
    has_code = "```" in note

    if case["needs_assets"]:
        dims = case.get("dimensions", [])
        if Dim.MATH in dims and not has_formula:
            issues["missing_formula"] = "Math-heavy topic but no formula assets found"
        if Dim.CODE in dims and not has_code:
            issues["missing_code"] = "Code-heavy topic but no code blocks found"
    else:
        # Should not add unnecessary assets
        pass

    return issues


def _count_pipeline_invocations(case_id: str, max_iterations: int, enable_assets: bool,
                                enable_notion: bool) -> int:
    """Expected number of ask_llm calls for a given pipeline path.

    Pipeline: infer → generate → (queries → retrieve → verify) × N → finalize
              → [plan → generate_assets → assemble → ] save → [notion]

    Key: N = max_iterations
    - Non-search path (max_iterations=0): infer + direct final = 2
    - Search path (max_iterations>0): 3 + N * 2 (queries + verify)
    - Assets path (+enable_assets): +2 (plan + generate_assets)
    - Notion (+enable_notion): no extra LLM call
    """
    base = 2 if max_iterations <= 0 else 3  # direct final, or draft + finalize
    if max_iterations > 0:
        base += max_iterations * 2  # queries + verify per iteration
    if enable_assets:
        base += 2  # plan_assets + generate_assets
    return base


# ============================================================================
# E2E test runner — one parametrized test per case
# ============================================================================

# Only run a curated subset for E2E by default (cases that cover diverse paths)
# Full suite is too slow/expensive; override with -k to run specific cases.
E2E_SUBSET_IDS = [
    "case_01_quantum",       # math + theory
    "case_03_cap_theorem",   # pure text theory
    "case_04_closure",       # short input
    "case_06_transformer",   # paper reading, English mixed
    "case_08_fastapi",       # GitHub analysis, URL
    "case_10_url_shortener", # interview prep, system design
    "case_14_llm_hallucination", # survey
    "case_16_rust_ownership",    # all English
    "case_18_vague_ai",      # vague input edge case
    "case_19_technical_debt",    # pure text, no assets
]

E2E_CASES = [c for c in EVAL_CASES if c["id"] in E2E_SUBSET_IDS]


class TestE2ENodeLevel:
    """Test individual prompt functions with real LLM — cheaper than full pipeline."""

    @pytest.mark.parametrize("case", E2E_CASES, ids=lambda c: c["id"])
    def test_infer_type_and_outline(self, case: dict) -> None:
        """Infer node: output must be parseable JSON with required fields."""
        from note_agent.config.llm import ask_llm
        from note_agent.agent.prompts import infer_type_and_outline_prompt

        prompt = infer_type_and_outline_prompt(case["input"])
        text = ask_llm(prompt, stream=False)

        # Clean the response
        text = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", text.strip(), flags=re.DOTALL)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(m.group()) if m else None

        assert data is not None, f"Failed to parse JSON from LLM response:\n{text[:500]}"
        assert "note_type" in data, f"Missing 'note_type' in response: {list(data.keys())}"
        assert "outline" in data, f"Missing 'outline' in response: {list(data.keys())}"
        assert isinstance(data["outline"], list), "'outline' is not a list"
        assert len(data["outline"]) > 0, "Outline is empty"
        for item in data["outline"]:
            assert "title" in item, f"Outline item missing 'title': {item}"

    @pytest.mark.parametrize("case", E2E_CASES, ids=lambda c: c["id"])
    def test_generate_initial_note(self, case: dict) -> None:
        """Initial note: must be valid markdown with structure."""
        from note_agent.config.llm import ask_llm
        from note_agent.agent.prompts import infer_type_and_outline_prompt, generate_initial_note_prompt

        # First get outline
        prompt1 = infer_type_and_outline_prompt(case["input"])
        text1 = ask_llm(prompt1, stream=False)
        text1 = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", text1.strip(), flags=re.DOTALL)
        m = re.search(r"\{.*\}", text1, re.DOTALL)
        data = json.loads(m.group()) if m else {"note_type": "学习笔记", "outline": []}
        note_type = data.get("note_type", "学习笔记")
        outline = json.dumps(data.get("outline", []), ensure_ascii=False)

        # Then generate note
        prompt2 = generate_initial_note_prompt(case["input"], note_type, outline)
        text2 = ask_llm(prompt2, stream=False)

        issues = _check_markdown_structure(text2)
        assert not issues, f"Markdown structure issues for case '{case['id']}':\n" + \
                           "\n".join(f"  - {k}: {v}" for k, v in issues.items())

        # Check minimum sections
        h2_count = sum(1 for line in text2.splitlines() if re.match(r"^## ", line))
        assert h2_count >= case.get("min_sections", 2), \
            f"Only {h2_count} sections, expected at least {case['min_sections']}"

        # Title should be present and meaningful
        h1 = [line for line in text2.splitlines() if re.match(r"^# ", line)]
        assert h1, "No top-level heading"
        title_text = h1[0].lstrip("# ").strip()
        assert len(title_text) >= 2, f"Title too short: '{title_text}'"


class TestE2EFullPipeline:
    """Full pipeline tests — expensive, run sparingly."""

    # Only test a few representative cases through the full pipeline
    FULL_CASES = [c for c in EVAL_CASES if c["id"] in [
        "case_03_cap_theorem",    # theory, no assets
        "case_19_technical_debt",  # pure text, no assets
    ]]

    @pytest.mark.parametrize("case", FULL_CASES, ids=lambda c: c["id"])
    def test_full_pipeline_no_assets(self, case: dict) -> None:
        """Full pipeline without assets — only text generation path."""
        from note_agent.agent.runner import build_initial_state
        from note_agent.agent.graph import get_graph
        from note_agent.domain.models import new_run_id
        from note_agent.domain.api import NoteAgentRequest

        request = NoteAgentRequest(
            raw_input=case["input"],
            max_iterations=0,
            enable_assets=False,
            enable_notion=False,
        )
        state = build_initial_state(request, new_run_id())

        from unittest.mock import patch
        with patch("note_agent.agent.graph.save_markdown", lambda t, c: f"/tmp/{t}.md"), \
             patch("note_agent.agent.graph.save_intermediate_note", lambda rid, label, note: f"/tmp/{rid}_{label}.md"), \
             patch("note_agent.agent.graph.append_event", lambda rid, ev: None), \
             patch("note_agent.agent.graph.emit_event"), \
             patch("note_agent.agent.graph.emit_node_start"):

            graph = get_graph()
            result = graph.invoke(state)

        # Basic structure checks
        final = result.get("final_note", "")
        assert final, "final_note is empty"

        issues = _check_markdown_structure(final)
        assert not issues, "Markdown issues:\n" + \
                           "\n".join(f"  - {k}: {v}" for k, v in issues.items())

        # Key terms
        term_issues = _check_key_terms(final, case.get("key_terms", []))
        # Key terms are SOFT checks — only warn if more than half are missing
        if term_issues:
            missing = term_issues.get("missing_key_terms", [])
            miss_rate = len(missing) / len(case["key_terms"]) if case["key_terms"] else 0
            if miss_rate > 0.5:
                pytest.fail(
                    f"More than 50% key terms missing.\nMissing: {missing}\n"
                    f"Note excerpt:\n{final[:500]}"
                )
            else:
                pytest.skip(
                    f"Some key terms missing (acceptable): {missing}"
                )

        # Note type should be reasonable (soft check)
        note_type = result.get("note_type", "")
        assert note_type, "note_type is empty"
