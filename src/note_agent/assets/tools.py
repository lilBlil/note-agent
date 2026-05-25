from __future__ import annotations

import json
import re
from pathlib import Path

from note_agent.assets.schemas import (
    AssetPlanItem,
    ChartBlock,
    CodeBlock,
    FormulaBlock,
    GeneratedAssets,
    MermaidBlock,
)
from note_agent.io.storage import get_assets_dir, write_json


LANGUAGE_EXTENSIONS = {
    "python": "py",
    "py": "py",
    "javascript": "js",
    "js": "js",
    "typescript": "ts",
    "ts": "ts",
    "bash": "sh",
    "shell": "sh",
    "sh": "sh",
    "json": "json",
    "yaml": "yaml",
    "yml": "yml",
    "sql": "sql",
    "html": "html",
    "css": "css",
    "java": "java",
    "cpp": "cpp",
    "c++": "cpp",
    "c": "c",
    "go": "go",
    "rust": "rs",
}


def _extract_json_text(text: str) -> str:
    text = (text or "").strip()

    if text.startswith("```json"):
        text = text[len("```json") :].strip()
    elif text.startswith("```"):
        text = text[len("```") :].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    array_match = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if array_match:
        return array_match.group(0)

    object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if object_match:
        return object_match.group(0)

    return text


def parse_asset_plan(text: str) -> list[AssetPlanItem]:
    try:
        data = json.loads(_extract_json_text(text))
        if isinstance(data, dict):
            data = data.get("assets", [])
        if not isinstance(data, list):
            return []
        return [AssetPlanItem(**item) for item in data if isinstance(item, dict)]
    except Exception:
        return []


def parse_generated_assets(text: str) -> GeneratedAssets:
    try:
        data = json.loads(_extract_json_text(text))
        if not isinstance(data, dict):
            return GeneratedAssets()
        return GeneratedAssets(**data)
    except Exception:
        return GeneratedAssets()


def _safe_name(value: str, default: str) -> str:
    value = (value or "").strip() or default
    value = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:60] or default


def _relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path(".").resolve()).as_posix()
    except Exception:
        return path.as_posix()


def save_formula_assets(run_id: str, formulas: list[FormulaBlock]) -> list[str]:
    if not formulas:
        return []

    assets_dir = get_assets_dir(run_id)
    path = assets_dir / "formula_index.json"
    write_json(path, formulas)
    return [str(path.resolve())]


def save_code_assets(run_id: str, code_blocks: list[CodeBlock]) -> list[str]:
    assets_dir = get_assets_dir(run_id)
    saved_paths = []

    for idx, block in enumerate(code_blocks, start=1):
        code_id = _safe_name(block.code_id, f"code_{idx:03d}")
        lang = (block.language or "text").lower().strip()
        ext = LANGUAGE_EXTENSIONS.get(lang, "txt")
        path = assets_dir / f"{code_id}.{ext}"
        path.write_text(block.code or "", encoding="utf-8")
        saved_paths.append(str(path.resolve()))

    return saved_paths


def save_mermaid_assets(run_id: str, diagrams: list[MermaidBlock]) -> list[str]:
    assets_dir = get_assets_dir(run_id)
    saved_paths = []

    for idx, block in enumerate(diagrams, start=1):
        diagram_id = _safe_name(block.diagram_id, f"diagram_{idx:03d}")
        path = assets_dir / f"{diagram_id}.mmd"
        path.write_text(block.mermaid or "", encoding="utf-8")
        saved_paths.append(str(path.resolve()))

    return saved_paths


def save_chart_specs(run_id: str, charts: list[ChartBlock]) -> list[str]:
    assets_dir = get_assets_dir(run_id)
    saved_paths = []

    for idx, chart in enumerate(charts, start=1):
        chart_id = _safe_name(chart.chart_id, f"chart_{idx:03d}")
        path = assets_dir / f"{chart_id}.json"
        write_json(path, chart)
        saved_paths.append(str(path.resolve()))

    return saved_paths


def render_chart_images(run_id: str, charts: list[ChartBlock]) -> list[str]:
    if not charts:
        return []

    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    assets_dir = get_assets_dir(run_id)
    saved_paths = []

    for idx, chart in enumerate(charts, start=1):
        if not chart.series:
            continue

        chart_id = _safe_name(chart.chart_id, f"chart_{idx:03d}")
        path = assets_dir / f"{chart_id}.png"

        fig, ax = plt.subplots(figsize=(8, 4.5))

        for series in chart.series:
            if not series.x or not series.y:
                continue

            if chart.chart_type == "bar":
                ax.bar(series.x, series.y, label=series.label or None)
            else:
                ax.plot(series.x, series.y, marker="o", label=series.label or None)

        ax.set_title(chart.title or chart_id)
        ax.set_xlabel(chart.x_label or "")
        ax.set_ylabel(chart.y_label or "")

        if any(series.label for series in chart.series):
            ax.legend()

        fig.tight_layout()
        fig.savefig(path, dpi=160)
        plt.close(fig)

        saved_paths.append(str(path.resolve()))

    return saved_paths


def formula_to_markdown(block: FormulaBlock) -> str:
    lines = []

    if block.title:
        lines.append(f"### {block.title}")

    if block.explanation:
        lines.append(block.explanation)

    if block.latex:
        lines.append(f"$$\n{block.latex}\n$$")

    if block.variables:
        lines.append("变量说明：")
        for name, meaning in block.variables.items():
            lines.append(f"- `{name}`：{meaning}")

    return "\n\n".join(lines).strip()


def code_to_markdown(block: CodeBlock) -> str:
    language = block.language or "text"
    title = block.title or block.code_id or "代码示例"
    body = block.code or ""
    purpose = f"\n\n{block.purpose}" if block.purpose else ""

    return f"### {title}{purpose}\n\n```{language}\n{body}\n```".strip()


def mermaid_to_markdown(block: MermaidBlock) -> str:
    title = block.title or block.diagram_id or "流程图"
    caption = f"\n\n{block.caption}" if block.caption else ""

    return f"### {title}{caption}\n\n```mermaid\n{block.mermaid}\n```".strip()


def chart_to_markdown(block: ChartBlock, image_paths: list[str]) -> str:
    title = block.title or block.chart_id or "图表"
    caption = block.caption or ""

    matched_path = ""
    for path in image_paths:
        if block.chart_id and block.chart_id in Path(path).name:
            matched_path = path
            break

    if matched_path:
        rel_path = _relative_to_project(Path(matched_path))
        image_md = f"![{title}]({rel_path})"
    else:
        rows = []
        for series in block.series:
            rows.append(f"- {series.label or 'series'}: x={series.x}, y={series.y}")
        image_md = "\n".join(rows) if rows else "图表数据为空。"

    return f"### {title}\n\n{caption}\n\n{image_md}".strip()


def save_generated_assets(run_id: str, assets: GeneratedAssets) -> list[str]:
    saved_paths = []
    saved_paths.extend(save_formula_assets(run_id, assets.formulas))
    saved_paths.extend(save_code_assets(run_id, assets.code_blocks))
    saved_paths.extend(save_mermaid_assets(run_id, assets.diagrams))
    saved_paths.extend(save_chart_specs(run_id, assets.charts))
    saved_paths.extend(render_chart_images(run_id, assets.charts))
    return saved_paths


def build_asset_markdown_items(
    assets: GeneratedAssets,
    asset_paths: list[str],
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []

    for block in assets.formulas:
        items.append((block.insert_after_heading, formula_to_markdown(block)))

    for block in assets.code_blocks:
        items.append((block.insert_after_heading, code_to_markdown(block)))

    for block in assets.diagrams:
        items.append((block.insert_after_heading, mermaid_to_markdown(block)))

    image_paths = [path for path in asset_paths if path.lower().endswith(".png")]
    for block in assets.charts:
        items.append((block.insert_after_heading, chart_to_markdown(block, image_paths)))

    return [(heading, markdown) for heading, markdown in items if markdown.strip()]


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
            insert_blocks = []
            still_remaining = []

            for target_heading, markdown in remaining:
                target = (target_heading or "").strip().lower()
                if target and target in heading_text:
                    insert_blocks.append(markdown)
                else:
                    still_remaining.append((target_heading, markdown))

            if insert_blocks:
                lines[i + 1 : i + 1] = ["", *insert_blocks, ""]
                i += len(insert_blocks) + 2
                remaining = still_remaining

        i += 1

    if remaining:
        lines.append("")
        lines.append("## 自动生成资产")
        lines.append("")

        for _, markdown in remaining:
            lines.append(markdown)
            lines.append("")

    return "\n".join(lines).strip() + "\n"
