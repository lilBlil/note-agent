"""Tests for input_loader module."""

from __future__ import annotations

import pytest

from note_agent.io.input_loader import (
    build_combined_input,
    is_valid_url,
    read_uploaded_text_file,
)


class TestIsValidUrl:
    def test_https_url(self) -> None:
        assert is_valid_url("https://example.com/page")

    def test_http_url(self) -> None:
        assert is_valid_url("http://example.com")

    def test_url_with_path_and_query(self) -> None:
        assert is_valid_url("https://example.com/path?key=value")

    def test_rejects_ftp(self) -> None:
        assert not is_valid_url("ftp://files.example.com")

    def test_rejects_missing_scheme(self) -> None:
        assert not is_valid_url("example.com/page")

    def test_rejects_empty_string(self) -> None:
        assert not is_valid_url("")

    def test_rejects_relative_path(self) -> None:
        assert not is_valid_url("/relative/path")


class TestReadUploadedTextFile:
    def test_reads_txt_content(self) -> None:
        result = read_uploaded_text_file("doc.txt", b"Hello world")
        assert result == "Hello world"

    def test_reads_md_content(self) -> None:
        result = read_uploaded_text_file("doc.md", b"# Title\n\nBody")
        assert result == "# Title\n\nBody"

    def test_strips_whitespace(self) -> None:
        result = read_uploaded_text_file("doc.txt", b"  content  \n")
        assert result == "content"

    def test_rejects_unsupported_extension(self) -> None:
        with pytest.raises(ValueError, match="暂不支持"):
            read_uploaded_text_file("doc.pdf", b"data")

    def test_rejects_empty_content(self) -> None:
        with pytest.raises(ValueError, match="内容为空"):
            read_uploaded_text_file("doc.txt", b"   ")

    def test_handles_non_utf8_bytes(self) -> None:
        result = read_uploaded_text_file("doc.txt", b"\xff\xfeinvalid")
        # Should not raise; decode with errors=ignore
        assert isinstance(result, str)


class TestBuildCombinedInput:
    def test_manual_text_only(self) -> None:
        result = build_combined_input(manual_text="hello")
        assert "hello" in result
        assert "用户手动输入" in result

    def test_file_texts(self) -> None:
        result = build_combined_input(file_texts=[("notes.txt", "file content")])
        assert "file content" in result
        assert "notes.txt" in result

    def test_webpage_texts(self) -> None:
        result = build_combined_input(
            webpage_texts=[("https://example.com", "page text")]
        )
        assert "page text" in result
        assert "https://example.com" in result

    def test_combined_all_sources(self) -> None:
        result = build_combined_input(
            manual_text="manual",
            file_texts=[("f.txt", "file")],
            webpage_texts=[("http://a.com", "web")],
        )
        assert "manual" in result
        assert "file" in result
        assert "web" in result
        assert "---" in result  # separator

    def test_skips_empty_file_texts(self) -> None:
        result = build_combined_input(
            file_texts=[("a.txt", "   "), ("b.txt", "valid")]
        )
        assert "a.txt" not in result
        assert "valid" in result

    def test_raises_on_all_empty(self) -> None:
        with pytest.raises(ValueError, match="输入内容为空"):
            build_combined_input()

    def test_raises_on_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="输入内容为空"):
            build_combined_input(manual_text="   ")

    def test_none_iterables_handled(self) -> None:
        result = build_combined_input(manual_text="x", file_texts=None, webpage_texts=None)
        assert "x" in result
