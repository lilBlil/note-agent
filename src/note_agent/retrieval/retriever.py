"""Reference retrieval orchestration and formatting."""

from __future__ import annotations

from note_agent.domain.models import ReferenceItem, ReferenceQuery
from note_agent.retrieval.sources import retrieve_by_source_type


def retrieve_references(
    reference_query: ReferenceQuery,
    web_backend: str = "duckduckgo",
    max_results_per_type: int = 5,
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
                )
            )
        except Exception:
            continue

    # Deduplicate
    seen: set[str] = set()
    deduped: list[ReferenceItem] = []
    for item in results:
        key = (
            (item.doi or "").lower().strip()
            or (item.url or "").lower().strip()
            or f"{item.title.lower().strip()}::{item.year or ''}::{item.source_name}"
        )
        if key and key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped


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
