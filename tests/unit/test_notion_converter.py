"""Tests for markdown-to-Notion block converter."""

from __future__ import annotations

from note_agent.notion.converter import markdown_to_notion_blocks


class TestMarkdownToNotionBlocks:
    def test_heading_levels(self) -> None:
        md = "# H1\n## H2\n### H3"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 3
        assert blocks[0]["type"] == "heading_1"
        assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "H1"
        assert blocks[1]["type"] == "heading_2"
        assert blocks[1]["heading_2"]["rich_text"][0]["text"]["content"] == "H2"
        assert blocks[2]["type"] == "heading_3"
        assert blocks[2]["heading_3"]["rich_text"][0]["text"]["content"] == "H3"

    def test_h4_falls_back_to_paragraph(self) -> None:
        """#### is not matched by the 1-3 heading regex, so it becomes a paragraph."""
        blocks = markdown_to_notion_blocks("#### H4")
        assert blocks[0]["type"] == "paragraph"

    def test_paragraph(self) -> None:
        blocks = markdown_to_notion_blocks("Hello world.")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "paragraph"
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Hello world."

    def test_code_block(self) -> None:
        md = "```python\nprint('hello')\n```"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "code"
        assert blocks[0]["code"]["language"] == "python"
        assert "print('hello')" in blocks[0]["code"]["rich_text"][0]["text"]["content"]

    def test_code_block_no_language(self) -> None:
        md = "```\nsome code\n```"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["code"]["language"] == "plain text"

    def test_mermaid_treated_as_plain_text(self) -> None:
        md = "```mermaid\ngraph TD\nA-->B\n```"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["code"]["language"] == "plain text"

    def test_code_block_truncated_to_2000_chars(self) -> None:
        long_line = "x" * 2100
        md = f"```\n{long_line}\n```"
        blocks = markdown_to_notion_blocks(md)
        content = blocks[0]["code"]["rich_text"][0]["text"]["content"]
        assert len(content) == 2000

    def test_formula_block(self) -> None:
        md = "$$\nE = mc^2\n$$"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "equation"
        assert blocks[0]["equation"]["expression"] == "E = mc^2"

    def test_multiline_formula(self) -> None:
        md = "$$\na = b\nc = d\n$$"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["equation"]["expression"] == "a = b\nc = d"

    def test_bullet_list(self) -> None:
        md = "- item one\n- item two\n* item three"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 3
        assert all(b["type"] == "bulleted_list_item" for b in blocks)
        assert blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "item one"
        assert blocks[2]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "item three"

    def test_numbered_list(self) -> None:
        md = "1. first\n2. second\n10. tenth"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 3
        assert all(b["type"] == "numbered_list_item" for b in blocks)
        assert blocks[1]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "second"

    def test_blank_lines_skipped(self) -> None:
        md = "line one\n\n\nline two"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 2
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "line one"
        assert blocks[1]["paragraph"]["rich_text"][0]["text"]["content"] == "line two"

    def test_empty_input(self) -> None:
        blocks = markdown_to_notion_blocks("")
        assert blocks == []

    def test_whitespace_only_input(self) -> None:
        blocks = markdown_to_notion_blocks("  \n  \n  ")
        assert blocks == []

    def test_mixed_content(self) -> None:
        md = "# Title\n\nIntro.\n\n- point one\n- point two\n\n```py\nx = 1\n```\n\nOutro."
        blocks = markdown_to_notion_blocks(md)
        types = [b["type"] for b in blocks]
        assert types == [
            "heading_1",
            "paragraph",
            "bulleted_list_item",
            "bulleted_list_item",
            "code",
            "paragraph",
        ]

    def test_object_block_structure(self) -> None:
        blocks = markdown_to_notion_blocks("text")
        assert blocks[0]["object"] == "block"

    def test_empty_heading_becomes_paragraph(self) -> None:
        """'# ' with no text doesn't match heading regex (.+ requires >=1 char)."""
        blocks = markdown_to_notion_blocks("# ")
        assert blocks[0]["type"] == "paragraph"
