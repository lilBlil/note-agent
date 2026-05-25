"""Tests for schemas and model definitions."""

from __future__ import annotations

from note_agent.schemas import (
    AssetPlanItem,
    ChartBlock,
    ChartSeries,
    CodeBlock,
    FormulaBlock,
    GeneratedAssets,
    MermaidBlock,
    NoteAgentRequest,
    NoteAgentResponse,
    ReferenceItem,
    ReferenceQuery,
    RunRecord,
    new_run_id,
    now_iso,
)


class TestNowIso:
    def test_returns_non_empty_string(self) -> None:
        result = now_iso()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_t_separator(self) -> None:
        assert "T" in now_iso()


class TestNewRunId:
    def test_starts_with_run_prefix(self) -> None:
        assert new_run_id().startswith("run_")

    def test_produces_unique_ids(self) -> None:
        ids = {new_run_id() for _ in range(10)}
        assert len(ids) == 10


class TestNoteAgentRequest:
    def test_defaults(self) -> None:
        req = NoteAgentRequest(raw_input="test")
        assert req.max_iterations == 1
        assert req.llm_provider == "deepseek"
        assert req.search_api == "duckduckgo"
        assert req.enable_assets is False

    def test_max_iterations_non_negative(self) -> None:
        req = NoteAgentRequest(raw_input="x", max_iterations=0)
        assert req.max_iterations == 0

    def test_minimal_valid(self) -> None:
        req = NoteAgentRequest(raw_input="hello")
        assert req.raw_input == "hello"


class TestReferenceQuery:
    def test_default_source_types(self) -> None:
        q = ReferenceQuery(query="test query")
        assert "web" in q.source_types
        assert "academic" in q.source_types

    def test_custom_source_types(self) -> None:
        q = ReferenceQuery(query="x", source_types=["paper", "book"])
        assert q.source_types == ["paper", "book"]


class TestReferenceItem:
    def test_defaults(self) -> None:
        item = ReferenceItem(query="q")
        assert item.source_type == "other"
        assert item.authors == []
        assert item.url == ""

    def test_full_construction(self) -> None:
        item = ReferenceItem(
            query="test",
            title="A Paper",
            source_type="paper",
            url="https://example.com",
            year=2024,
        )
        assert item.title == "A Paper"
        assert item.year == 2024


class TestRunRecord:
    def test_default_status_running(self) -> None:
        record = RunRecord(run_id="r1")
        assert record.status == "running"

    def test_full_record(self) -> None:
        record = RunRecord(
            run_id="r1",
            status="success",
            raw_input_preview="hello",
            llm_provider="openai",
            search_api="tavily",
            max_iterations=2,
            saved_path="/tmp/note.md",
        )
        assert record.status == "success"


class TestNoteAgentResponse:
    def test_minimal(self) -> None:
        resp = NoteAgentResponse(
            run_id="r1",
            note_type="research_note",
            final_note="# Note",
            saved_path="/tmp/n.md",
            sources=[],
            iterations=1,
        )
        assert resp.note_type == "research_note"


class TestAssetModels:
    def test_formula_block(self) -> None:
        fb = FormulaBlock(
            formula_id="f1",
            title="Bayes",
            latex=r"P(A|B) = \frac{P(B|A)P(A)}{P(B)}",
            variables={"P(A)": "prior"},
        )
        assert fb.latex.startswith("P(A|B)")

    def test_code_block(self) -> None:
        cb = CodeBlock(code_id="c1", title="sort", language="python", code="sorted(x)")
        assert cb.language == "python"

    def test_mermaid_block(self) -> None:
        mb = MermaidBlock(diagram_id="d1", title="flow", mermaid="graph TD\nA-->B")
        assert "graph TD" in mb.mermaid

    def test_chart_block(self) -> None:
        ch = ChartBlock(
            chart_id="ch1",
            title="trend",
            chart_type="line",
            series=[ChartSeries(label="s1", x=[1, 2], y=[3.0, 4.0])],
        )
        assert len(ch.series) == 1
        assert ch.series[0].y == [3.0, 4.0]

    def test_generated_assets_empty(self) -> None:
        ga = GeneratedAssets()
        assert ga.formulas == []
        assert ga.code_blocks == []

    def test_asset_plan_item(self) -> None:
        item = AssetPlanItem(asset_type="formula", priority="high")
        assert item.asset_type == "formula"
        assert item.priority == "high"
