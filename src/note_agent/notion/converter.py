"""Convert Markdown note content to Notion API block format.

Supports: headings, paragraphs, code blocks, bullet/numbered lists,
block LaTeX ($$...$$), and inline formatting:
  **bold**  *italic*  `code`  ~~strikethrough~~  [link](url)  $math$
"""

from __future__ import annotations

import re
from typing import Any

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_CODE_FENCE_RE = re.compile(r"^```(\w*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
_NUMBERED_RE = re.compile(r"^\d+\.\s+(.+)$")
_FORMULA_BLOCK_RE = re.compile(r"^\$\$$")

# Inline patterns — tried in order at each position
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_BOLD_UNDER_RE = re.compile(r"__(.+?)__")
_STRIKE_RE = re.compile(r"~~(.+?)~~")
_ITALIC_RE = re.compile(r"\*(?!\s)(.+?)(?<!\s)\*")
_ITALIC_UNDER_RE = re.compile(r"_(?!\s)(.+?)(?<!\s)_")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_INLINE_DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$")
_INLINE_MATH_RE = re.compile(r"\$(.+?)\$")

_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\|([\s\-:]+\|)+\s*$")
_HR_RE = re.compile(r"^\s{0,3}(-{3,}|\*{3,}|_{3,})\s*$")

_ANNOTATION_KEYS = frozenset({"bold", "italic", "strikethrough", "code"})


def _text_segment(content: str, **annotations: bool) -> dict[str, Any]:
    seg: dict[str, Any] = {"type": "text", "text": {"content": content}}
    ann = {k: v for k, v in annotations.items() if k in _ANNOTATION_KEYS and v}
    if ann:
        seg["annotations"] = ann
    return seg


def _mark_annotations(segments: list[dict[str, Any]], **kwargs: bool) -> None:
    for seg in segments:
        if seg["type"] == "text":
            ann = seg.setdefault("annotations", {})
            ann.update({k: v for k, v in kwargs.items() if v})


def _parse_inline_rich_text(text: str) -> list[dict[str, Any]]:
    """Recursively parse inline markdown into Notion rich_text segments."""
    if not text:
        return []

    result: list[dict[str, Any]] = []
    i = 0

    while i < len(text):
        # 1. Inline code `...`
        m = _INLINE_CODE_RE.match(text, pos=i)
        if m:
            result.append(_text_segment(m.group(1), code=True))
            i = m.end()
            continue

        # 2. Bold **...**
        m = _BOLD_RE.match(text, pos=i)
        if m:
            inner = _parse_inline_rich_text(m.group(1))
            _mark_annotations(inner, bold=True)
            result.extend(inner)
            i = m.end()
            continue

        # 3. Bold __...__
        m = _BOLD_UNDER_RE.match(text, pos=i)
        if m:
            inner = _parse_inline_rich_text(m.group(1))
            _mark_annotations(inner, bold=True)
            result.extend(inner)
            i = m.end()
            continue

        # 4. Strikethrough ~~...~~
        m = _STRIKE_RE.match(text, pos=i)
        if m:
            inner = _parse_inline_rich_text(m.group(1))
            _mark_annotations(inner, strikethrough=True)
            result.extend(inner)
            i = m.end()
            continue

        # 5. Italic *...*  (bold already tried; only single * reaches here)
        m = _ITALIC_RE.match(text, pos=i)
        if m:
            inner = _parse_inline_rich_text(m.group(1))
            _mark_annotations(inner, italic=True)
            result.extend(inner)
            i = m.end()
            continue

        # 6. Italic _..._
        m = _ITALIC_UNDER_RE.match(text, pos=i)
        if m:
            inner = _parse_inline_rich_text(m.group(1))
            _mark_annotations(inner, italic=True)
            result.extend(inner)
            i = m.end()
            continue

        # 7. Link [text](url) — recursively parse link text
        m = _LINK_RE.match(text, pos=i)
        if m:
            inner = _parse_inline_rich_text(m.group(1))
            for seg in inner:
                if seg["type"] == "text":
                    seg["text"]["link"] = {"url": m.group(2)}
            result.extend(inner)
            i = m.end()
            continue

        # 8. Inline display math $$...$$
        m = _INLINE_DISPLAY_MATH_RE.match(text, pos=i)
        if m:
            result.append({"type": "equation", "equation": {"expression": m.group(1)}})
            i = m.end()
            continue

        # 9. Inline math $...$
        m = _INLINE_MATH_RE.match(text, pos=i)
        if m:
            result.append({"type": "equation", "equation": {"expression": m.group(1)}})
            i = m.end()
            continue

        # 10. No pattern matched — accumulate plain text until next special char
        nxt = len(text)
        for ch in ("`", "*", "_", "~", "[", "$"):
            idx = text.find(ch, i + 1)  # search after current char
            if idx != -1 and idx < nxt:
                nxt = idx
        # If current char is itself special but unmatched, eat it as literal
        if nxt == i:
            nxt = i + 1
        result.append(_text_segment(text[i:nxt]))
        i = nxt

    return result


# ---------------------------------------------------------------------------
# Block-level helpers
# ---------------------------------------------------------------------------


def _heading_block(level: int, text: str) -> dict[str, Any]:
    key = f"heading_{min(level, 3)}"
    return {"object": "block", "type": key, key: {"rich_text": _parse_inline_rich_text(text)}}


def _paragraph_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _parse_inline_rich_text(text)},
    }


def _code_block(code: str, language: str) -> dict[str, Any]:
    lang = language or "plain text"
    return {
        "object": "block",
        "type": "code",
        "code": {"rich_text": [{"type": "text", "text": {"content": code}}], "language": lang},
    }


def _bulleted_list_item(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _parse_inline_rich_text(text)},
    }


def _numbered_list_item(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": _parse_inline_rich_text(text)},
    }


def _divider_block() -> dict[str, Any]:
    return {"object": "block", "type": "divider", "divider": {}}


def _equation_block(latex: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "equation",
        "equation": {"expression": latex},
    }


def _parse_table_row(line: str) -> list[list[dict[str, Any]]]:
    """Parse a | cell | cell | line into a list of rich_text cell arrays."""
    # Strip leading/trailing pipes, then split by |
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    cells = [c.strip() for c in inner.split("|")]
    return [_parse_inline_rich_text(cell) or [{"type": "text", "text": {"content": ""}}] for cell in cells]


def _table_block(header_line: str, data_lines: list[str]) -> dict[str, Any]:
    """Build a Notion table block from markdown table lines."""
    header_cells = _parse_table_row(header_line)
    width = len(header_cells)

    rows: list[dict[str, Any]] = []
    rows.append({
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": header_cells},
    })
    for dl in data_lines:
        rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": _parse_table_row(dl)},
        })

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": rows,
        },
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def markdown_to_notion_blocks(markdown: str) -> list[dict[str, Any]]:
    """Parse markdown into a list of Notion block dicts.

    Block-level: headings (#–###), code fences (```), block LaTeX ($$…$$),
    bullet/numbered lists, paragraphs.

    Inline: **bold**, *italic*, `code`, ~~strikethrough~~, [links](url), $math$.
    """
    lines = markdown.splitlines()
    blocks: list[dict[str, Any]] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code fence
        code_match = _CODE_FENCE_RE.match(line)
        if code_match:
            language = code_match.group(1)
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_text = "\n".join(code_lines)[:2000]
            if language == "mermaid":
                blocks.append(_code_block(code_text, "plain text"))
            else:
                blocks.append(_code_block(code_text, language))
            i += 1
            continue

        # Formula block $$...$$
        if _FORMULA_BLOCK_RE.match(line.strip()):
            latex_lines: list[str] = []
            i += 1
            while i < len(lines) and not _FORMULA_BLOCK_RE.match(lines[i].strip()):
                latex_lines.append(lines[i])
                i += 1
            blocks.append(_equation_block("\n".join(latex_lines).strip()))
            i += 1
            continue

        # Heading
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append(_heading_block(level, heading_match.group(2)))
            i += 1
            continue

        # Bullet list
        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            blocks.append(_bulleted_list_item(bullet_match.group(1)))
            i += 1
            continue

        # Numbered list
        numbered_match = _NUMBERED_RE.match(line)
        if numbered_match:
            blocks.append(_numbered_list_item(numbered_match.group(1)))
            i += 1
            continue

        # Table — header row followed by separator row
        if (
            _TABLE_ROW_RE.match(line)
            and i + 1 < len(lines)
            and _TABLE_SEP_RE.match(lines[i + 1])
        ):
            header_line = line
            data_lines: list[str] = []
            i += 2  # skip header and separator
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
                data_lines.append(lines[i])
                i += 1
            blocks.append(_table_block(header_line, data_lines))
            continue

        # Horizontal rule: ---, ***, ___
        if _HR_RE.match(line):
            blocks.append(_divider_block())
            i += 1
            continue

        # Blank line — skip
        if not line.strip():
            i += 1
            continue

        # Paragraph
        blocks.append(_paragraph_block(line))
        i += 1

    return blocks
