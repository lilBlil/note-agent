"""High-level publish API for pushing notes to Notion."""

from __future__ import annotations

from note_agent.notion.client import NotionClient
from note_agent.notion.converter import markdown_to_notion_blocks


def publish_note(
    markdown: str,
    title: str,
    parent_page_id: str | None = None,
    token: str | None = None,
) -> str:
    """Convert a markdown note and publish it to Notion. Returns the page URL."""
    client = NotionClient(token=token, parent_page_id=parent_page_id)
    blocks = markdown_to_notion_blocks(markdown)

    # Notion API limits children to 100 blocks per request
    first_batch = blocks[:100]
    remaining = blocks[100:]

    url, page_id = client.create_page(
        title=title, blocks=first_batch, parent_page_id=parent_page_id
    )

    if remaining:
        for i in range(0, len(remaining), 100):
            client.append_blocks(page_id, remaining[i : i + 100])

    return url
