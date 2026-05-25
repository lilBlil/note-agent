from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


ReferenceType = Literal["web", "paper", "book", "academic", "other"]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


class ReferenceQuery(BaseModel):
    """一次统一参考信息检索请求。"""

    query: str
    source_types: list[ReferenceType] = Field(default_factory=lambda: ["web", "academic"])
    reason: str = ""


class ReferenceItem(BaseModel):
    """统一参考信息结果。覆盖网页、论文、书籍和开放学术资料。"""

    query: str
    title: str = ""
    snippet: str = ""
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    publisher: str = ""
    url: str = ""
    pdf_url: str = ""
    doi: str = ""
    citation_count: int | None = None
    source_type: ReferenceType = "other"
    source_name: str = ""
    # compatibility with previous paper_search.py if it is still present locally
    source: str = ""
    retrieved_at: str = Field(default_factory=now_iso)


# Backward-compatible aliases for older modules. New code should use ReferenceItem.
SearchResultItem = ReferenceItem
PaperSearchResult = ReferenceItem


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