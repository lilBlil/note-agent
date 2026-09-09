from __future__ import annotations

from note_agent.domain.models import ReferenceItem, ReferenceQuery
from note_agent.services import research


def test_retrieval_service_returns_results_sources_and_failures(monkeypatch) -> None:
    item = ReferenceItem(
        query="test query",
        title="Test result",
        url="https://example.com",
        source_type="web",
        source_name="duckduckgo",
    )
    monkeypatch.setattr(research, "emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(research, "retrieve_references", lambda *args, **kwargs: [item])
    monkeypatch.setattr(
        research,
        "collect_reference_urls",
        lambda results: [result.url for result in results],
    )

    results, sources, failures = research.retrieve_reference_materials(
        [ReferenceQuery(query="test query", source_types=["web"])],
        search_api="duckduckgo",
    )

    assert results == [item]
    assert sources == ["https://example.com"]
    assert failures == []


def test_refinement_service_applies_patch_and_preserves_label(monkeypatch) -> None:
    saved = []
    monkeypatch.setattr(research, "emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        research,
        "format_references_for_prompt",
        lambda results: "reference context",
    )
    monkeypatch.setattr(
        research,
        "ask_llm",
        lambda *args, **kwargs: "### PATCH: Section\nUpdated content.",
    )
    monkeypatch.setattr(
        research,
        "save_intermediate_note",
        lambda run_id, label, note: saved.append((run_id, label, note)) or "/tmp/refined.md",
    )

    refined, path = research.refine_note_content(
        raw_input="test input",
        current_note="# Note\n\n## Section\nOriginal content.",
        reference_results=[],
        llm_provider="deepseek",
        run_id="run_test",
        next_iteration=1,
        intermediate_label="iteration_1_refined",
    )

    assert "Updated content." in refined
    assert path == "/tmp/refined.md"
    assert saved == [("run_test", "iteration_1_refined", refined)]


def test_finalization_service_generates_and_saves_final_note(monkeypatch) -> None:
    saved = []
    monkeypatch.setattr(research, "emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(research, "ask_llm", lambda *args, **kwargs: "# Final")
    monkeypatch.setattr(
        research,
        "save_intermediate_note",
        lambda run_id, label, note: saved.append((run_id, label, note)) or "/tmp/final.md",
    )

    final_note, path = research.finalize_note_text(
        current_note="# Draft",
        sources=["https://example.com"],
        llm_provider="deepseek",
        run_id="run_test",
    )

    assert final_note == "# Final"
    assert path == "/tmp/final.md"
    assert saved == [("run_test", "final_text_only", "# Final")]
