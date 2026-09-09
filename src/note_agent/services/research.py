"""Shared retrieval, refinement, and finalization business logic."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from typing import Any

from note_agent.agent.common import apply_patches, dedupe_urls
from note_agent.agent.prompts import finalize_note_prompt, verify_and_refine_prompt
from note_agent.config.llm import ask_llm
from note_agent.config.runtime import max_results_per_source, max_retrieval_workers
from note_agent.domain.models import ReferenceItem, ReferenceQuery
from note_agent.io.events import emit_event
from note_agent.io.storage import save_intermediate_note
from note_agent.retrieval.retriever import (
    collect_reference_urls,
    format_references_for_prompt,
    retrieve_references,
)


def retrieve_reference_materials(
    reference_queries: list[ReferenceQuery],
    *,
    search_api: str,
    retrieve: Callable[..., list[ReferenceItem]] | None = None,
    collect_urls: Callable[[list[ReferenceItem]], list[str]] | None = None,
    emit: Callable[..., Any] | None = None,
) -> tuple[list[ReferenceItem], list[str], list[dict]]:
    """Retrieve references and return results, source URLs, and failures."""
    if not reference_queries:
        return [], [], []

    retrieve = retrieve or retrieve_references
    collect_urls = collect_urls or collect_reference_urls
    emit = emit or emit_event

    def fetch(reference_query: ReferenceQuery) -> tuple[list[ReferenceItem], list[dict]]:
        failures: list[dict] = []
        emit(
            "info",
            text=(
                f"Retrieving references: {reference_query.query}; "
                f"source types: {', '.join(reference_query.source_types)}"
            ),
        )
        try:
            results = retrieve(
                reference_query,
                web_backend=search_api,
                max_results_per_type=max_results_per_source(),
                on_failure=failures.append,
            )
            return results, failures
        except Exception as exc:
            failure = {
                "query": reference_query.query,
                "source_type": ",".join(reference_query.source_types),
                "source_name": search_api,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            emit(
                "warning",
                text=f"Reference retrieval failed: {reference_query.query}: {exc}",
                failed_source=failure,
            )
            return [], [failure]

    results: list[ReferenceItem] = []
    sources: list[str] = []
    failed_sources: list[dict] = []
    with ThreadPoolExecutor(
        max_workers=min(len(reference_queries), max_retrieval_workers())
    ) as pool:
        futures = [pool.submit(fetch, query) for query in reference_queries]
        for future in as_completed(futures):
            query_results, query_failures = future.result()
            results.extend(query_results)
            sources.extend(collect_urls(query_results))
            failed_sources.extend(query_failures)

    source_counts = Counter(
        item.source_name or item.source_type or "unknown"
        for item in results
    )
    source_summary = ", ".join(
        f"{name}:{count}" for name, count in sorted(source_counts.items())
    ) or "none"
    emit(
        "info",
        text=f"Retrieval summary: total={len(results)}; sources={source_summary}",
    )
    if failed_sources:
        emit(
            "warning",
            text=f"Retrieval failures recorded: {len(failed_sources)}",
            failed_sources=failed_sources,
        )

    web_requested = any("web" in query.source_types for query in reference_queries)
    web_result_count = source_counts.get(search_api, 0)
    if not web_requested:
        emit(
            "info",
            text=(
                f"Web backend '{search_api}' was not called because "
                "no generated query requested source_type='web'."
            ),
        )
    elif web_result_count == 0:
        emit(
            "warning",
            text=(
                f"Web backend '{search_api}' was requested but returned "
                "no recorded results; check failed_sources."
            ),
        )

    return results, dedupe_urls(sources), failed_sources


def refine_note_content(
    *,
    raw_input: str,
    current_note: str,
    reference_results: list[ReferenceItem | dict],
    llm_provider: str,
    run_id: str,
    next_iteration: int,
    intermediate_label: str,
    ask: Callable[..., str] | None = None,
    format_references: Callable[[list[ReferenceItem]], str] | None = None,
    apply: Callable[[str, str], str] | None = None,
    save: Callable[[str, str, str], str] | None = None,
    emit: Callable[..., Any] | None = None,
) -> tuple[str, str]:
    """Refine a note with references and persist the intermediate note."""
    ask = ask or ask_llm
    format_references = format_references or format_references_for_prompt
    apply = apply or apply_patches
    save = save or save_intermediate_note
    emit = emit or emit_event

    reference_items = [
        ReferenceItem(**item) if isinstance(item, dict) else item
        for item in reference_results
    ]
    references_text = format_references(reference_items)
    patch_text = ask(
        verify_and_refine_prompt(
            raw_input=raw_input,
            current_note=current_note,
            references=references_text,
        ),
        provider=llm_provider,
        stream=True,
    )
    refined_note = apply(current_note, patch_text)
    intermediate_path = save(
        run_id,
        intermediate_label,
        refined_note,
    )
    emit(
        "info",
        text=f"Refinement complete: iteration={next_iteration}; path={intermediate_path}",
    )
    return refined_note, intermediate_path


def finalize_note_text(
    *,
    current_note: str,
    sources: list,
    llm_provider: str,
    run_id: str,
    ask: Callable[..., str] | None = None,
    save: Callable[[str, str, str], str] | None = None,
    emit: Callable[..., Any] | None = None,
) -> tuple[str, str]:
    """Generate the final text note and persist its intermediate copy."""
    ask = ask or ask_llm
    save = save or save_intermediate_note
    emit = emit or emit_event

    final_note = ask(
        finalize_note_prompt(
            current_note=current_note,
            sources=sources,
        ),
        provider=llm_provider,
        stream=True,
    )
    intermediate_path = save(run_id, "final_text_only", final_note)
    emit("info", text=f"Final note generated: path={intermediate_path}")
    return final_note, intermediate_path
