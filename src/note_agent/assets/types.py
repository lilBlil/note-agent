"""Asset-specific Pydantic models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AssetType = Literal["formula", "code", "mermaid", "chart"]


class AssetPlanItem(BaseModel):
    asset_type: AssetType
    purpose: str = ""
    necessity_reason: str = ""
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
