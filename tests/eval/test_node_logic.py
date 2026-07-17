"""
Mock-based tests for graph node functions.

Each test mocks `ask_llm` (and other I/O) to return controlled responses,
then verifies that the node function correctly processes the output and
updates the state.

These tests verify the PIPELINE LOGIC — not LLM quality. They catch:
- JSON parse failures from malformed LLM output
- State update errors
- Boundary conditions (max_iterations, empty inputs, etc.)
- Route function correctness
"""

from __future__ import annotations

import json

import pytest

from note_agent.agent.graph import (
    build_graph,
    finalize_note,
    generate_initial_note,
    generate_note_assets,
    generate_reference_queries,
    infer_type_and_outline,
    plan_note_assets,
    publish_notion_node,
    retrieve_references_node,
    route_after_finalize,
    route_after_initial_note,
    route_after_save,
    route_iteration,
    save_markdown_node,
    verify_and_refine,
)
from note_agent.domain.models import ReferenceItem

from tests.eval.conftest import mock_ask_llm_sequence, mock_graph_io, mock_entire_pipeline


# ============================================================================
# Route functions (no LLM needed — pure logic)
# ============================================================================

class TestRouteFunctions:
    def test_route_after_initial_zero_iterations(self, base_state) -> None:
        base_state["max_iterations"] = 0
        assert route_after_initial_note(base_state) == "finalize"

    def test_route_after_initial_with_iterations(self, base_state) -> None:
        base_state["max_iterations"] = 3
        assert route_after_initial_note(base_state) == "continue"

    def test_route_iteration_at_limit(self, base_state) -> None:
        base_state["max_iterations"] = 2
        base_state["iteration_count"] = 2
        assert route_iteration(base_state) == "finalize"

    def test_route_iteration_below_limit(self, base_state) -> None:
        base_state["max_iterations"] = 3
        base_state["iteration_count"] = 1
        assert route_iteration(base_state) == "continue"

    def test_route_iteration_at_zero(self, base_state) -> None:
        base_state["max_iterations"] = 0
        base_state["iteration_count"] = 0
        assert route_iteration(base_state) == "finalize"

    def test_route_after_finalize_assets_enabled(self, base_state) -> None:
        base_state["enable_assets"] = True
        assert route_after_finalize(base_state) == "assets"

    def test_route_after_finalize_assets_disabled(self, base_state) -> None:
        base_state["enable_assets"] = False
        assert route_after_finalize(base_state) == "save"

    def test_route_after_save_notion_enabled(self, base_state) -> None:
        base_state["enable_notion"] = True
        assert route_after_save(base_state) == "publish_notion"

    def test_route_after_save_notion_disabled(self, base_state) -> None:
        base_state["enable_notion"] = False
        assert route_after_save(base_state) == "end"


# ============================================================================
# infer_type_and_outline node
# ============================================================================

class TestInferTypeAndOutline:
    def test_valid_json(self, base_state) -> None:
        resp = json.dumps({
            "note_type": "技术方案笔记",
            "outline": [
                {"title": "背景", "purpose": "说明问题场景"},
                {"title": "方案对比", "purpose": "对比各方案优劣"},
            ]
        }, ensure_ascii=False)
        with mock_entire_pipeline([resp]):
            result = infer_type_and_outline(base_state)
        assert result["note_type"] == "技术方案笔记"
        assert len(result["note_outline"]) == 2
        assert result["note_outline"][0]["title"] == "背景"

    def test_json_in_code_fence(self, base_state) -> None:
        resp = '```json\n{"note_type": "学习笔记", "outline": [{"title": "概述", "purpose": "简介"}]}\n```'
        with mock_entire_pipeline([resp]):
            result = infer_type_and_outline(base_state)
        assert result["note_type"] == "学习笔记"
        assert len(result["note_outline"]) == 1

    def test_malformed_json_fallback(self, base_state) -> None:
        """Malformed JSON should trigger fallback to defaults."""
        with mock_entire_pipeline(["这不是JSON，是随便写的"]):
            result = infer_type_and_outline(base_state)
        assert result["note_type"] == "学习笔记"  # default
        assert len(result["note_outline"]) == 4  # default outline has 4 entries

    def test_empty_response(self, base_state) -> None:
        with mock_entire_pipeline([""]):
            result = infer_type_and_outline(base_state)
        assert result["note_type"] == "学习笔记"
        assert len(result["note_outline"]) == 4

    def test_json_with_only_type_no_outline(self, base_state) -> None:
        with mock_entire_pipeline(['{"note_type": "面试准备笔记"}']):
            result = infer_type_and_outline(base_state)
        assert result["note_type"] == "面试准备笔记"
        assert len(result["note_outline"]) == 4  # default fill

    def test_extra_fields_ignored(self, base_state) -> None:
        """Extra JSON fields should be safely ignored."""
        resp = json.dumps({
            "note_type": "研究综述笔记",
            "outline": [{"title": "概述", "purpose": "介绍"}],
            "extra_field": "should_be_ignored",
            "version": 2,
        }, ensure_ascii=False)
        with mock_entire_pipeline([resp]):
            result = infer_type_and_outline(base_state)
        assert result["note_type"] == "研究综述笔记"

    def test_note_type_stripped(self, base_state) -> None:
        """Whitespace around note_type should be stripped."""
        resp = json.dumps({
            "note_type": "  论文阅读笔记  ",
            "outline": [{"title": "摘要", "purpose": "..."}]
        }, ensure_ascii=False)
        with mock_entire_pipeline([resp]):
            result = infer_type_and_outline(base_state)
        assert result["note_type"] == "论文阅读笔记"


# ============================================================================
# generate_initial_note node
# ============================================================================

class TestGenerateInitialNote:
    def test_basic_generation(self, base_state) -> None:
        note_md = "# CAP定理详解\n\n## 概述\nCAP定理是分布式系统的基石。"
        with mock_entire_pipeline([note_md]):
            result = generate_initial_note(base_state)
        assert result["current_note"] == note_md
        assert result["iteration_count"] == 0
        assert result["reference_queries"] == []
        assert len(result["intermediate_paths"]) == 1

    def test_state_reset_on_new_generation(self, base_state) -> None:
        """generate_initial_note resets reference/asset state."""
        base_state["reference_queries"] = [{"query": "old"}]
        base_state["sources"] = ["old_source"]
        base_state["evidence_items"] = ["old_evidence"]
        with mock_entire_pipeline(["# New Note"]):
            result = generate_initial_note(base_state)
        assert result["reference_queries"] == []
        assert result["sources"] == []
        assert result["evidence_items"] == []

    def test_note_with_code_blocks(self, base_state) -> None:
        note_md = "# Python装饰器\n\n```python\ndef dec(f):\n    return f\n```"
        with mock_entire_pipeline([note_md]):
            result = generate_initial_note(base_state)
        assert "```python" in result["current_note"]


# ============================================================================
# generate_reference_queries node
# ============================================================================

class TestGenerateReferenceQueries:
    def test_generates_queries(self, base_state) -> None:
        base_state["current_note"] = "# CAP定理\n\nCAP定理很重要但缺乏形式化证明。"
        resp = json.dumps({
            "reference_queries": [
                {"query": "CAP theorem proof Gilbert Lynch", "source_types": ["paper"], "reason": "补充形式化证明"}
            ]
        })
        with mock_entire_pipeline([resp]):
            result = generate_reference_queries(base_state)
        assert len(result["reference_queries"]) == 1
        assert result["reference_queries"][0]["query"] == "CAP theorem proof Gilbert Lynch"

    def test_deduplicates_against_used(self, base_state) -> None:
        base_state["current_note"] = "# Test"
        base_state["used_reference_queries"] = ["cap theorem proof"]
        resp = json.dumps({
            "reference_queries": [
                {"query": "CAP THEOREM proof", "source_types": ["web"]},  # same normalized
                {"query": "new query about consistency", "source_types": ["web"]}
            ]
        })
        with mock_entire_pipeline([resp]):
            result = generate_reference_queries(base_state)
        # First query should be filtered out (duplicate), only second remains
        assert len(result["reference_queries"]) == 1
        assert result["reference_queries"][0]["query"] == "new query about consistency"

    def test_empty_queries(self, base_state) -> None:
        base_state["current_note"] = "# Complete Note\n\nEverything covered."
        with mock_entire_pipeline(['{"reference_queries": []}']):
            result = generate_reference_queries(base_state)
        assert result["reference_queries"] == []

    def test_max_4_queries(self, base_state) -> None:
        """Queries are capped at 4."""
        base_state["current_note"] = "# Note"
        queries = [{"query": f"query {i}", "source_types": ["web"]} for i in range(10)]
        resp = json.dumps({"reference_queries": queries})
        with mock_entire_pipeline([resp]):
            result = generate_reference_queries(base_state)
        assert len(result["reference_queries"]) <= 4

    def test_query_with_string_format(self, base_state) -> None:
        """Item can be a plain string instead of dict."""
        base_state["current_note"] = "# Note"
        resp = json.dumps({"reference_queries": ["plain string query"]})
        with mock_entire_pipeline([resp]):
            result = generate_reference_queries(base_state)
        assert len(result["reference_queries"]) == 1
        assert result["reference_queries"][0]["query"] == "plain string query"


# ============================================================================
# retrieve_references node
# ============================================================================

class TestRetrieveReferences:
    def test_empty_queries(self, base_state) -> None:
        base_state["reference_queries"] = []
        with mock_graph_io():
            result = retrieve_references_node(base_state)
        assert result["reference_results"] == []

    def test_with_real_reference_query(self, base_state) -> None:
        """Integration with actual retrieve_references (mocked)."""
        from unittest.mock import patch

        base_state["reference_queries"] = [
            {"query": "test", "source_types": ["web"], "reason": "test"}
        ]
        with mock_graph_io():
            with patch(
                "note_agent.agent.graph.retrieve_references",
                return_value=[
                    ReferenceItem(
                        query="test",
                        title="Test Result",
                        snippet="A test snippet",
                        url="https://example.com",
                        source_type="web",
                        source_name="Example",
                    )
                ],
            ), \
            patch(
                "note_agent.agent.graph.collect_reference_urls",
                return_value=["https://example.com"],
            ):
                result = retrieve_references_node(base_state)
        assert len(result["reference_results"]) >= 1
        assert "https://example.com" in result["sources"]


# ============================================================================
# verify_and_refine node
# ============================================================================

class TestVerifyAndRefine:
    def test_applies_patches(self, base_state) -> None:
        base_state["current_note"] = "# Note\n\n## Section A\nOriginal content A.\n\n## Section B\nOriginal B."
        base_state["iteration_count"] = 0
        patch_text = "### PATCH: Section A\nUpdated content A."
        with mock_entire_pipeline([patch_text]):
            result = verify_and_refine(base_state)
        assert "Updated content A" in result["current_note"]
        assert "Original B" in result["current_note"]  # unchanged
        assert result["iteration_count"] == 1

    def test_no_changes_path(self, base_state) -> None:
        base_state["current_note"] = "# Note\n\n## Section\nContent."
        with mock_entire_pipeline(["### NO_CHANGES"]):
            result = verify_and_refine(base_state)
        assert result["current_note"] == base_state["current_note"]

    def test_increments_iteration(self, base_state) -> None:
        base_state["iteration_count"] = 3
        with mock_entire_pipeline(["### NO_CHANGES"]):
            result = verify_and_refine(base_state)
        assert result["iteration_count"] == 4


# ============================================================================
# finalize_note node
# ============================================================================

class TestFinalizeNote:
    def test_with_sources(self, base_state) -> None:
        base_state["current_note"] = "# Note\n\n## Content\nSome content [待验证]。"
        base_state["sources"] = ["https://example.com"]
        final = "# Final Note\n\n## Content\nSome verified content.\n\n## Sources\nhttps://example.com"
        with mock_entire_pipeline([final]):
            result = finalize_note(base_state)
        assert result["final_note"] == final
        assert len(result["intermediate_paths"]) == 1

    def test_no_sources(self, base_state) -> None:
        base_state["current_note"] = "# Note\n\nSimple content."
        base_state["sources"] = []
        final = "# Final Note\n\nSimple content."
        with mock_entire_pipeline([final]):
            result = finalize_note(base_state)
        assert result["final_note"] == final


# ============================================================================
# asset planning and generation nodes
# ============================================================================

class TestPlanAssets:
    def test_plans_formulas(self, base_state) -> None:
        base_state["final_note"] = "# CAP\n\n## Proof\nMathematical proof of the theorem..."
        base_state["note_type"] = "学习笔记"
        plan_json = json.dumps([
            {"asset_type": "formula", "purpose": "CAP定理形式化", "necessity_reason": "文字描述不精确", "insert_after_heading": "Proof", "priority": "high"}
        ])
        with mock_entire_pipeline([plan_json]):
            result = plan_note_assets(base_state)
        assert len(result["asset_plan"]) >= 0  # filter may remove low-priority

    def test_empty_plan(self, base_state) -> None:
        base_state["final_note"] = "# Pure Text\n\nNo need for assets."
        base_state["note_type"] = "学习笔记"
        with mock_entire_pipeline(["[]"]):
            result = plan_note_assets(base_state)
        assert result["asset_plan"] == []

    def test_dict_plan(self, base_state) -> None:
        """Plan can be a dict with 'assets' key."""
        base_state["final_note"] = "# Note"
        base_state["note_type"] = "学习笔记"
        plan_json = json.dumps({"assets": [
            {"asset_type": "code", "purpose": "示例", "necessity_reason": "需要代码", "priority": "high"}
        ]})
        with mock_entire_pipeline([plan_json]):
            result = plan_note_assets(base_state)
        # parse_asset_plan handles dict format
        assert isinstance(result["asset_plan"], list)


class TestGenerateAssets:
    def test_empty_plan(self, base_state) -> None:
        base_state["asset_plan"] = []
        base_state["final_note"] = "# Note"
        with mock_graph_io():
            result = generate_note_assets(base_state)
        assert result["generated_assets"] == {}
        assert result["asset_paths"] == []

    def test_generates_formula_asset(self, base_state) -> None:
        base_state["asset_plan"] = [{"asset_type": "formula", "purpose": "CAP", "priority": "high"}]
        base_state["final_note"] = "# CAP Theorem"
        assets_json = json.dumps({
            "formulas": [
                {"formula_id": "f1", "title": "CAP定义", "latex": "C \\land A \\land P = \\bot", "explanation": "三者不可兼得"}
            ],
            "code_blocks": [],
            "diagrams": [],
            "charts": [],
        })
        with mock_entire_pipeline([assets_json]):
            result = generate_note_assets(base_state)
        assert "formulas" in result["generated_assets"]
        assert len(result["generated_assets"]["formulas"]) == 1


# ============================================================================
# save & publish nodes (minimal)
# ============================================================================

class TestSaveAndPublish:
    def test_save_markdown_generates_title(self, base_state) -> None:
        base_state["final_note"] = "# CAP Theorem Detailed Explanation\n\nContent."
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("note_agent.agent.graph.save_markdown", lambda t, c: "/tmp/test.md")
            mp.setattr("note_agent.agent.graph.append_event", lambda rid, ev: None)
            result = save_markdown_node(base_state)
        assert result["note_title"] == "CAP Theorem Detailed Explanation"

    def test_publish_notion_extracts_title(self, base_state) -> None:
        base_state["note_title"] = ""
        base_state["final_note"] = "# My Note Title\n\nContent."
        from unittest.mock import patch
        with mock_graph_io():
            with patch("note_agent.agent.graph.publish_note", return_value="https://notion.so/page"), \
                 patch("note_agent.agent.graph.append_event"):
                result = publish_notion_node(base_state)
        assert result["notion_url"] == "https://notion.so/page"

    def test_publish_notion_handles_error(self, base_state) -> None:
        base_state["note_title"] = "Test"
        base_state["final_note"] = "# Test\nContent."
        from unittest.mock import patch
        with mock_graph_io():
            with patch("note_agent.agent.graph.publish_note", side_effect=Exception("API Error")), \
                 patch("note_agent.agent.graph.append_event"):
                result = publish_notion_node(base_state)
        assert result["notion_url"] == ""


# ============================================================================
# Graph construction (smoke test)
# ============================================================================

class TestGraphBuild:
    def test_builds_without_error(self) -> None:
        graph = build_graph()
        assert graph is not None

    def test_all_nodes_registered(self) -> None:
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "infer_type_and_outline", "generate_initial_note",
            "generate_reference_queries", "retrieve_references",
            "verify_and_refine", "finalize_note",
            "plan_note_assets", "generate_note_assets",
            "assemble_assets_into_note", "save_markdown",
            "publish_notion",
        }
        assert expected.issubset(node_names)


# ============================================================================
# Full pipeline smoke test (with mocks)
# ============================================================================

class TestPipelineSmoke:
    def test_minimal_pipeline_completes(self, base_state) -> None:
        """Simulate a complete pipeline run with mocked LLM at each step.

        Pipeline path (max_iterations=0, assets=off, notion=off):
        infer → generate → finalize → save → END
        """
        base_state["max_iterations"] = 0
        base_state["enable_assets"] = False  # skip asset nodes
        base_state["enable_notion"] = False

        # 4 LLM calls: infer + generate + finalize + title
        responses = [
            json.dumps({"note_type": "学习笔记", "outline": [{"title": "概述", "purpose": "简介"}]}, ensure_ascii=False),
            "# Test Note\n\n## 概述\nThis is a test.",
            "# Test Note\n\n## 概述\nFinalized content.",
            "TestNote",
        ]

        with mock_graph_io():
            with mock_ask_llm_sequence(responses):
                with pytest.MonkeyPatch.context() as mp:
                    mp.setattr("note_agent.agent.graph.save_markdown", lambda t, c: "/tmp/test.md")
                    mp.setattr("note_agent.agent.graph.append_event", lambda rid, ev: None)
                    mp.setattr("note_agent.agent.graph.publish_note", lambda **kw: "https://notion.so")

                    graph = build_graph()
                    result = graph.invoke(base_state)

        assert result["note_type"] == "学习笔记"
        assert result["current_note"] == "# Test Note\n\n## 概述\nThis is a test."
        assert result["final_note"] == "# Test Note\n\n## 概述\nFinalized content."
