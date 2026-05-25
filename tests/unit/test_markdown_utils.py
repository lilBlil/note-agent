"""Tests for markdown utility functions."""

from __future__ import annotations

import pytest

from note_agent.utils import clean_filename, strip_markdown_fence


class TestCleanFilename:
    def test_simple_title(self) -> None:
        assert clean_filename("My Note") == "My_Note"

    def test_strips_heading_prefix(self) -> None:
        assert clean_filename("# Title") == "Title"
        assert clean_filename("## Subtitle") == "Subtitle"

    def test_replaces_spaces_with_underscores(self) -> None:
        assert clean_filename("hello world test") == "hello_world_test"

    def test_removes_special_chars(self) -> None:
        assert clean_filename('test:file*name?"here"') == "testfilenamehere"

    def test_collapses_multiple_underscores(self) -> None:
        assert clean_filename("a   b") == "a_b"

    def test_truncates_to_40_chars(self) -> None:
        long_name = "a" * 50
        result = clean_filename(long_name)
        assert len(result) <= 40

    def test_fallback_for_empty(self) -> None:
        assert clean_filename("") == "note"
        assert clean_filename("###") == "note"

    def test_strips_leading_trailing_underscores(self) -> None:
        assert clean_filename("  hello  ") == "hello"


class TestStripMarkdownFence:
    def test_strips_markdown_fence(self) -> None:
        result = strip_markdown_fence("```markdown\n# Title\nBody\n```")
        assert result == "# Title\nBody"

    def test_strips_md_fence(self) -> None:
        result = strip_markdown_fence("```md\n# Title\n```")
        assert result == "# Title"

    def test_strips_generic_fence(self) -> None:
        result = strip_markdown_fence("```\n# Title\n```")
        assert result == "# Title"

    def test_preserves_unfenced_content(self) -> None:
        content = "# Plain title\n\nBody text."
        result = strip_markdown_fence(content)
        assert result == content

    def test_jumps_to_first_heading(self) -> None:
        content = "intro text\n# Real Title\nBody"
        result = strip_markdown_fence("```markdown\nintro text\n# Real Title\nBody\n```")
        assert result.startswith("# Real Title")

    def test_no_heading_preserves_all(self) -> None:
        result = strip_markdown_fence("```\njust text\nno heading\n```")
        assert result == "just text\nno heading"
