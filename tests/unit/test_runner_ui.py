"""Tests for UI-side runner input assembly."""

from __future__ import annotations

import pytest

from note_agent.io import input_loader
from note_agent.ui import runner_ui


def test_build_combined_input_records_failed_url_without_stopping(monkeypatch) -> None:
    def fake_fetch(url: str) -> str:
        if url.endswith("/bad"):
            raise ValueError("fetch failed")
        return "good page content"

    monkeypatch.setattr(input_loader, "fetch_webpage_text", fake_fetch)
    view: dict = {}

    result = runner_ui.build_combined_input(
        {
            "manual_text": "topic",
            "file_texts": [],
            "urls": ["https://example.com/good", "https://example.com/bad"],
        },
        view,
    )

    assert "topic" in result
    assert "good page content" in result
    assert view["failed_urls"] == [
        {"url": "https://example.com/bad", "error": "fetch failed"}
    ]


def test_build_combined_input_reports_all_failed_urls(monkeypatch) -> None:
    def fake_fetch(url: str) -> str:
        raise ValueError(f"cannot fetch {url}")

    monkeypatch.setattr(input_loader, "fetch_webpage_text", fake_fetch)
    view: dict = {}

    with pytest.raises(ValueError, match="URL"):
        runner_ui.build_combined_input(
            {
                "manual_text": "",
                "file_texts": [],
                "urls": ["https://example.com/bad"],
            },
            view,
        )

    assert view["failed_urls"] == [
        {
            "url": "https://example.com/bad",
            "error": "cannot fetch https://example.com/bad",
        }
    ]
