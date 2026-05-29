"""Tests for publish_note orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from note_agent.notion.publish import publish_note


class TestPublishNote:
    def test_creates_page_and_returns_url(self, monkeypatch) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "parent_1")

        mock_client_instance = MagicMock()
        mock_client_instance.create_page.return_value = ("https://notion.so/Page-1", "page_1")

        with patch(
            "note_agent.notion.publish.NotionClient", return_value=mock_client_instance
        ):
            url = publish_note("# Hello\n\nWorld.", "My Note")

        assert url == "https://notion.so/Page-1"
        mock_client_instance.create_page.assert_called_once()
        call_args = mock_client_instance.create_page.call_args
        assert call_args.kwargs["title"] == "My Note"
        assert len(call_args.kwargs["blocks"]) > 0

    def test_splits_into_batches_of_100(self, monkeypatch) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "parent_1")

        mock_client_instance = MagicMock()
        mock_client_instance.create_page.return_value = ("url", "pid")

        blocks = ["line {}".format(i) for i in range(250)]
        markdown = "\n".join(blocks)

        with patch(
            "note_agent.notion.publish.NotionClient", return_value=mock_client_instance
        ):
            publish_note(markdown, "Big Note")

        assert mock_client_instance.append_blocks.call_count == 2
        calls = mock_client_instance.append_blocks.call_args_list
        assert len(calls[0].args[1]) == 100
        assert len(calls[1].args[1]) == 50

    def test_no_append_when_under_100_blocks(self, monkeypatch) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "parent_1")

        mock_client_instance = MagicMock()
        mock_client_instance.create_page.return_value = ("url", "pid")

        with patch(
            "note_agent.notion.publish.NotionClient", return_value=mock_client_instance
        ):
            publish_note("short note", "Short")

        mock_client_instance.append_blocks.assert_not_called()

    def test_passes_explicit_ids(self, monkeypatch) -> None:
        monkeypatch.setenv("NOTION_API_KEY", "secret")
        monkeypatch.delenv("NOTION_PARENT_PAGE_ID", raising=False)

        mock_client_ctor = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.create_page.return_value = ("url", "pid")
        mock_client_ctor.return_value = mock_client_instance

        with patch(
            "note_agent.notion.publish.NotionClient", mock_client_ctor
        ):
            publish_note(
                "# Note",
                "Title",
                parent_page_id="explicit_parent",
                token="explicit_token",
            )

        mock_client_ctor.assert_called_once_with(
            token="explicit_token",
            parent_page_id="explicit_parent",
        )
