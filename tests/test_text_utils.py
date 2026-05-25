"""Tests for text utility functions."""

from __future__ import annotations

from note_agent.utils import normalize_query


class TestNormalizeQuery:
    def test_lowercase(self) -> None:
        assert normalize_query("Hello World") == "hello world"

    def test_strips_whitespace(self) -> None:
        assert normalize_query("  hello  world  ") == "hello world"

    def test_collapses_multiple_spaces(self) -> None:
        assert normalize_query("hello   world") == "hello world"

    def test_handles_tabs_and_newlines(self) -> None:
        assert normalize_query("hello\tworld\nfoo") == "hello world foo"

    def test_mixed_case_and_whitespace(self) -> None:
        assert normalize_query("  LangChain AGENT  ") == "langchain agent"

    def test_empty_string(self) -> None:
        assert normalize_query("") == ""

    def test_only_whitespace(self) -> None:
        assert normalize_query("   \t\n  ") == ""
