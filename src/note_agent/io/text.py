"""Text, filename, and markdown utilities."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

NOTES_DIR = Path("notes")


def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())


def clean_filename(title: str) -> str:
    title = title.strip()
    title = re.sub(r"^#+\s*", "", title)
    title = re.sub(r'[\\/:*?"<>|]', "", title)
    title = re.sub(r"\s+", "_", title)
    title = re.sub(r"_+", "_", title)
    title = title.strip("_")
    return title[:40] or "note"


def strip_markdown_fence(content: str) -> str:
    content = content.strip()
    if content.startswith("```markdown"):
        content = content[len("```markdown"):].strip()
    elif content.startswith("```md"):
        content = content[len("```md"):].strip()
    elif content.startswith("```"):
        content = content[len("```"):].strip()
    if content.endswith("```"):
        content = content[:-3].strip()
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            content = "\n".join(lines[i:]).strip()
            break
    return content


def save_markdown(title: str, content: str) -> str:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = clean_filename(title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    content = strip_markdown_fence(content)
    file_path = NOTES_DIR / f"{safe_title}_{timestamp}.md"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path.resolve())
