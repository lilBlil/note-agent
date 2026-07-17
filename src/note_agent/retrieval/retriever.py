"""Reference retrieval orchestration and formatting."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from note_agent.domain.models import ReferenceItem, ReferenceQuery
from note_agent.retrieval.sources import retrieve_by_source_type, dedupe_references
from note_agent.io.events import emit_event

FailureHandler = Callable[[dict[str, Any]], None]


def _record_retrieval_failure(
    *,
    reference_query: ReferenceQuery,
    source_type: str,
    web_backend: str,
    error: Exception,
    on_failure: FailureHandler | None = None,
) -> None:
    source_name = web_backend if source_type == "web" else source_type
    payload = {
        "query": reference_query.query,
        "source_type": source_type,
        "source_name": source_name,
        "error_type": type(error).__name__,
        "error": str(error),
    }
    emit_event(
        "warning",
        text=(
            "Reference retrieval failed: "
            f"{source_name} ({source_type}) for query {reference_query.query}: {error}"
        ),
        failed_source=payload,
    )
    if on_failure:
        on_failure(payload)


def retrieve_references(
    reference_query: ReferenceQuery,
    web_backend: str = "duckduckgo",
    max_results_per_type: int = 5,
    on_failure: FailureHandler | None = None,
) -> list[ReferenceItem]:
    results: list[ReferenceItem] = []
    source_types = reference_query.source_types or ["web", "academic"]

    for source_type in source_types:
        try:
            results.extend(
                retrieve_by_source_type(
                    reference_query.query,
                    source_type,
                    web_backend=web_backend,
                    max_results=max_results_per_type,
                    on_failure=on_failure,
                )
            )
        except Exception as e:
            _record_retrieval_failure(
                reference_query=reference_query,
                source_type=source_type,
                web_backend=web_backend,
                error=e,
                on_failure=on_failure,
            )
            continue

    return dedupe_references(results)


def format_references_for_prompt(results: list[ReferenceItem]) -> str:
    if not results:
        return "无参考信息检索结果。"

    blocks = []
    for idx, item in enumerate(results, start=1):
        authors = ", ".join(item.authors[:6])
        if len(item.authors) > 6:
            authors += ", et al."

        blocks.append(
            "\n".join([
                f"[R{idx}]",
                f"Type: {item.source_type}",
                f"Source: {item.source_name}",
                f"Query: {item.query}",
                f"Title: {item.title}",
                f"Authors: {authors}",
                f"Year: {item.year or ''}",
                f"Venue/Publisher: {item.venue or item.publisher}",
                f"Summary: {item.abstract or item.snippet}",
                f"URL: {item.url}",
                f"PDF: {item.pdf_url}",
                f"DOI/ISBN: {item.doi}",
                f"Citation Count: {item.citation_count if item.citation_count is not None else ''}",
                f"Retrieved At: {item.retrieved_at}",
            ])
        )

    return "\n\n".join(blocks)


def collect_reference_urls(results: list[ReferenceItem]) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for item in results:
        for url in (item.url, item.pdf_url):
            url = (url or "").strip()
            if url and url not in seen:
                urls.append(url)
                seen.add(url)
    return urls
