from pathlib import Path

from note_agent.io import markdown


def test_clean_filename_removes_heading_marker_and_invalid_characters():
    filename = markdown.clean_filename('# Bad:/Name* With   Spaces?')

    assert filename == "BadName_With_Spaces"


def test_strip_markdown_fence_removes_wrapper_and_preamble():
    content = """
Here is the note:

```markdown
Preamble text
# Actual Title

Body
```
"""

    assert markdown.strip_markdown_fence(content) == "# Actual Title\n\nBody"


def test_save_markdown_uses_clean_filename_and_strips_content(tmp_path, monkeypatch):
    monkeypatch.setattr(markdown, "NOTES_DIR", tmp_path)

    saved_path = Path(
        markdown.save_markdown("Bad:/Title", "```markdown\n# Title\n\nBody\n```")
    )

    assert saved_path.parent == tmp_path
    assert saved_path.name.startswith("BadTitle_")
    assert saved_path.suffix == ".md"
    assert saved_path.read_text(encoding="utf-8") == "# Title\n\nBody"


def test_normalize_query_collapses_case_and_whitespace():
    assert markdown.normalize_query("  LangGraph   Agent WORKFLOW ") == "langgraph agent workflow"
