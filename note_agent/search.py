from __future__ import annotations

import os

import requests
from ddgs import DDGS

from note_agent.models import SearchResultItem, now_iso
from note_agent.storage import load_search_cache, save_search_cache


def search_duckduckgo(query: str, max_results: int = 5) -> list[SearchResultItem]:
    results = []

    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            results.append(
                SearchResultItem(
                    query=query,
                    title=item.get("title", "") or "",
                    snippet=item.get("body", "") or "",
                    url=item.get("href", "") or "",
                    search_api="duckduckgo",
                    retrieved_at=now_iso(),
                )
            )

    return results


def search_tavily(query: str, max_results: int = 5) -> list[SearchResultItem]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("未找到 TAVILY_API_KEY，请检查 .env 文件")

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
    items = data.get("results", [])

    return [
        SearchResultItem(
            query=query,
            title=item.get("title", "") or "",
            snippet=item.get("content", "") or "",
            url=item.get("url", "") or "",
            search_api="tavily",
            retrieved_at=now_iso(),
        )
        for item in items
    ]


def search_perplexity(query: str, max_results: int = 5) -> list[SearchResultItem]:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError("未找到 PERPLEXITY_API_KEY，请检查 .env 文件")

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
                {
                    "role": "user",
                    "content": query,
                },
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
            SearchResultItem(
                query=query,
                title="Perplexity Search Result",
                snippet=content,
                url=url,
                search_api="perplexity",
                retrieved_at=now_iso(),
            )
            for url in citations[:max_results]
        ]

    return [
        SearchResultItem(
            query=query,
            title="Perplexity Search Result",
            snippet=content,
            url="",
            search_api="perplexity",
            retrieved_at=now_iso(),
        )
    ]


def search_searxng(query: str, max_results: int = 5) -> list[SearchResultItem]:
    base_url = os.getenv("SEARXNG_URL")
    if not base_url:
        raise ValueError("未找到 SEARXNG_URL，请检查 .env 文件")

    response = requests.get(
        f"{base_url.rstrip('/')}/search",
        params={
            "q": query,
            "format": "json",
        },
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    items = data.get("results", [])[:max_results]

    return [
        SearchResultItem(
            query=query,
            title=item.get("title", "") or "",
            snippet=item.get("content", "") or "",
            url=item.get("url", "") or "",
            search_api="searxng",
            retrieved_at=now_iso(),
        )
        for item in items
    ]


def web_search(
    query: str,
    search_api: str = "duckduckgo",
    max_results: int = 5,
    use_cache: bool = True,
) -> list[SearchResultItem]:
    if use_cache:
        cached = load_search_cache(
            search_api=search_api,
            query=query,
            max_results=max_results,
        )
        if cached is not None:
            return cached

    if search_api == "duckduckgo":
        results = search_duckduckgo(query, max_results=max_results)
    elif search_api == "tavily":
        results = search_tavily(query, max_results=max_results)
    elif search_api == "perplexity":
        results = search_perplexity(query, max_results=max_results)
    elif search_api == "searxng":
        results = search_searxng(query, max_results=max_results)
    else:
        raise ValueError(f"不支持的搜索后端：{search_api}")

    save_search_cache(
        search_api=search_api,
        query=query,
        max_results=max_results,
        results=results,
    )

    return results


def format_search_results_for_prompt(results: list[SearchResultItem]) -> str:
    if not results:
        return "无搜索结果。"

    blocks = []

    for idx, item in enumerate(results, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[S{idx}]",
                    f"Query: {item.query}",
                    f"Title: {item.title}",
                    f"Snippet: {item.snippet}",
                    f"URL: {item.url}",
                    f"Search API: {item.search_api}",
                    f"Retrieved At: {item.retrieved_at}",
                ]
            )
        )

    return "\n\n".join(blocks)


def collect_source_urls(results: list[SearchResultItem]) -> list[str]:
    seen = set()
    urls = []

    for item in results:
        url = (item.url or "").strip()
        if url and url not in seen:
            urls.append(url)
            seen.add(url)

    return urls