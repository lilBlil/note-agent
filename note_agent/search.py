import os
from typing import Tuple

import requests
from ddgs import DDGS


def search_duckduckgo(query: str, max_results: int = 5) -> Tuple[str, list[str]]:
    results = []
    sources = []

    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            title = item.get("title", "")
            body = item.get("body", "")
            href = item.get("href", "")

            results.append(f"标题：{title}\n摘要：{body}\n链接：{href}")

            if href:
                sources.append(href)

    return "\n\n".join(results), sources


def search_tavily(query: str, max_results: int = 5) -> Tuple[str, list[str]]:
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

    results = []
    sources = []

    for item in items:
        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")

        results.append(f"标题：{title}\n摘要：{content}\n链接：{url}")

        if url:
            sources.append(url)

    return "\n\n".join(results), sources


def search_perplexity(query: str, max_results: int = 5) -> Tuple[str, list[str]]:
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

    # Perplexity API 返回结构可能随版本变化，sources 先从 citations 尝试读取
    citations = data.get("citations", [])
    sources = [c for c in citations if isinstance(c, str)]

    return content, sources


def search_searxng(query: str, max_results: int = 5) -> Tuple[str, list[str]]:
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

    results = []
    sources = []

    for item in items:
        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")

        results.append(f"标题：{title}\n摘要：{content}\n链接：{url}")

        if url:
            sources.append(url)

    return "\n\n".join(results), sources


def web_search(query: str, search_api: str = "duckduckgo", max_results: int = 5) -> Tuple[str, list[str]]:
    if search_api == "duckduckgo":
        return search_duckduckgo(query, max_results=max_results)

    if search_api == "tavily":
        return search_tavily(query, max_results=max_results)

    if search_api == "perplexity":
        return search_perplexity(query, max_results=max_results)

    if search_api == "searxng":
        return search_searxng(query, max_results=max_results)

    raise ValueError(f"不支持的搜索后端：{search_api}")