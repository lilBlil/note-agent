"""Notion API client for publishing notes."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class NotionClient:
    """Thin wrapper around the Notion SDK for note publishing."""

    def __init__(
        self,
        token: str | None = None,
        parent_page_id: str | None = None,
    ):
        try:
            from notion_client import Client
        except ImportError as e:
            raise ImportError(
                "notion-client is required: pip install 'langchain-note-agent[notion]'"
            ) from e

        self._token = token or os.getenv("NOTION_API_KEY", "")
        self._parent_page_id = parent_page_id or os.getenv("NOTION_PARENT_PAGE_ID", "")
        if not self._token:
            raise ValueError("Missing NOTION_API_KEY — check .env")
        self._client = Client(auth=self._token)

    @property
    def parent_page_id(self) -> str:
        return self._parent_page_id

    def create_page(
        self,
        title: str,
        blocks: list[dict[str, Any]],
        parent_page_id: str | None = None,
    ) -> tuple[str, str]:
        """Create a new page under a parent page. Returns (page_url, page_id)."""
        parent_id = parent_page_id or self._parent_page_id
        if not parent_id:
            raise ValueError("No parent_page_id provided and NOTION_PARENT_PAGE_ID not set")

        response = self._client.pages.create(
            parent={"page_id": parent_id},
            properties={"title": {"title": [{"text": {"content": title}}]}},
            children=blocks,
        )
        return response["url"], response["id"]

    def append_blocks(
        self,
        page_id: str,
        blocks: list[dict[str, Any]],
    ) -> None:
        """Append blocks to an existing page."""
        self._client.blocks.children.append(block_id=page_id, children=blocks)

    def search_pages(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search pages in the workspace."""
        response = self._client.search(
            query=query,
            filter={"property": "object", "value": "page"},
            page_size=limit,
        )
        return response.get("results", [])
