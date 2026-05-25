import pytest

from note_agent.io.input_loader import (
    build_combined_input,
    is_valid_url,
    read_text_file,
    read_uploaded_text_file,
)


def test_read_text_file_supports_txt_and_strips_content(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("\nhello\n", encoding="utf-8")

    assert read_text_file(str(path)) == "hello"


def test_read_text_file_rejects_unsupported_suffix(tmp_path):
    path = tmp_path / "note.pdf"
    path.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="暂不支持"):
        read_text_file(str(path))


def test_read_uploaded_text_file_decodes_utf8_and_rejects_empty():
    assert read_uploaded_text_file("note.md", b"  hello  ") == "hello"

    with pytest.raises(ValueError, match="上传文件内容为空"):
        read_uploaded_text_file("note.md", b"   ")


def test_is_valid_url_accepts_http_and_https_only():
    assert is_valid_url("https://example.com")
    assert is_valid_url("http://example.com/path")
    assert not is_valid_url("ftp://example.com")
    assert not is_valid_url("not-a-url")


def test_build_combined_input_preserves_source_sections():
    combined = build_combined_input(
        manual_text="manual",
        file_texts=[("a.md", "file text")],
        webpage_texts=[("https://example.com", "web text")],
    )

    assert "# 用户手动输入" in combined
    assert "# 导入文件：a.md" in combined
    assert "# 导入网页：https://example.com" in combined
    assert combined.count("---") == 2


def test_build_combined_input_rejects_empty_inputs():
    with pytest.raises(ValueError, match="输入内容为空"):
        build_combined_input()
