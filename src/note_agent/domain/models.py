"""Domain models: core data objects, state, and type literals."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Sequence, TypedDict
from uuid import uuid4

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

ReferenceType = Literal["web", "paper", "book", "academic", "other"]

LLMProvider = Literal[
    "deepseek",
    "openai",
    "anthropic",
    "qwen",
    "moonshot",
    "zhipu",
    "siliconflow",
]

SearchAPI = Literal["duckduckgo", "tavily", "perplexity", "searxng"]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


def build_base_state(
    *,
    run_id: str,
    raw_input: str,
    max_iterations: int,
    llm_provider: str,
    search_api: str,
    enable_assets: bool,
    enable_notion: bool,
    messages: Sequence[BaseMessage] | None = None,
) -> dict[str, Any]:
    """Build the shared initial graph state for fixed and ReAct runners."""
    return {
        "messages": list(messages or []),
        "run_id": run_id,
        "raw_input": raw_input,
        "max_iterations": max_iterations,
        "iteration_count": 0,
        "llm_provider": llm_provider,
        "search_api": search_api,
        "enable_assets": enable_assets,
        "enable_notion": enable_notion,
        "note_type": "",
        "note_outline": [],
        "current_note": "",
        "reference_queries": [],
        "used_reference_queries": [],
        "reference_results": [],
        "evidence_items": [],
        "sources": [],
        "failed_sources": [],
        "verification_report": "",
        "final_note": "",
        "note_title": "",
        "saved_path": "",
        "notion_url": "",
        "intermediate_paths": [],
        "asset_plan": [],
        "generated_assets": {},
        "asset_paths": [],
        "asset_errors": [],
    }


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
    status: Literal["running", "success", "error", "cancelled"] = "running"
    mode: str = "fixed"
    raw_input_preview: str = ""
    llm_provider: str = ""
    search_api: str = ""
    max_iterations: int = 0
    enable_assets: bool = False
    enable_notion: bool = False
    notion_url: str = ""
    saved_path: str = ""
    error: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class NoteResearchState(TypedDict):
    """State for ReAct-based note research agent."""

    # Core agent state
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Run metadata
    run_id: str
    raw_input: str
    max_iterations: int
    iteration_count: int

    # Configuration
    llm_provider: str
    search_api: str
    enable_assets: bool
    enable_notion: bool

    # Note structure
    note_type: str
    note_outline: list[dict[str, str]]
    current_note: str

    # Reference and search state
    reference_queries: list[dict[str, Any]]
    used_reference_queries: list[str]
    reference_results: list[ReferenceItem]
    evidence_items: list[ReferenceItem]
    sources: list[str]
    failed_sources: list[dict[str, Any]]

    # Verification
    verification_report: str

    # Final output
    final_note: str
    note_title: str
    notion_url: str
    saved_path: str
    intermediate_paths: list[str]

    # Assets
    asset_plan: list[dict[str, Any]]
    generated_assets: dict[str, Any]
    asset_paths: list[str]
    asset_errors: list[dict[str, Any]]
