"""Domain models: core data objects, state, and type literals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, TypedDict
from uuid import uuid4

from pydantic import BaseModel, Field

ReferenceType = Literal["web", "paper", "book", "academic", "other"]

LLMProvider = Literal["deepseek", "openai", "qwen", "moonshot", "zhipu", "siliconflow"]

SearchAPI = Literal["duckduckgo", "tavily", "perplexity", "searxng"]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


class ReferenceQuery(BaseModel):
    """A unified reference retrieval request."""

    query: str
    source_types: list[ReferenceType] = Field(default_factory=lambda: ["web", "academic"])
    reason: str = ""


class ReferenceItem(BaseModel):
    """Unified reference result covering web, papers, books, and academic sources."""

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
    source: str = ""
    retrieved_at: str = Field(default_factory=now_iso)


class RunRecord(BaseModel):
    """Summary record for a single agent run."""

    run_id: str
    status: Literal["running", "success", "error"] = "running"
    raw_input_preview: str = ""
    llm_provider: str = ""
    search_api: str = ""
    max_iterations: int = 0
    enable_assets: bool = False
    saved_path: str = ""
    error: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class NoteResearchState(TypedDict):
    run_id: str
    raw_input: str
    max_iterations: int
    iteration_count: int

    llm_provider: str
    search_api: str
    enable_assets: bool

    note_type: str
    note_outline: List[Dict[str, str]]
    current_note: str

    reference_queries: List[Dict[str, Any]]
    used_reference_queries: List[str]
    reference_results: List[ReferenceItem]
    evidence_items: List[ReferenceItem]
    sources: List[str]

    verification_report: str

    final_note: str
    saved_path: str
    intermediate_paths: List[str]

    asset_plan: List[Dict[str, Any]]
    generated_assets: Dict[str, Any]
    asset_paths: List[str]
