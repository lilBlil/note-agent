from datetime import datetime
from typing import Any, Dict, List, Literal, TypedDict
from uuid import uuid4

from pydantic import BaseModel, Field


ReferenceType = Literal["web", "paper", "book", "academic", "other"]

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


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


class ReferenceQuery(BaseModel):
    """一次统一参考信息检索请求。"""

    query: str
    source_types: list[ReferenceType] = Field(default_factory=lambda: ["web", "academic"])
    reason: str = ""


class ReferenceItem(BaseModel):
    """统一参考信息结果，覆盖网页、论文、书籍和开放学术资料。"""

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


# Backward-compatible aliases for older modules.
SearchResultItem = ReferenceItem
PaperSearchResult = ReferenceItem


class RunRecord(BaseModel):
    """一次 Agent 运行的摘要记录。"""

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


class NoteAgentRequest(BaseModel):
    raw_input: str
    # 0 means skip retrieval-verification-refinement iterations.
    max_iterations: int = Field(default=1, ge=0)
    llm_provider: LLMProvider = "deepseek"
    # This is now only the preferred web backend inside unified retrieval.
    search_api: SearchAPI = "duckduckgo"
    # Keep multimodal assets out of the default workflow. Enable only when needed.
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


AssetType = Literal["formula", "code", "mermaid", "chart"]


class AssetPlanItem(BaseModel):
    """LLM 规划出来的一项笔记资产需求。"""

    asset_type: AssetType
    purpose: str = ""
    insert_after_heading: str = ""
    priority: Literal["low", "medium", "high"] = "medium"


class FormulaBlock(BaseModel):
    formula_id: str = ""
    title: str = ""
    latex: str = ""
    explanation: str = ""
    variables: dict[str, str] = Field(default_factory=dict)
    insert_after_heading: str = ""


class CodeBlock(BaseModel):
    code_id: str = ""
    title: str = ""
    language: str = "python"
    code: str = ""
    purpose: str = ""
    insert_after_heading: str = ""


class MermaidBlock(BaseModel):
    diagram_id: str = ""
    title: str = ""
    mermaid: str = ""
    caption: str = ""
    insert_after_heading: str = ""


class ChartSeries(BaseModel):
    label: str = ""
    x: list[Any] = Field(default_factory=list)
    y: list[float] = Field(default_factory=list)


class ChartBlock(BaseModel):
    chart_id: str = ""
    title: str = ""
    chart_type: Literal["line", "bar"] = "line"
    x_label: str = ""
    y_label: str = ""
    series: list[ChartSeries] = Field(default_factory=list)
    caption: str = ""
    insert_after_heading: str = ""


class GeneratedAssets(BaseModel):
    formulas: list[FormulaBlock] = Field(default_factory=list)
    code_blocks: list[CodeBlock] = Field(default_factory=list)
    diagrams: list[MermaidBlock] = Field(default_factory=list)
    charts: list[ChartBlock] = Field(default_factory=list)


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
