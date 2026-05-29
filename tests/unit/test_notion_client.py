"""Tests for NotionClient."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from note_agent.notion.client import NotionClient


@pytest.fixture
def mock_notion_sdk() -> MagicMock:
    """Inject a fake notion_client module so Client is patchable."""
    fake_notion_client = MagicMock()
    fake_notion_client.Client = MagicMock()
    original = sys.modules.get("notion_client")
    sys.modules["notion_client"] = fake_notion_client
    yield fake_notion_client
    if original is None:
        sys.modules.pop("notion_client", None)
    else:
        sys.modules["notion_client"] = original


class TestNotionClientInit:
    def test_uses_token_from_env(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret_abc")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "page_123")

        client = NotionClient()
        assert client._token == "secret_abc"
        assert client._parent_page_id == "page_123"

    def test_uses_explicit_args_over_env(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "env_secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "env_page")

        client = NotionClient(token="arg_secret", parent_page_id="arg_page")
        assert client._token == "arg_secret"
        assert client._parent_page_id == "arg_page"

    def test_raises_if_token_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        with pytest.raises(ValueError, match="NOTION_API_KEY"):
            NotionClient()

    def test_parent_page_id_property(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "page_abc")

        client = NotionClient()
        assert client.parent_page_id == "page_abc"


class TestNotionClientCreatePage:
    def test_returns_url_and_id(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "parent_123")

        client = NotionClient()
        client._client.pages.create.return_value = {
            "url": "https://notion.so/My-Page-abc123",
            "id": "abc-123-def",
        }

        url, page_id = client.create_page("Test", [{"object": "block"}])

        assert url == "https://notion.so/My-Page-abc123"
        assert page_id == "abc-123-def"
        client._client.pages.create.assert_called_once_with(
            parent={"page_id": "parent_123"},
            properties={"title": {"title": [{"text": {"content": "Test"}}]}},
            children=[{"object": "block"}],
        )

    def test_uses_explicit_parent_page_id(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "env_parent")

        client = NotionClient()
        client._client.pages.create.return_value = {"url": "u", "id": "i"}
        client.create_page("T", [], parent_page_id="explicit_parent")

        call_kwargs = client._client.pages.create.call_args.kwargs
        assert call_kwargs["parent"]["page_id"] == "explicit_parent"

    def test_raises_if_no_parent_id(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.delenv("NOTION_PARENT_PAGE_ID", raising=False)

        client = NotionClient()
        with pytest.raises(ValueError, match="parent_page_id"):
            client.create_page("T", [])


class TestNotionClientAppendBlocks:
    def test_calls_sdk_append(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "p")

        client = NotionClient()
        client.append_blocks("page_id_1", [{"object": "block"}])

        client._client.blocks.children.append.assert_called_once_with(
            block_id="page_id_1",
            children=[{"object": "block"}],
        )


class TestNotionClientSearchPages:
    def test_returns_results(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "p")

        client = NotionClient()
        client._client.search.return_value = {"results": [{"id": "1"}, {"id": "2"}]}
        results = client.search_pages("query", limit=5)

        assert len(results) == 2
        client._client.search.assert_called_once_with(
            query="query",
            filter={"property": "object", "value": "page"},
            page_size=5,
        )

    def test_returns_empty_list_when_no_results(self, monkeypatch, mock_notion_sdk) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "p")

        client = NotionClient()
        client._client.search.return_value = {}
        results = client.search_pages("nonexistent")

        assert results == []
