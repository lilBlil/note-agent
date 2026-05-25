from __future__ import annotations

import xml.etree.ElementTree as ET

import requests
from ddgs import DDGS

from config.settings import get_settings
from note_agent.io.storage import load_reference_cache, save_reference_cache
from note_agent.models import ReferenceItem, ReferenceQuery, now_iso


SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_URL = "https://export.arxiv.org/api/query"
OPENALEX_URL = "https://api.openalex.org/works"
GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_URL = "https://openlibrary.org/search.json"


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split())


def _dedupe(items: list[ReferenceItem]) -> list[ReferenceItem]:
    seen = set()
    result = []

    for item in items:
        key = (
            (item.doi or "").lower().strip()
            or (item.url or "").lower().strip()
            or f"{item.title.lower().strip()}::{item.year or ''}::{item.source_name}"
        )
        if key and key not in seen:
            result.append(item)
            seen.add(key)

    return result


def _cached(source_name: str, query: str, max_results: int, loader):
    cached = load_reference_cache(source_name=source_name, query=query, max_results=max_results)
    if cached is not None:
        return cached
    results = loader()
    save_reference_cache(
        source_name=source_name,
        query=query,
        max_results=max_results,
        results=results,
    )
    return results


def retrieve_duckduckgo(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "duckduckgo"

    def loader():
        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append(
                    ReferenceItem(
                        query=query,
                        title=item.get("title", "") or "",
                        snippet=item.get("body", "") or "",
                        url=item.get("href", "") or "",
                        source_type="web",
                        source_name=source_name,
                        retrieved_at=now_iso(),
                    )
                )
        return results

    return _cached(source_name, query, max_results, loader)


def retrieve_tavily(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "tavily"

    def loader():
        api_key = get_settings().tavily_api_key
        if not api_key:
            raise ValueError("未找到 TAVILY_API_KEY，请检查 .env 或 env/.env 文件")

        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        return [
            ReferenceItem(
                query=query,
                title=item.get("title", "") or "",
                snippet=item.get("content", "") or "",
                url=item.get("url", "") or "",
                source_type="web",
                source_name=source_name,
                retrieved_at=now_iso(),
            )
            for item in data.get("results", [])
        ]

    return _cached(source_name, query, max_results, loader)


def retrieve_perplexity(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "perplexity"

    def loader():
        api_key = get_settings().perplexity_api_key
        if not api_key:
            raise ValueError("未找到 PERPLEXITY_API_KEY，请检查 .env 或 env/.env 文件")

        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a search assistant. Return factual search-based notes with source URLs.",
                    },
                    {"role": "user", "content": query},
                ],
                "max_tokens": 800,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        citations = [c for c in data.get("citations", []) if isinstance(c, str)]

        if citations:
            return [
                ReferenceItem(
                    query=query,
                    title="Perplexity Search Result",
                    snippet=content,
                    url=url,
                    source_type="web",
                    source_name=source_name,
                    retrieved_at=now_iso(),
                )
                for url in citations[:max_results]
            ]

        return [
            ReferenceItem(
                query=query,
                title="Perplexity Search Result",
                snippet=content,
                source_type="web",
                source_name=source_name,
                retrieved_at=now_iso(),
            )
        ]

    return _cached(source_name, query, max_results, loader)


def retrieve_searxng(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "searxng"

    def loader():
        base_url = get_settings().searxng_url
        if not base_url:
            raise ValueError("未找到 SEARXNG_URL，请检查 .env 或 env/.env 文件")

        response = requests.get(
            f"{base_url.rstrip('/')}/search",
            params={"q": query, "format": "json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        return [
            ReferenceItem(
                query=query,
                title=item.get("title", "") or "",
                snippet=item.get("content", "") or "",
                url=item.get("url", "") or "",
                source_type="web",
                source_name=source_name,
                retrieved_at=now_iso(),
            )
            for item in data.get("results", [])[:max_results]
        ]

    return _cached(source_name, query, max_results, loader)


def retrieve_semantic_scholar(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "semantic_scholar"

    def loader():
        fields = ",".join(
            [
                "title",
                "abstract",
                "authors",
                "year",
                "venue",
                "url",
                "openAccessPdf",
                "externalIds",
                "citationCount",
            ]
        )
        headers = {}
        api_key = get_settings().semantic_scholar_api_key
        if api_key:
            headers["x-api-key"] = api_key

        response = requests.get(
            SEMANTIC_SCHOLAR_URL,
            params={"query": query, "limit": max_results, "fields": fields},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for paper in data.get("data", []) or []:
            external_ids = paper.get("externalIds") or {}
            open_access_pdf = paper.get("openAccessPdf") or {}
            results.append(
                ReferenceItem(
                    query=query,
                    title=_clean_text(paper.get("title")),
                    abstract=_clean_text(paper.get("abstract")),
                    snippet=_clean_text(paper.get("abstract")),
                    authors=[_clean_text(a.get("name")) for a in paper.get("authors", []) if a.get("name")],
                    year=paper.get("year"),
                    venue=_clean_text(paper.get("venue")),
                    url=paper.get("url") or "",
                    pdf_url=open_access_pdf.get("url") or "",
                    doi=external_ids.get("DOI") or "",
                    citation_count=paper.get("citationCount"),
                    source_type="paper",
                    source_name=source_name,
                    retrieved_at=now_iso(),
                )
            )
        return _dedupe(results)

    return _cached(source_name, query, max_results, loader)


def retrieve_arxiv(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "arxiv"

    def loader():
        response = requests.get(
            ARXIV_URL,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
            timeout=30,
        )
        response.raise_for_status()

        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        results = []

        for entry in root.findall("atom:entry", ns):
            title = _clean_text(entry.findtext("atom:title", default="", namespaces=ns))
            abstract = _clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
            published = entry.findtext("atom:published", default="", namespaces=ns)
            year = int(published[:4]) if published[:4].isdigit() else None

            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.findtext("atom:name", default="", namespaces=ns)
                if name:
                    authors.append(_clean_text(name))

            abs_url = ""
            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                href = link.attrib.get("href", "")
                title_attr = link.attrib.get("title", "")
                rel = link.attrib.get("rel", "")
                if rel == "alternate" and href:
                    abs_url = href
                if title_attr == "pdf" and href:
                    pdf_url = href

            results.append(
                ReferenceItem(
                    query=query,
                    title=title,
                    abstract=abstract,
                    snippet=abstract,
                    authors=authors,
                    year=year,
                    venue="arXiv",
                    url=abs_url,
                    pdf_url=pdf_url,
                    doi=entry.findtext("arxiv:doi", default="", namespaces=ns) or "",
                    source_type="paper",
                    source_name=source_name,
                    retrieved_at=now_iso(),
                )
            )
        return _dedupe(results)

    return _cached(source_name, query, max_results, loader)


def retrieve_google_books(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "google_books"

    def loader():
        response = requests.get(
            GOOGLE_BOOKS_URL,
            params={"q": query, "maxResults": max_results},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("items", []) or []:
            info = item.get("volumeInfo") or {}
            year = None
            published = info.get("publishedDate") or ""
            if published[:4].isdigit():
                year = int(published[:4])
            identifiers = info.get("industryIdentifiers") or []
            doi = ""
            for ident in identifiers:
                if ident.get("type") in {"ISBN_10", "ISBN_13"}:
                    doi = ident.get("identifier") or ""
                    break
            results.append(
                ReferenceItem(
                    query=query,
                    title=_clean_text(info.get("title")),
                    snippet=_clean_text(info.get("description")),
                    abstract=_clean_text(info.get("description")),
                    authors=[_clean_text(a) for a in info.get("authors", [])],
                    year=year,
                    publisher=_clean_text(info.get("publisher")),
                    url=info.get("infoLink") or "",
                    doi=doi,
                    source_type="book",
                    source_name=source_name,
                    retrieved_at=now_iso(),
                )
            )
        return _dedupe(results)

    return _cached(source_name, query, max_results, loader)


def retrieve_open_library(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "open_library"

    def loader():
        response = requests.get(
            OPEN_LIBRARY_URL,
            params={"q": query, "limit": max_results},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("docs", []) or []:
            key = item.get("key") or ""
            url = f"https://openlibrary.org{key}" if key else ""
            year = item.get("first_publish_year")
            results.append(
                ReferenceItem(
                    query=query,
                    title=_clean_text(item.get("title")),
                    authors=[_clean_text(a) for a in item.get("author_name", [])],
                    year=year if isinstance(year, int) else None,
                    publisher=", ".join(item.get("publisher", [])[:3]) if item.get("publisher") else "",
                    url=url,
                    doi=(item.get("isbn", [""]) or [""])[0],
                    source_type="book",
                    source_name=source_name,
                    retrieved_at=now_iso(),
                )
            )
        return _dedupe(results)

    return _cached(source_name, query, max_results, loader)


def retrieve_openalex(query: str, max_results: int = 5) -> list[ReferenceItem]:
    source_name = "openalex"

    def loader():
        response = requests.get(
            OPENALEX_URL,
            params={"search": query, "per-page": max_results},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", []) or []:
            authors = []
            for authorship in item.get("authorships", [])[:8]:
                author = authorship.get("author") or {}
                if author.get("display_name"):
                    authors.append(_clean_text(author.get("display_name")))

            primary_location = item.get("primary_location") or {}
            source = primary_location.get("source") or {}
            item_type = (item.get("type") or "").lower()
            source_type = "book" if "book" in item_type else "academic"

            results.append(
                ReferenceItem(
                    query=query,
                    title=_clean_text(item.get("display_name")),
                    authors=authors,
                    year=item.get("publication_year"),
                    venue=_clean_text(source.get("display_name")),
                    url=item.get("id") or item.get("doi") or "",
                    doi=(item.get("doi") or "").replace("https://doi.org/", ""),
                    citation_count=item.get("cited_by_count"),
                    source_type=source_type,
                    source_name=source_name,
                    retrieved_at=now_iso(),
                )
            )
        return _dedupe(results)

    return _cached(source_name, query, max_results, loader)


def retrieve_by_source_type(
    query: str,
    source_type: str,
    web_backend: str = "duckduckgo",
    max_results: int = 5,
) -> list[ReferenceItem]:
    if source_type == "web":
        if web_backend == "tavily":
            return retrieve_tavily(query, max_results=max_results)
        if web_backend == "perplexity":
            return retrieve_perplexity(query, max_results=max_results)
        if web_backend == "searxng":
            return retrieve_searxng(query, max_results=max_results)
        return retrieve_duckduckgo(query, max_results=max_results)

    if source_type == "paper":
        results = []
        for fn in (retrieve_semantic_scholar, retrieve_arxiv):
            try:
                results.extend(fn(query, max_results=max_results))
            except Exception:
                continue
        return _dedupe(results)

    if source_type == "book":
        results = []
        for fn in (retrieve_google_books, retrieve_open_library):
            try:
                results.extend(fn(query, max_results=max_results))
            except Exception:
                continue
        return _dedupe(results)

    if source_type == "academic":
        results = []
        for fn in (retrieve_openalex, retrieve_semantic_scholar):
            try:
                results.extend(fn(query, max_results=max_results))
            except Exception:
                continue
        return _dedupe(results)

    return []


def retrieve_references(
    reference_query: ReferenceQuery,
    web_backend: str = "duckduckgo",
    max_results_per_type: int = 5,
) -> list[ReferenceItem]:
    results = []
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

    return _dedupe(results)


def format_references_for_prompt(results: list[ReferenceItem]) -> str:
    if not results:
        return "无参考信息检索结果。"

    blocks = []
    for idx, item in enumerate(results, start=1):
        authors = ", ".join(item.authors[:6])
        if len(item.authors) > 6:
            authors += ", et al."

        blocks.append(
            "\n".join(
                [
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
                ]
            )
        )

    return "\n\n".join(blocks)


def collect_reference_urls(results: list[ReferenceItem]) -> list[str]:
    seen = set()
    urls = []

    for item in results:
        for url in (item.url, item.pdf_url):
            url = (url or "").strip()
            if url and url not in seen:
                urls.append(url)
                seen.add(url)

    return urls
