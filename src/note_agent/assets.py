"""Multimodal asset generation and markdown injection."""

from __future__ import annotations

import json
import re
from pathlib import Path

from note_agent.schemas import (
    AssetPlanItem,
    ChartBlock,
    CodeBlock,
    FormulaBlock,
    GeneratedAssets,
    MermaidBlock,
)
from note_agent.storage import get_assets_dir, write_json

LANGUAGE_EXTENSIONS: dict[str, str] = {
    "python": "py", "py": "py", "javascript": "js", "js": "js",
    "typescript": "ts", "ts": "ts", "bash": "sh", "shell": "sh", "sh": "sh",
    "json": "json", "yaml": "yaml", "yml": "yml", "sql": "sql",
    "html": "html", "css": "css", "java": "java", "cpp": "cpp", "c++": "cpp",
    "c": "c", "go": "go", "rust": "rs",
}


def _extract_json_text(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    m = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if m:
        return m.group(0)
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return m.group(0) if m else text


def parse_asset_plan(text: str) -> list[AssetPlanItem]:
    try:
        data = json.loads(_extract_json_text(text))
        if isinstance(data, dict):
            data = data.get("assets", [])
        return [AssetPlanItem(**item) for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def parse_generated_assets(text: str) -> GeneratedAssets:
    try:
        data = json.loads(_extract_json_text(text))
        return GeneratedAssets(**data) if isinstance(data, dict) else GeneratedAssets()
    except Exception:
        return GeneratedAssets()


def _safe_name(value: str, default: str) -> str:
    value = (value or "").strip() or default
    value = re.sub(r"[^a-zA-Z0-9_\-一-鿿]", "_", value)
    return re.sub(r"_+", "_", value).strip("_")[:60] or default


def _relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path(".").resolve()).as_posix()
    except Exception:
        return path.as_posix()


# -- Save helpers ------------------------------------------------------------


def save_formula_assets(run_id: str, formulas: list[FormulaBlock]) -> list[str]:
    if not formulas:
        return []
    path = get_assets_dir(run_id) / "formula_index.json"
    write_json(path, formulas)
    return [str(path.resolve())]


def save_code_assets(run_id: str, code_blocks: list[CodeBlock]) -> list[str]:
    assets_dir = get_assets_dir(run_id)
    saved: list[str] = []
    for idx, block in enumerate(code_blocks, start=1):
        code_id = _safe_name(block.code_id, f"code_{idx:03d}")
        ext = LANGUAGE_EXTENSIONS.get((block.language or "text").lower().strip(), "txt")
        p = assets_dir / f"{code_id}.{ext}"
        p.write_text(block.code or "", encoding="utf-8")
        saved.append(str(p.resolve()))
    return saved


def save_mermaid_assets(run_id: str, diagrams: list[MermaidBlock]) -> list[str]:
    assets_dir = get_assets_dir(run_id)
    saved: list[str] = []
    for idx, block in enumerate(diagrams, start=1):
        did = _safe_name(block.diagram_id, f"diagram_{idx:03d}")
        p = assets_dir / f"{did}.mmd"
        p.write_text(block.mermaid or "", encoding="utf-8")
        saved.append(str(p.resolve()))
    return saved


def save_chart_specs(run_id: str, charts: list[ChartBlock]) -> list[str]:
    assets_dir = get_assets_dir(run_id)
    saved: list[str] = []
    for idx, chart in enumerate(charts, start=1):
        cid = _safe_name(chart.chart_id, f"chart_{idx:03d}")
        p = assets_dir / f"{cid}.json"
        write_json(p, chart)
        saved.append(str(p.resolve()))
    return saved


def render_chart_images(run_id: str, charts: list[ChartBlock]) -> list[str]:
    if not charts:
        return []
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    assets_dir = get_assets_dir(run_id)
    saved: list[str] = []
    for idx, chart in enumerate(charts, start=1):
        if not chart.series:
            continue
        cid = _safe_name(chart.chart_id, f"chart_{idx:03d}")
        p = assets_dir / f"{cid}.png"
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for series in chart.series:
            if not series.x or not series.y:
                continue
            if chart.chart_type == "bar":
                ax.bar(series.x, series.y, label=series.label or None)
            else:
                ax.plot(series.x, series.y, marker="o", label=series.label or None)
        ax.set_title(chart.title or cid)
        ax.set_xlabel(chart.x_label or "")
        ax.set_ylabel(chart.y_label or "")
        if any(s.label for s in chart.series):
            ax.legend()
        fig.tight_layout()
        fig.savefig(p, dpi=160)
        plt.close(fig)
        saved.append(str(p.resolve()))
    return saved


def save_generated_assets(run_id: str, assets: GeneratedAssets) -> list[str]:
    saved: list[str] = []
    saved.extend(save_formula_assets(run_id, assets.formulas))
    saved.extend(save_code_assets(run_id, assets.code_blocks))
    saved.extend(save_mermaid_assets(run_id, assets.diagrams))
    saved.extend(save_chart_specs(run_id, assets.charts))
    saved.extend(render_chart_images(run_id, assets.charts))
    return saved


# -- Markdown builders -------------------------------------------------------


def formula_to_markdown(block: FormulaBlock) -> str:
    parts: list[str] = []
    if block.title:
        parts.append(f"### {block.title}")
    if block.explanation:
        parts.append(block.explanation)
    if block.latex:
        parts.append(f"$$\n{block.latex}\n$$")
    if block.variables:
        parts.append("变量说明：")
        for name, meaning in block.variables.items():
            parts.append(f"- `{name}`：{meaning}")
    return "\n\n".join(parts).strip()


def code_to_markdown(block: CodeBlock) -> str:
    lang = block.language or "text"
    title = block.title or block.code_id or "代码示例"
    body = block.code or ""
    purpose = f"\n\n{block.purpose}" if block.purpose else ""
    return f"### {title}{purpose}\n\n```{lang}\n{body}\n```".strip()


def mermaid_to_markdown(block: MermaidBlock) -> str:
    title = block.title or block.diagram_id or "流程图"
    caption = f"\n\n{block.caption}" if block.caption else ""
    return f"### {title}{caption}\n\n```mermaid\n{block.mermaid}\n```".strip()


def chart_to_markdown(block: ChartBlock, image_paths: list[str]) -> str:
    title = block.title or block.chart_id or "图表"
    caption = block.caption or ""
    matched = ""
    for p in image_paths:
        if block.chart_id and block.chart_id in Path(p).name:
            matched = p
            break
    if matched:
        rel = _relative_to_project(Path(matched))
        img = f"![{title}]({rel})"
    else:
        rows = [f"- {s.label or 'series'}: x={s.x}, y={s.y}" for s in block.series]
        img = "\n".join(rows) if rows else "图表数据为空。"
    return f"### {title}\n\n{caption}\n\n{img}".strip()


def build_asset_markdown_items(
    assets: GeneratedAssets,
    asset_paths: list[str],
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for b in assets.formulas:
        items.append((b.insert_after_heading, formula_to_markdown(b)))
    for b in assets.code_blocks:
        items.append((b.insert_after_heading, code_to_markdown(b)))
    for b in assets.diagrams:
        items.append((b.insert_after_heading, mermaid_to_markdown(b)))
    image_paths = [p for p in asset_paths if p.lower().endswith(".png")]
    for b in assets.charts:
        items.append((b.insert_after_heading, chart_to_markdown(b, image_paths)))
    return [(h, m) for h, m in items if m.strip()]


def inject_assets_into_markdown(note: str, items: list[tuple[str, str]]) -> str:
    if not items:
        return note

    lines = note.splitlines()
    remaining = list(items)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            heading_text = line.lstrip("#").strip().lower()
            insert: list[str] = []
            still: list[tuple[str, str]] = []
            for target_heading, markdown in remaining:
                target = (target_heading or "").strip().lower()
                if target and target in heading_text:
                    insert.append(markdown)
                else:
                    still.append((target_heading, markdown))
            if insert:
                lines[i + 1 : i + 1] = ["", *insert, ""]
                i += len(insert) + 2
                remaining = still
        i += 1

    if remaining:
        lines.append("")
        lines.append("## 自动生成资产")
        lines.append("")
        for _, markdown in remaining:
            lines.append(markdown)
            lines.append("")

    return "\n".join(lines).strip() + "\n"
