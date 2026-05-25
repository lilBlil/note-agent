"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_markdown() -> str:
    return "# Test Title\n\n## Section 1\n\nContent here.\n\n## Section 2\n\nMore content."


@pytest.fixture
def sample_fenced_markdown() -> str:
    return '```markdown\n# Title\n\nBody text.\n```'


@pytest.fixture
def sample_urls() -> list[str]:
    return [
        "https://example.com/article",
        "https://arxiv.org/abs/1234.5678",
    ]


@pytest.fixture
def sample_uploaded_content() -> bytes:
    return b"## Uploaded note\n\nSome content here."
