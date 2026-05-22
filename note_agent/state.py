from typing import TypedDict, List, Dict

from note_agent.models import SearchResultItem


class NoteResearchState(TypedDict):
    run_id: str
    raw_input: str
    max_iterations: int
    iteration_count: int

    llm_provider: str
    search_api: str

    note_type: str
    note_outline: List[Dict[str, str]]
    current_note: str

    search_queries: List[str]
    used_search_queries: List[str]

    # 当前轮结构化搜索结果
    search_results: List[SearchResultItem]
    # 全部迭代累计证据
    evidence_items: List[SearchResultItem]
    sources: List[str]

    verification_report: str

    final_note: str
    saved_path: str
    intermediate_paths: List[str]