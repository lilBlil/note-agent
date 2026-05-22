from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


class SearchResultItem(BaseModel):
    """单条结构化检索结果。"""

    query: str
    title: str = ""
    snippet: str = ""
    url: str = ""
    search_api: str = ""
    retrieved_at: str = Field(default_factory=now_iso)


class RunRecord(BaseModel):
    """一次 Agent 运行的摘要记录。"""

    run_id: str
    status: Literal["running", "success", "error"] = "running"
    raw_input_preview: str = ""
    llm_provider: str = ""
    search_api: str = ""
    max_iterations: int = 0
    saved_path: str = ""
    error: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)