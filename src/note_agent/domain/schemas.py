"""I/O boundary schemas for the agent API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from note_agent.domain.models import LLMProvider, SearchAPI


class NoteAgentRequest(BaseModel):
    raw_input: str
    max_iterations: int = Field(default=1, ge=0)
    llm_provider: LLMProvider = "deepseek"
    search_api: SearchAPI = "duckduckgo"
    enable_assets: bool = False


class NoteAgentResponse(BaseModel):
    run_id: str
    note_type: str
    final_note: str
    saved_path: str
    sources: list[str]
    used_reference_queries: list[str] = Field(default_factory=list)
    iterations: int
    intermediate_paths: list[str] = Field(default_factory=list)
    asset_paths: list[str] = Field(default_factory=list)
    run_log_dir: str = ""
