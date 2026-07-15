"""Session view-model and the fixed-pipeline stage map.

`RunView` is the single source of truth the render layer draws from, both
during live streaming and on later reruns. The agent workflow is never
touched here — we only fold its public events into view state.
"""

from __future__ import annotations

import streamlit as st

# Canonical fixed-workflow pipeline, in order, with short Chinese labels.
PIPELINE: list[tuple[str, str]] = [
    ("infer_type_and_outline", "任务分析"),
    ("generate_initial_note", "生成初稿"),
    ("generate_reference_queries", "查询生成"),
    ("retrieve_references", "信息检索"),
    ("verify_and_refine", "内容验证"),
    ("finalize_note", "生成笔记"),
]
_ASSET_STAGES: list[tuple[str, str]] = [
    ("plan_note_assets", "规划资产"),
    ("generate_note_assets", "生成资产"),
    ("assemble_assets_into_note", "组装笔记"),
    ("save_markdown", "保存笔记"),
    ("publish_notion", "发布 Notion"),
]
NODE_LABELS = dict(PIPELINE + _ASSET_STAGES)


def new_view(*, mode: str, task: dict, params: dict, settings: dict) -> dict:
    """Build a fresh pending RunView from a submitted task."""
    return {
        "status": "pending",          # pending → running → done | error
        "mode": mode,                  # "fixed" | "react"
        "task": task,                  # user-facing: text, files[], urls[]
        "params": params,              # execution: manual_text, file_texts, urls
        "settings": settings,          # llm, search, iters, assets, notion
        "nodes": [],                   # fixed: [{node,label,status}]
        "react": [],                   # react: [{think,act,observe}]
        "iteration": 0,
        "max_iterations": settings.get("iters", 0),
        "live_text": "",              # streaming buffer for current node
        "final_note": "",
        "sources": [],
        "usage": {},
        "trace": [],                   # [(label, keys)] execution trace
        "run_id": "",
        "run_log_dir": "",
        "error": "",
        "readonly": False,             # True when loaded from history
    }


def get_view() -> dict | None:
    return st.session_state.get("view")


def set_view(view: dict | None) -> None:
    st.session_state["view"] = view


def start_stage(view: dict, node: str, label: str) -> None:
    """Fold a fixed-mode node_start into the pipeline stepper."""
    for n in view["nodes"]:
        if n["status"] == "running":
            n["status"] = "done"
    short = NODE_LABELS.get(node, label)
    view["nodes"].append({"node": node, "label": short, "status": "running"})
    view["live_text"] = ""
    if node == "verify_and_refine":
        view["iteration"] += 1


def start_react_step(view: dict, label: str) -> None:
    """A ReAct `agent` node_start opens a new Think/Act/Observe step."""
    view["iteration"] += 1
    view["react"].append({"think": label, "act": "", "observe": []})


def set_react_act(view: dict, label: str) -> None:
    if view["react"]:
        view["react"][-1]["act"] = label


def add_react_observe(view: dict, text: str) -> None:
    if not view["react"]:
        view["react"].append({"think": "", "act": "", "observe": []})
    view["react"][-1]["observe"].append(text)


def finish(view: dict, status: str = "done") -> None:
    for n in view["nodes"]:
        if n["status"] == "running":
            n["status"] = "done"
    view["status"] = status
