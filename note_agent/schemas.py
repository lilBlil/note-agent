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
    max_iterations: int = Field(default=2, ge=1, le=5)
    llm_provider: LLMProvider = "deepseek"
    search_api: SearchAPI = "duckduckgo"


class NoteAgentResponse(BaseModel):
    note_type: str
    final_note: str
    saved_path: str
    sources: list[str]
    used_search_queries: list[str]
    iterations: int