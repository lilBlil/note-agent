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
    # 0 表示不执行检索-核验-修正迭代；不设置上限。
    max_iterations: int = Field(default=2, ge=0)
    llm_provider: LLMProvider = "deepseek"
    search_api: SearchAPI = "duckduckgo"


class NoteAgentResponse(BaseModel):
    run_id: str
    note_type: str
    final_note: str
    saved_path: str
    sources: list[str]
    used_search_queries: list[str]
    iterations: int
    intermediate_paths: list[str] = Field(default_factory=list)
    run_log_dir: str = ""