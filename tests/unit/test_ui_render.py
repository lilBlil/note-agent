"""Tests for UI markdown rendering helpers."""

from __future__ import annotations

from note_agent.ui.render import normalize_latex_delimiters


def test_normalize_latex_display_delimiters() -> None:
    note = "Before\n\\[\nR_{emp}(f)=\\frac{1}{n}\\sum_i L_i\n\\]\nAfter"

    result = normalize_latex_delimiters(note)

    assert "\\[" not in result
    assert "\\]" not in result
    assert "$$\nR_{emp}(f)=\\frac{1}{n}\\sum_i L_i\n$$" in result


def test_normalize_latex_inline_delimiters() -> None:
    note = "输入空间 \\(\\mathcal{X}\\) and output \\(y_i\\)."

    result = normalize_latex_delimiters(note)

    assert result == "输入空间 $\\mathcal{X}$ and output $y_i$."


def test_normalize_latex_skips_code_fences() -> None:
    note = "Text \\(x\\)\n\n```python\nprint('\\(x\\)')\n```\n\n\\[\ny=x\n\\]"

    result = normalize_latex_delimiters(note)

    assert "Text $x$" in result
    assert "```python\nprint('\\(x\\)')\n```" in result
    assert "$$\ny=x\n$$" in result
