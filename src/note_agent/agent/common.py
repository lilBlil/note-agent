"""Shared helpers for fixed and ReAct note workflows."""

from __future__ import annotations

import json
import re


DEFAULT_OUTLINE = [
    {"title": "主题概述", "purpose": "概括主题背景和核心问题"},
    {"title": "核心概念", "purpose": "整理关键概念"},
    {"title": "实践要点", "purpose": "整理可操作内容"},
    {"title": "后续问题", "purpose": "记录需要继续研究的问题"},
]


def dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        url = (url or "").strip()
        if url and url not in seen:
            result.append(url)
            seen.add(url)
    return result


def parse_note_structure(text: str) -> tuple[str, list]:
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL)
    try:
        data = json.loads(stripped)
    except Exception:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        try:
            data = json.loads(match.group()) if match else {}
        except Exception:
            data = {}

    note_type = str(data.get("note_type") or "学习笔记").strip()
    outline = data.get("outline") or DEFAULT_OUTLINE
    return note_type, outline


def apply_patches(current_note: str, patch_text: str) -> str:
    """Apply LLM-generated PATCH blocks onto the current note."""
    if "### NO_CHANGES" in patch_text:
        return current_note

    section_re = re.compile(r"^(#{1,3} .+)$", re.MULTILINE)
    headings = [(match.group(1), match.start()) for match in section_re.finditer(current_note)]

    def replace_section(note: str, heading: str, new_content: str) -> str:
        idx = note.find(heading)
        if idx == -1:
            return note

        level = len(heading.split(" ")[0])
        after = idx + len(heading)
        next_heading_re = re.compile(r"^#{1," + str(level) + r"} .+", re.MULTILINE)
        match = next_heading_re.search(note, after + 1)
        end = match.start() if match else len(note)

        if level == 1 and match is None:
            subheading = re.compile(r"^#{2,6} .+", re.MULTILINE).search(note, after + 1)
            if subheading:
                end = subheading.start()

        return note[:idx] + new_content.rstrip() + "\n\n" + note[end:]

    patch_block_re = re.compile(
        r"### (PATCH|PATCH_NEW): (.+?)(?: AFTER: (.+?))?\n"
        r"(.*?)(?=### (?:PATCH|PATCH_NEW|NO_CHANGES)|$)",
        re.DOTALL,
    )
    result = current_note
    for match in patch_block_re.finditer(patch_text):
        kind = match.group(1)
        heading = match.group(2).strip()
        after_heading = (match.group(3) or "").strip()
        content = match.group(4).strip()

        if kind == "PATCH":
            full_heading = next((h for h, _ in headings if heading in h), None)
            if full_heading:
                result = replace_section(result, full_heading, f"{full_heading}\n\n{content}")
        elif kind == "PATCH_NEW":
            insert_after = (
                next((h for h, _ in headings if after_heading in h), None)
                if after_heading
                else None
            )
            new_block = f"\n\n## {heading}\n\n{content}"
            if insert_after:
                level = len(insert_after.split(" ")[0])
                after_idx = result.find(insert_after)
                next_match = re.compile(r"^#{1," + str(level) + r"} .+", re.MULTILINE).search(
                    result,
                    after_idx + len(insert_after) + 1,
                )
                pos = next_match.start() if next_match else len(result)
                result = result[:pos] + new_block + "\n\n" + result[pos:]
            else:
                result = result.rstrip() + new_block

    return result
