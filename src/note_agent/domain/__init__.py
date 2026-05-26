from note_agent.domain.models import (
    LLMProvider,
    NoteResearchState,
    ReferenceItem,
    ReferenceQuery,
    ReferenceType,
    RunRecord,
    SearchAPI,
    new_run_id,
    now_iso,
)
from note_agent.domain.api import NoteAgentRequest, NoteAgentResponse

# Backward-compatible aliases exposed at the old schemas level.
SearchResultItem = ReferenceItem
PaperSearchResult = ReferenceItem

__all__ = [
    "LLMProvider",
    "NoteAgentRequest",
    "NoteAgentResponse",
    "NoteResearchState",
    "ReferenceItem",
    "ReferenceQuery",
    "ReferenceType",
    "RunRecord",
    "SearchAPI",
    "SearchResultItem",
    "PaperSearchResult",
    "new_run_id",
    "now_iso",
]
