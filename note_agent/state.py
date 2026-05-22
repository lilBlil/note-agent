from typing import Any, Dict, List, TypedDict

from note_agent.models import ReferenceItem


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

    # v4.0 unified reference retrieval
    reference_queries: List[Dict[str, Any]]
    used_reference_queries: List[str]
    reference_results: List[ReferenceItem]
    evidence_items: List[ReferenceItem]
    sources: List[str]

    verification_report: str

    final_note: str
    saved_path: str
    intermediate_paths: List[str]

    # v4.0 multimodal note assets
    asset_plan: List[Dict[str, Any]]
    generated_assets: Dict[str, Any]
    asset_paths: List[str]