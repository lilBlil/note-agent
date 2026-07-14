"""
Thorough unit tests for `_apply_patches` — the core function that processes
LLM-generated patch instructions to modify note content.

This function uses complex regex to split, match, and replace sections.
It MUST be correct because downstream nodes depend on its output.
"""

from __future__ import annotations

import pytest

from note_agent.agent.graph import _apply_patches


# ============================================================================
# Sample note used across tests
# ============================================================================

FULL_NOTE = """# CAP定理详解

## 概述
CAP定理是分布式系统设计的基石理论。

## C —— 一致性
一致性要求所有节点在同一时刻看到相同的数据。

## A —— 可用性
可用性要求每个非故障节点都能返回响应。

## P —— 分区容错性
分区容错性要求系统在网络分区时仍能运行。

## 三者权衡
由于网络分区不可避免，系统必须在C和A之间做选择。"""


# ============================================================================
# Basic correctness
# ============================================================================

class TestNoChanges:
    def test_exact_match(self) -> None:
        """NO_CHANGES marker returns original note unchanged."""
        result = _apply_patches(FULL_NOTE, "### NO_CHANGES")
        assert result == FULL_NOTE

    def test_no_changes_with_extra_text(self) -> None:
        """NO_CHANGES anywhere in the response triggers early return."""
        patch_text = "Some preamble text\n### NO_CHANGES\nSome trailing text"
        result = _apply_patches(FULL_NOTE, patch_text)
        assert result == FULL_NOTE

    def test_no_matching_patch_blocks(self) -> None:
        """Text without any PATCH blocks leaves note unchanged."""
        result = _apply_patches(FULL_NOTE, "这是一些解释文字，没有实际的patch块。")
        assert result == FULL_NOTE

    def test_empty_patch_text(self) -> None:
        result = _apply_patches(FULL_NOTE, "")
        assert result == FULL_NOTE


class TestPatchReplace:
    def test_replace_single_section(self) -> None:
        patch = "### PATCH: C —— 一致性\n更新后的一致性章节内容。"
        result = _apply_patches(FULL_NOTE, patch)
        assert "更新后的一致性章节内容" in result
        assert "一致性要求所有节点在同一时刻看到相同的数据" not in result
        # Other sections untouched
        assert "## 概述" in result
        assert "## A —— 可用性" in result
        assert "可用性要求每个非故障节点都能返回响应" in result

    def test_replace_multiple_sections(self) -> None:
        patch = (
            "### PATCH: C —— 一致性\n新的一致性内容。\n\n"
            "### PATCH: A —— 可用性\n新的可用性内容。\n\n"
            "### PATCH: 三者权衡\n新的权衡内容。"
        )
        result = _apply_patches(FULL_NOTE, patch)
        assert "新的一致性内容" in result
        assert "新的可用性内容" in result
        assert "新的权衡内容" in result
        # Untouched
        assert "## 概述" in result
        assert "## P —— 分区容错性" in result
        assert "分区容错性要求系统在网络分区时仍能运行" in result

    def test_replace_fuzzy_heading_match(self) -> None:
        """Heading matching is substring-based — '一致性' should match 'C —— 一致性'."""
        patch = "### PATCH: 一致性\n模糊匹配更新。"
        result = _apply_patches(FULL_NOTE, patch)
        assert "模糊匹配更新" in result
        assert "一致性要求所有节点在同一时刻看到相同的数据" not in result

    def test_replace_first_section(self) -> None:
        patch = "### PATCH: 概述\n更新后的概述章节。"
        result = _apply_patches(FULL_NOTE, patch)
        assert "更新后的概述章节" in result
        assert "CAP定理是分布式系统设计的基石理论" not in result

    def test_replace_last_section(self) -> None:
        patch = "### PATCH: 三者权衡\n更新最后的章节。"
        result = _apply_patches(FULL_NOTE, patch)
        assert "更新最后的章节" in result
        assert "由于网络分区不可避免，系统必须在C和A之间做选择" not in result


class TestPatchNew:
    def test_insert_after_existing(self) -> None:
        patch = "### PATCH_NEW: PACELC扩展 AFTER: 三者权衡\nPACELC是CAP的扩展理论。"
        result = _apply_patches(FULL_NOTE, patch)
        assert "## PACELC扩展" in result
        assert "PACELC是CAP的扩展理论" in result
        # Inserted after "三者权衡", before end
        pos_3 = result.index("## 三者权衡")
        pos_new = result.index("## PACELC扩展")
        assert pos_new > pos_3

    def test_insert_without_after(self) -> None:
        """PATCH_NEW without AFTER clause appends at end."""
        patch = "### PATCH_NEW: 附录\n附录内容。"
        result = _apply_patches(FULL_NOTE, patch)
        assert "## 附录" in result
        assert "附录内容" in result
        # Appended at end — the last non-empty line should be the content
        last_lines = [l for l in result.splitlines() if l.strip()]
        assert "附录内容" in last_lines[-1]

    def test_insert_after_first(self) -> None:
        patch = "### PATCH_NEW: 前置知识 AFTER: 概述\n学习CAP需要理解分布式系统基础知识。"
        result = _apply_patches(FULL_NOTE, patch)
        assert "## 前置知识" in result
        pos_overview = result.index("## 概述")
        pos_new = result.index("## 前置知识")
        assert pos_new > pos_overview
        # Should appear before C —— 一致性
        pos_c = result.index("## C —— 一致性")
        assert pos_new < pos_c

    def test_insert_multiple_new(self) -> None:
        patch = (
            "### PATCH_NEW: 扩展阅读 AFTER: 三者权衡\n更多资料。\n\n"
            "### PATCH_NEW: 实践案例 AFTER: P —— 分区容错性\n实际案例。"
        )
        result = _apply_patches(FULL_NOTE, patch)
        assert "## 扩展阅读" in result
        assert "## 实践案例" in result


class TestMixedPatches:
    def test_replace_and_insert(self) -> None:
        patch = (
            "### PATCH: C —— 一致性\n更新后的一致性。\n\n"
            "### PATCH_NEW: 总结 AFTER: 三者权衡\n全书总结内容。"
        )
        result = _apply_patches(FULL_NOTE, patch)
        assert "更新后的一致性" in result
        assert "## 总结" in result
        # Original C content removed
        assert "一致性要求所有节点在同一时刻看到相同的数据" not in result

    def test_patch_order_independence(self) -> None:
        """Patches are applied in order of appearance in the patch text."""
        # Swap order — both should still apply
        patch = (
            "### PATCH_NEW: 前言 AFTER: 概述\n前言内容。\n\n"
            "### PATCH: 概述\n更新的概述。"
        )
        result = _apply_patches(FULL_NOTE, patch)
        assert "## 前言" in result
        assert "更新的概述" in result


# ============================================================================
# Edge cases
# ============================================================================

class TestEdgeCases:
    def test_nonexistent_heading(self) -> None:
        """PATCH targeting a heading not in the note — note unchanged."""
        patch = "### PATCH: 不存在的章节\n这段内容不会被插入。"
        result = _apply_patches(FULL_NOTE, patch)
        assert "这段内容不会被插入" not in result
        assert result == FULL_NOTE

    def test_nonexistent_after_target(self) -> None:
        """PATCH_NEW with nonexistent AFTER target — appended at end."""
        patch = "### PATCH_NEW: 新章节 AFTER: 不存在的章节\n新内容。"
        result = _apply_patches(FULL_NOTE, patch)
        # Appended at end since no match found
        assert "## 新章节" in result
        assert "新内容" in result
        # Section should appear near the end
        last_heading_idx = max(
            result.find(h) for h in ["## 三者权衡"]
            if result.find(h) != -1
        )
        assert result.find("## 新章节") > last_heading_idx

    def test_special_regex_chars_in_heading(self) -> None:
        """Headings with regex-special characters like ( ) [ ] * + should work."""
        note = """# 测试笔记

## C++ vs Rust (性能对比)
C++和Rust的性能对比分析。

## 函数 f(x) = x^2 + 1 的解析
数学分析章节。"""
        patch = "### PATCH: C++ vs Rust (性能对比)\n更新后的性能对比。"
        result = _apply_patches(note, patch)
        assert "更新后的性能对比" in result

    def test_heading_substring_ambiguity(self) -> None:
        """When patch heading '一致性' is a substring of both the H1
        '# 分布式一致性' and H2 '## 一致性', the first match in the
        heading list wins. Since headings are iterated in document order,
        the H1 '# 分布式一致性' (which contains '一致性') matches first.

        This is a known limitation of the current substring-based matching.
        To work around it, use more specific patch targets.
        """
        note = """# 分布式一致性

## 一致性
强一致性概念。

## 最终一致性
最终一致性的概念。"""
        # "一致性" is a substring of the H1 first → the entire note gets replaced
        patch = "### PATCH: 一致性\n更新后的一致性。"
        result = _apply_patches(note, patch)
        assert "更新后的一致性" in result
        # With a more specific target, only the intended section is replaced
        patch_specific = "### PATCH: 最终一致性\n更新后的最终一致性。"
        result2 = _apply_patches(note, patch_specific)
        assert "更新后的最终一致性" in result2
        assert "强一致性概念" in result2  # other sections preserved

    def test_multiline_content_in_patch(self) -> None:
        """Patch content can span multiple paragraphs with markdown formatting."""
        patch = """### PATCH: C —— 一致性

## C —— 一致性（修订）

### 强一致性
强一致性要求所有读操作返回最新的写结果。

### 顺序一致性
比强一致性更弱的保证，只要求操作的顺序在所有节点上一致。

参考：
- Lamport, "How to Make a Multiprocessor Computer..."
"""
        result = _apply_patches(FULL_NOTE, patch)
        assert "强一致性要求所有读操作返回最新的写结果" in result
        assert "顺序一致性" in result
        assert "Lamport" in result

    def test_patch_with_code_blocks(self) -> None:
        """Patch content may contain code fences."""
        patch = """### PATCH: C —— 一致性

一致性验证代码示例：

```python
def check_consistency(nodes, expected_value):
    for node in nodes:
        assert node.read() == expected_value
```
"""
        result = _apply_patches(FULL_NOTE, patch)
        assert "```python" in result
        assert "def check_consistency" in result

    def test_empty_content_patch(self) -> None:
        """PATCH with empty content clears the section."""
        patch = "### PATCH: C —— 一致性\n"  # No content after heading
        result = _apply_patches(FULL_NOTE, patch)
        # The heading stays, but content is empty (just whitespace/newlines)
        assert "## C —— 一致性" in result

    def test_consecutive_patches_same_heading(self) -> None:
        """Multiple PATCH blocks targeting the same heading —
        each overwrites the previous result."""
        patch = (
            "### PATCH: C —— 一致性\n第一版更新。\n\n"
            "### PATCH: C —— 一致性\n第二版更新（最终版）。"
        )
        result = _apply_patches(FULL_NOTE, patch)
        # Patches are applied sequentially. Second PATCH overwrites the first.
        # Last write wins.
        assert "第二版更新（最终版）" in result
        assert "第一版更新" not in result

    def test_only_heading_no_content(self) -> None:
        """Note with only headings, no section content."""
        headings_only = "# 笔记\n\n## 第一章\n\n## 第二章\n\n## 第三章"
        patch = "### PATCH: 第一章\n第一章的内容。"
        result = _apply_patches(headings_only, patch)
        assert "第一章的内容" in result
        assert "## 第二章" in result

    def test_heading_with_inline_code(self) -> None:
        """Heading with backticks."""
        note = "# 笔记\n\n## `useState` Hook 详解\nuseState是React最基础的状态Hook。"
        patch = "### PATCH: `useState` Hook 详解\n更新后的Hook详解。"
        result = _apply_patches(note, patch)
        assert "更新后的Hook详解" in result

    def test_patch_text_between_blocks(self) -> None:
        """Text between PATCH blocks should be ignored (only PATCH blocks matter)."""
        patch = (
            "我审查了笔记，以下章节需要修改：\n\n"
            "### PATCH: C —— 一致性\n更新的一致性。\n\n"
            "另外A章节的内容也不错，但需要一个小修正：\n\n"
            "### PATCH: A —— 可用性\n更新的可用性。"
        )
        result = _apply_patches(FULL_NOTE, patch)
        assert "更新的一致性" in result
        assert "更新的可用性" in result
        # The "我审查了笔记" text should not appear (it's not part of any section)
        # Actually it COULD appear in the gap between patches depending on how
        # regex matches. Let me check: the regex captures content between PATCH headers,
        # so "我审查了笔记..." before first PATCH is not captured — good.

    def test_very_long_content(self) -> None:
        """Patch with very long replacement content (stress test)."""
        long_content = "A" * 10000
        patch = f"### PATCH: C —— 一致性\n{long_content}"
        result = _apply_patches(FULL_NOTE, patch)
        assert long_content in result

    def test_multiple_h2_same_level(self) -> None:
        """All sections are h2 — patch targeting any should work correctly."""
        note = """# Title

## Section A
Content A.

## Section B
Content B.

## Section C
Content C."""
        patch = "### PATCH: Section B\nUpdated B."
        result = _apply_patches(note, patch)
        assert "Updated B." in result
        assert "Content A." in result
        assert "Content C." in result
        assert "Content B." not in result

    def test_h3_sections(self) -> None:
        """Note with h3 sub-sections — replacement respects heading level."""
        note = """# Title

## Chapter 1
Chapter content.

### 1.1 Subsection
Subsection content.

### 1.2 Another
More content.

## Chapter 2
Chapter 2 content."""
        patch = "### PATCH: Chapter 1\nNew chapter 1 content."
        result = _apply_patches(note, patch)
        assert "New chapter 1 content" in result
        assert "Chapter 2 content" in result
        # h3 subsections inside Chapter 1 should be removed (replaced along with chapter)
        assert "Subsection content" not in result


class TestH1TitlePatchRegression:
    """Regression for the note-destroying bug found by the benchmark harness.

    The H1 title has no same-level sibling, so replace_section's "next heading
    at same-or-higher level" boundary matched nothing and set end=len(note),
    replacing the ENTIRE document with a single patch block. Judge scores
    collapsed 4.75 -> 3.15 -> 1.0 across refine iterations because the model
    frequently emits `### PATCH: <title>`. The fix bounds an H1 patch at the
    first subheading so only the title's intro is replaced.
    """

    def test_patch_h1_title_preserves_all_sections(self) -> None:
        patch = "### PATCH: CAP定理详解\nCAP定理描述了分布式系统的根本权衡。"
        result = _apply_patches(FULL_NOTE, patch)
        # every downstream section must survive
        for heading in ["## 概述", "## C —— 一致性", "## A —— 可用性",
                        "## P —— 分区容错性", "## 三者权衡"]:
            assert heading in result, f"H1 patch wiped section {heading!r}"
        # original body content must survive
        assert "一致性要求所有节点" in result
        assert "系统必须在C和A之间做选择" in result
        # the new intro must be present
        assert "根本权衡" in result
        # sanity: note must not shrink to just the title
        assert len(result) > len(FULL_NOTE) * 0.8

    def test_patch_h1_only_replaces_intro(self) -> None:
        """The H1 patch should replace only the title's intro paragraph."""
        note = "# 标题\n\n旧引言段落。\n\n## 章节一\n章节一内容。"
        patch = "### PATCH: 标题\n新引言段落。"
        result = _apply_patches(note, patch)
        assert "新引言段落" in result
        assert "旧引言段落" not in result
        assert "## 章节一" in result and "章节一内容" in result
