from typing import Literal

from pydantic import BaseModel, Field


LLMProvider = Literal[
    "deepseek",
    "openai",
    "qwen",
    "moonshot",
    "zhipu",
    "siliconflow",
]

SearchAPI = Literal[
    "duckduckgo",
    "tavily",
    "perplexity",
    "searxng",
]


class NoteAgentRequest(BaseModel):
    raw_input: str
    # 0 means skip retrieval-verification-refinement iterations.
    max_iterations: int = Field(default=2, ge=0)
    llm_provider: LLMProvider = "deepseek"
    # This is now only the preferred web backend inside unified retrieval.
    search_api: SearchAPI = "duckduckgo"


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