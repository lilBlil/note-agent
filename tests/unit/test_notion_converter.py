"""Tests for markdown-to-Notion block converter."""

from __future__ import annotations

from note_agent.notion.converter import markdown_to_notion_blocks


class TestMarkdownToNotionBlocks:
    # -- headings ----------------------------------------------------------

    def test_heading_levels(self) -> None:
        md = "# H1\n## H2\n### H3"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 3
        assert blocks[0]["type"] == "heading_1"
        assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "H1"
        assert blocks[1]["type"] == "heading_2"
        assert blocks[1]["heading_2"]["rich_text"][0]["text"]["content"] == "H2"
        assert blocks[2]["type"] == "heading_3"
        assert blocks[2]["heading_3"]["rich_text"][0]["text"]["content"] == "H3"

    def test_h4_falls_back_to_paragraph(self) -> None:
        blocks = markdown_to_notion_blocks("#### H4")
        assert blocks[0]["type"] == "paragraph"

    # -- paragraph ---------------------------------------------------------

    def test_paragraph(self) -> None:
        blocks = markdown_to_notion_blocks("Hello world.")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "paragraph"
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Hello world."

    def test_empty_heading_becomes_paragraph(self) -> None:
        blocks = markdown_to_notion_blocks("# ")
        assert blocks[0]["type"] == "paragraph"

    # -- code blocks -------------------------------------------------------

    def test_code_block(self) -> None:
        md = "```python\nprint('hello')\n```"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "code"
        assert blocks[0]["code"]["language"] == "python"
        assert "print('hello')" in blocks[0]["code"]["rich_text"][0]["text"]["content"]

    def test_code_block_no_language(self) -> None:
        md = "```\nsome code\n```"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["code"]["language"] == "plain text"

    def test_mermaid_treated_as_plain_text(self) -> None:
        md = "```mermaid\ngraph TD\nA-->B\n```"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["code"]["language"] == "plain text"

    def test_code_block_truncated_to_2000_chars(self) -> None:
        long_line = "x" * 2100
        md = f"```\n{long_line}\n```"
        blocks = markdown_to_notion_blocks(md)
        content = blocks[0]["code"]["rich_text"][0]["text"]["content"]
        assert len(content) == 2000

    # -- block formulas ----------------------------------------------------

    def test_formula_block(self) -> None:
        md = "$$\nE = mc^2\n$$"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "equation"
        assert blocks[0]["equation"]["expression"] == "E = mc^2"

    def test_multiline_formula(self) -> None:
        md = "$$\na = b\nc = d\n$$"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["equation"]["expression"] == "a = b\nc = d"

    # -- lists -------------------------------------------------------------

    def test_bullet_list(self) -> None:
        md = "- item one\n- item two\n* item three"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 3
        assert all(b["type"] == "bulleted_list_item" for b in blocks)
        assert blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "item one"
        assert blocks[2]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "item three"

    def test_numbered_list(self) -> None:
        md = "1. first\n2. second\n10. tenth"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 3
        assert all(b["type"] == "numbered_list_item" for b in blocks)
        assert blocks[1]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "second"

    # -- blank lines / empty -----------------------------------------------

    def test_blank_lines_skipped(self) -> None:
        md = "line one\n\n\nline two"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 2
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "line one"
        assert blocks[1]["paragraph"]["rich_text"][0]["text"]["content"] == "line two"

    def test_empty_input(self) -> None:
        blocks = markdown_to_notion_blocks("")
        assert blocks == []

    def test_whitespace_only_input(self) -> None:
        blocks = markdown_to_notion_blocks("  \n  \n  ")
        assert blocks == []

    # -- mixed blocks ------------------------------------------------------

    def test_mixed_content(self) -> None:
        md = "# Title\n\nIntro.\n\n- point one\n- point two\n\n```py\nx = 1\n```\n\nOutro."
        blocks = markdown_to_notion_blocks(md)
        types = [b["type"] for b in blocks]
        assert types == [
            "heading_1",
            "paragraph",
            "bulleted_list_item",
            "bulleted_list_item",
            "code",
            "paragraph",
        ]

    def test_object_block_structure(self) -> None:
        blocks = markdown_to_notion_blocks("text")
        assert blocks[0]["object"] == "block"

    # =====================================================================
    # Inline formatting
    # =====================================================================

    # -- bold --------------------------------------------------------------

    def test_bold_double_asterisk(self) -> None:
        blocks = markdown_to_notion_blocks("this is **bold** text")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert len(rich) == 3
        assert rich[0] == {"type": "text", "text": {"content": "this is "}}
        assert rich[1] == {"type": "text", "text": {"content": "bold"}, "annotations": {"bold": True}}
        assert rich[2] == {"type": "text", "text": {"content": " text"}}

    def test_bold_double_underscore(self) -> None:
        blocks = markdown_to_notion_blocks("also __bold__ here")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[1] == {"type": "text", "text": {"content": "bold"}, "annotations": {"bold": True}}

    # -- italic ------------------------------------------------------------

    def test_italic_asterisk(self) -> None:
        blocks = markdown_to_notion_blocks("some *italic* word")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[1] == {"type": "text", "text": {"content": "italic"}, "annotations": {"italic": True}}

    def test_italic_underscore(self) -> None:
        blocks = markdown_to_notion_blocks("some _italic_ word")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[1] == {"type": "text", "text": {"content": "italic"}, "annotations": {"italic": True}}

    def test_asterisk_with_space_not_italic(self) -> None:
        """* text * with spaces around content is not italic — stays literal."""
        blocks = markdown_to_notion_blocks("this * text * stays")
        rich = blocks[0]["paragraph"]["rich_text"]
        # No segment should have italic annotation
        for seg in rich:
            assert seg.get("annotations", {}).get("italic") is not True

    def test_multiplication_not_italic(self) -> None:
        """2 * 3 * 4 has spaces, should stay literal — no italic applied."""
        blocks = markdown_to_notion_blocks("result is 2 * 3 * 4")
        rich = blocks[0]["paragraph"]["rich_text"]
        for seg in rich:
            assert seg.get("annotations", {}).get("italic") is not True

    # -- inline code -------------------------------------------------------

    def test_inline_code(self) -> None:
        blocks = markdown_to_notion_blocks("use `print()` function")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[1] == {
            "type": "text",
            "text": {"content": "print()"},
            "annotations": {"code": True},
        }

    def test_inline_code_preserves_literal_asterisks(self) -> None:
        """Content inside backticks should NOT be parsed further."""
        blocks = markdown_to_notion_blocks("the `**not bold**` here")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[1]["text"]["content"] == "**not bold**"
        assert rich[1]["annotations"] == {"code": True}
        # Should NOT have bold annotation
        assert "bold" not in rich[1].get("annotations", {})

    # -- strikethrough -----------------------------------------------------

    def test_strikethrough(self) -> None:
        blocks = markdown_to_notion_blocks("this is ~~deleted~~ text")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[1] == {
            "type": "text",
            "text": {"content": "deleted"},
            "annotations": {"strikethrough": True},
        }

    # -- links -------------------------------------------------------------

    def test_link(self) -> None:
        blocks = markdown_to_notion_blocks("see [Google](https://google.com)")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[1] == {
            "type": "text",
            "text": {"content": "Google", "link": {"url": "https://google.com"}},
        }

    # -- inline math -------------------------------------------------------

    def test_inline_math_standalone(self) -> None:
        blocks = markdown_to_notion_blocks("$x = 1$")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert len(rich) == 1
        assert rich[0]["type"] == "equation"
        assert rich[0]["equation"]["expression"] == "x = 1"

    def test_inline_math_with_surrounding_text(self) -> None:
        blocks = markdown_to_notion_blocks("The value is $x = 1$ now.")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert len(rich) == 3
        assert rich[0] == {"type": "text", "text": {"content": "The value is "}}
        assert rich[1] == {"type": "equation", "equation": {"expression": "x = 1"}}
        assert rich[2] == {"type": "text", "text": {"content": " now."}}

    def test_multiple_inline_math(self) -> None:
        blocks = markdown_to_notion_blocks("$a$ and $b$")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[0]["type"] == "equation"
        assert rich[2]["type"] == "equation"

    def test_inline_math_with_superscript(self) -> None:
        blocks = markdown_to_notion_blocks("$V^\\pi(s)$ and $Q^\\pi(s, a)$")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[0]["equation"]["expression"] == "V^\\pi(s)"
        assert rich[2]["equation"]["expression"] == "Q^\\pi(s, a)"

    def test_double_dollar_inline_math(self) -> None:
        """$$...$$ inline display math should NOT include $ in expression."""
        blocks = markdown_to_notion_blocks("The formula $$E=mc^2$$ is famous.")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[1]["type"] == "equation"
        assert rich[1]["equation"]["expression"] == "E=mc^2"
        # Make sure no stray $ appears
        assert "$" not in rich[1]["equation"]["expression"]

    def test_double_dollar_inline_math_with_subscript(self) -> None:
        blocks = markdown_to_notion_blocks("$$V^\\pi(s) = \\mathbb{E}_\\pi[G_t]$$")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert len(rich) == 1
        assert rich[0]["equation"]["expression"] == "V^\\pi(s) = \\mathbb{E}_\\pi[G_t]"

    def test_double_dollar_takes_priority_over_single(self) -> None:
        """$$...$$ should be tried before $...$."""
        blocks = markdown_to_notion_blocks("$$x$$ and $y$")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[0]["equation"]["expression"] == "x"
        assert rich[2]["equation"]["expression"] == "y"

    # -- inline formatting in headings / lists -----------------------------

    def test_inline_math_in_heading(self) -> None:
        blocks = markdown_to_notion_blocks("## 定义 $f(x)$")
        rich = blocks[0]["heading_2"]["rich_text"]
        assert rich[0] == {"type": "text", "text": {"content": "定义 "}}
        assert rich[1] == {"type": "equation", "equation": {"expression": "f(x)"}}

    def test_bold_in_heading(self) -> None:
        blocks = markdown_to_notion_blocks("## 关于 **非平稳性** 的分析")
        rich = blocks[0]["heading_2"]["rich_text"]
        assert rich[1] == {
            "type": "text",
            "text": {"content": "非平稳性"},
            "annotations": {"bold": True},
        }

    def test_inline_math_in_bullet(self) -> None:
        blocks = markdown_to_notion_blocks("- 期望回报 $G_t$")
        rich = blocks[0]["bulleted_list_item"]["rich_text"]
        assert rich[0] == {"type": "text", "text": {"content": "期望回报 "}}
        assert rich[1] == {"type": "equation", "equation": {"expression": "G_t"}}

    def test_inline_code_in_numbered_list(self) -> None:
        blocks = markdown_to_notion_blocks("1. call `setup()` first")
        rich = blocks[0]["numbered_list_item"]["rich_text"]
        assert rich[1]["annotations"] == {"code": True}

    # -- nesting -----------------------------------------------------------

    def test_bold_contains_italic(self) -> None:
        blocks = markdown_to_notion_blocks("**bold *and italic* text**")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert len(rich) == 3
        assert rich[0] == {
            "type": "text", "text": {"content": "bold "}, "annotations": {"bold": True},
        }
        assert rich[1] == {
            "type": "text", "text": {"content": "and italic"},
            "annotations": {"bold": True, "italic": True},
        }
        assert rich[2] == {
            "type": "text", "text": {"content": " text"}, "annotations": {"bold": True},
        }

    def test_strikethrough_contains_code(self) -> None:
        blocks = markdown_to_notion_blocks("~~old `api_v1` gone~~")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[0]["annotations"] == {"strikethrough": True}
        assert rich[1]["annotations"] == {"strikethrough": True, "code": True}
        assert rich[2]["annotations"] == {"strikethrough": True}

    def test_link_contains_bold(self) -> None:
        blocks = markdown_to_notion_blocks("[**important** docs](https://x.com)")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert rich[0]["text"]["content"] == "important"
        assert rich[0]["annotations"] == {"bold": True}
        assert rich[0]["text"]["link"] == {"url": "https://x.com"}

    # -- edge cases --------------------------------------------------------

    def test_text_without_formatting_is_unchanged(self) -> None:
        blocks = markdown_to_notion_blocks("Plain text without math.")
        rich = blocks[0]["paragraph"]["rich_text"]
        assert len(rich) == 1
        assert rich[0] == {"type": "text", "text": {"content": "Plain text without math."}}

    def test_inline_and_block_math_coexist(self) -> None:
        md = "Inline $E=mc^2$ here.\n\n$$\nF = ma\n$$\n\nAfter block."
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["type"] == "paragraph"
        assert blocks[0]["paragraph"]["rich_text"][1]["type"] == "equation"
        assert blocks[1]["type"] == "equation"
        assert blocks[1]["equation"]["expression"] == "F = ma"
        assert blocks[2]["type"] == "paragraph"

    def test_dollar_in_text_not_math(self) -> None:
        """Single $ without closing pair — treated as literal text, not math."""
        blocks = markdown_to_notion_blocks("It costs $5 only.")
        rich = blocks[0]["paragraph"]["rich_text"]
        # No segment should be an equation
        for seg in rich:
            assert seg["type"] == "text"
        # Combined text should contain the dollar sign
        combined = "".join(s["text"]["content"] for s in rich if s["type"] == "text")
        assert "$5" in combined

    def test_no_annotations_key_when_no_formatting(self) -> None:
        """Plain text segments should omit the annotations key entirely."""
        blocks = markdown_to_notion_blocks("hello")
        seg = blocks[0]["paragraph"]["rich_text"][0]
        assert "annotations" not in seg

    # =====================================================================
    # Tables
    # =====================================================================

    def test_simple_table(self) -> None:
        md = "| A | B |\n|----|----|\n| 1 | 2 |\n| 3 | 4 |"
        blocks = markdown_to_notion_blocks(md)
        assert len(blocks) == 1
        table = blocks[0]
        assert table["type"] == "table"
        assert table["table"]["table_width"] == 2
        assert table["table"]["has_column_header"] is True
        assert table["table"]["has_row_header"] is False
        children = table["table"]["children"]
        assert len(children) == 3  # header + 2 data rows
        # Header row
        assert children[0]["type"] == "table_row"
        assert children[0]["table_row"]["cells"][0][0]["text"]["content"] == "A"
        assert children[0]["table_row"]["cells"][1][0]["text"]["content"] == "B"
        # Data rows
        assert children[1]["table_row"]["cells"][0][0]["text"]["content"] == "1"
        assert children[1]["table_row"]["cells"][1][0]["text"]["content"] == "2"

    def test_table_three_columns(self) -> None:
        md = "| X | Y | Z |\n|---|---|---|\n| a | b | c |"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["table"]["table_width"] == 3
        cells = blocks[0]["table"]["children"][1]["table_row"]["cells"]
        assert len(cells) == 3

    def test_table_with_inline_formatting(self) -> None:
        md = "| Name | Desc |\n|------|------|\n| **bold** | `code` |\n| *italic* | $x$ |"
        blocks = markdown_to_notion_blocks(md)
        children = blocks[0]["table"]["children"]
        row1 = children[1]["table_row"]["cells"]
        # First cell: bold
        assert row1[0][0] == {
            "type": "text",
            "text": {"content": "bold"},
            "annotations": {"bold": True},
        }
        # Second cell: code
        assert row1[1][0] == {
            "type": "text",
            "text": {"content": "code"},
            "annotations": {"code": True},
        }
        row2 = children[2]["table_row"]["cells"]
        assert row2[0][0]["annotations"] == {"italic": True}
        assert row2[1][0]["type"] == "equation"

    def test_table_surrounded_by_paragraphs(self) -> None:
        md = "Before.\n\n| K | V |\n|---|---|\n| 1 | 2 |\n\nAfter."
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["type"] == "paragraph"
        assert blocks[1]["type"] == "table"
        assert blocks[2]["type"] == "paragraph"

    def test_pipe_in_text_not_table(self) -> None:
        """A single | in text without a separator row is NOT a table."""
        md = "value | description"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["type"] == "paragraph"

    def test_table_with_separator_colons(self) -> None:
        """Alignment colons in separator should be handled."""
        md = "| L | C | R |\n|:--|:-:|--:|\n| a | b | c |"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["type"] == "table"
        assert blocks[0]["table"]["table_width"] == 3

    # =====================================================================
    # Horizontal rules
    # =====================================================================

    def test_hr_three_dashes(self) -> None:
        blocks = markdown_to_notion_blocks("---")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "divider"
        assert blocks[0]["divider"] == {}

    def test_hr_three_asterisks(self) -> None:
        blocks = markdown_to_notion_blocks("***")
        assert blocks[0]["type"] == "divider"

    def test_hr_three_underscores(self) -> None:
        blocks = markdown_to_notion_blocks("___")
        assert blocks[0]["type"] == "divider"

    def test_hr_with_spaces(self) -> None:
        blocks = markdown_to_notion_blocks("  ---  ")
        assert blocks[0]["type"] == "divider"

    def test_hr_longer_than_three(self) -> None:
        blocks = markdown_to_notion_blocks("-------------------")
        assert blocks[0]["type"] == "divider"

    def test_hr_between_paragraphs(self) -> None:
        md = "Before.\n\n---\n\nAfter."
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["type"] == "paragraph"
        assert blocks[1]["type"] == "divider"
        assert blocks[2]["type"] == "paragraph"

    def test_hr_not_confused_with_table_separator(self) -> None:
        """--- alone is a divider, not a table separator row."""
        blocks = markdown_to_notion_blocks("---")
        assert blocks[0]["type"] == "divider"

    def test_hr_not_confused_with_bullet(self) -> None:
        """- text is a bullet, --- is a divider."""
        md = "- item\n---\n* item"
        blocks = markdown_to_notion_blocks(md)
        assert blocks[0]["type"] == "bulleted_list_item"
        assert blocks[1]["type"] == "divider"
        assert blocks[2]["type"] == "bulleted_list_item"

    def test_hr_in_heading_not_divider(self) -> None:
        """--- inside a heading line is NOT a divider."""
        blocks = markdown_to_notion_blocks("## Section --- continued")
        assert blocks[0]["type"] == "heading_2"
