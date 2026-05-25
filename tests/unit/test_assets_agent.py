import json

from note_agent.assets.schemas import CodeBlock, FormulaBlock, GeneratedAssets, MermaidBlock
from note_agent.assets.tools import (
    build_asset_markdown_items,
    inject_assets_into_markdown,
    parse_asset_plan,
    parse_generated_assets,
    save_generated_assets,
)


def test_parse_asset_plan_accepts_fenced_json_array():
    text = """```json
[
  {
    "asset_type": "formula",
    "purpose": "explain equation",
    "insert_after_heading": "Math",
    "priority": "high"
  }
]
```"""

    plan = parse_asset_plan(text)

    assert len(plan) == 1
    assert plan[0].asset_type == "formula"
    assert plan[0].insert_after_heading == "Math"


def test_parse_generated_assets_returns_empty_model_for_invalid_json():
    assets = parse_generated_assets("not json")

    assert assets.formulas == []
    assert assets.code_blocks == []
    assert assets.diagrams == []
    assert assets.charts == []


def test_build_asset_markdown_items_and_inject_by_heading():
    assets = GeneratedAssets(
        formulas=[
            FormulaBlock(
                title="Bellman",
                latex="V(s)=max_a Q(s,a)",
                insert_after_heading="Math",
            )
        ],
        code_blocks=[
            CodeBlock(
                title="Example",
                language="python",
                code="print('hi')",
                insert_after_heading="Code",
            )
        ],
        diagrams=[
            MermaidBlock(
                title="Flow",
                mermaid="flowchart TD\nA-->B",
                insert_after_heading="Missing",
            )
        ],
    )

    items = build_asset_markdown_items(assets, asset_paths=[])
    note = "# Title\n\n## Math\n\ntext\n\n## Code\n\ntext"
    injected = inject_assets_into_markdown(note, items)

    assert "### Bellman" in injected
    assert "$$\nV(s)=max_a Q(s,a)\n$$" in injected
    assert "```python\nprint('hi')\n```" in injected
    assert "## 自动生成资产" in injected
    assert "```mermaid\nflowchart TD\nA-->B\n```" in injected


def test_save_generated_assets_writes_expected_files(tmp_path, monkeypatch):
    import note_agent.assets.tools as asset_tools

    monkeypatch.setattr(asset_tools, "get_assets_dir", lambda run_id: tmp_path / run_id)
    monkeypatch.setattr(asset_tools, "render_chart_images", lambda run_id, charts: [])

    assets = GeneratedAssets(
        formulas=[FormulaBlock(title="Formula", latex="x")],
        code_blocks=[CodeBlock(code_id="demo", language="python", code="print(1)")],
        diagrams=[MermaidBlock(diagram_id="flow", mermaid="flowchart TD\nA-->B")],
    )

    paths = save_generated_assets("run_test", assets)
    relative_names = {path.split("run_test/")[-1] for path in paths}

    assert relative_names == {"formula_index.json", "demo.py", "flow.mmd"}
    formula_index = tmp_path / "run_test" / "formula_index.json"
    assert json.loads(formula_index.read_text(encoding="utf-8"))[0]["title"] == "Formula"
