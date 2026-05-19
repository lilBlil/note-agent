from typing import TypedDict, List, Dict


class NoteResearchState(TypedDict):
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
    search_results: List[str]
    sources: List[str]

    verification_report: str

    final_note: str
    saved_path: str