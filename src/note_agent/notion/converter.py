"""Convert Markdown note content to Notion API block format."""

from __future__ import annotations

import re
from typing import Any

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_CODE_FENCE_RE = re.compile(r"^```(\w*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
_NUMBERED_RE = re.compile(r"^\d+\.\s+(.+)$")
_FORMULA_BLOCK_RE = re.compile(r"^\$\$$")


def _rich_text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text}}] if text else []


def _heading_block(level: int, text: str) -> dict[str, Any]:
    key = f"heading_{min(level, 3)}"
    return {"object": "block", "type": key, key: {"rich_text": _rich_text(text)}}


def _paragraph_block(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(text)}}


def _code_block(code: str, language: str) -> dict[str, Any]:
    lang = language or "plain text"
    return {
        "object": "block",
        "type": "code",
        "code": {"rich_text": _rich_text(code), "language": lang},
    }


def _bulleted_list_item(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich_text(text)},
    }


def _numbered_list_item(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": _rich_text(text)},
    }


def _equation_block(latex: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "equation",
        "equation": {"expression": latex},
    }


def markdown_to_notion_blocks(markdown: str) -> list[dict[str, Any]]:
    """Parse markdown into a list of Notion block dicts.

    Supports: headings, paragraphs, code blocks, bullet lists,
    numbered lists, and LaTeX equation blocks ($$...$$).
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
            # Notion API limits code blocks to 2000 chars
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

        # Blank line — skip
        if not line.strip():
            i += 1
            continue

        # Paragraph
        blocks.append(_paragraph_block(line))
        i += 1

    return blocks
