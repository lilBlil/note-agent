from __future__ import annotations

import pytest

from note_agent.domain.models import build_base_state


@pytest.fixture
def base_state() -> dict:
    return build_base_state(
        run_id="run_test",
        raw_input="测试输入",
        max_iterations=2,
        llm_provider="deepseek",
        search_api="duckduckgo",
        enable_assets=True,
        enable_notion=False,
    )
