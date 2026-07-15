"""Session view-model and the fixed-pipeline stage map.

`RunView` is the single source of truth the render layer draws from, both
during live streaming and on later reruns. The agent workflow is never
touched here — we only fold its public events into view state.
"""

from __future__ import annotations

import time

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
        "run_id": "",
        "run_log_dir": "",
        "error": "",
        "readonly": False,             # True when loaded from history
        "_t0": None,                   # monotonic start of current step
        "_tok0": 0,                    # cumulative tokens at step start
    }


def _now() -> float:
    return time.monotonic()


def _cum_tokens(view: dict) -> int:
    return int((view.get("usage") or {}).get("total_tokens") or 0)


def _seal_current(view: dict) -> None:
    """Attach elapsed time + tokens spent to the currently-running entries."""
    if view["_t0"] is None:
        return
    dur = _now() - view["_t0"]
    tok = max(0, _cum_tokens(view) - view["_tok0"])
    for n in view["nodes"]:
        if n["status"] == "running" and "dur" not in n:
            n["dur"], n["tok"] = dur, tok
    if view["react"] and "dur" not in view["react"][-1]:
        view["react"][-1]["dur"] = dur
        view["react"][-1]["tok"] = tok


def get_view() -> dict | None:
    return st.session_state.get("view")


def set_view(view: dict | None) -> None:
    st.session_state["view"] = view


def start_stage(view: dict, node: str, label: str) -> None:
    """Fold a fixed-mode node_start into the pipeline stepper."""
    _seal_current(view)
    for n in view["nodes"]:
        if n["status"] == "running":
            n["status"] = "done"
    short = NODE_LABELS.get(node, label)
    view["nodes"].append({"node": node, "label": short, "status": "running"})
    view["live_text"] = ""
    view["_t0"], view["_tok0"] = _now(), _cum_tokens(view)
    if node == "verify_and_refine":
        view["iteration"] += 1


def start_react_step(view: dict, label: str) -> None:
    """A ReAct `agent` node_start opens a new Think/Act/Observe step."""
    _seal_current(view)
    view["iteration"] += 1
    view["react"].append({"think": label, "act": "", "observe": []})
    view["_t0"], view["_tok0"] = _now(), _cum_tokens(view)


def set_react_act(view: dict, label: str) -> None:
    if view["react"]:
        view["react"][-1]["act"] = label


def add_react_observe(view: dict, text: str) -> None:
    if not view["react"]:
        view["react"].append({"think": "", "act": "", "observe": []})
    view["react"][-1]["observe"].append(text)


def finish(view: dict, status: str = "done") -> None:
    _seal_current(view)
    for n in view["nodes"]:
        if n["status"] == "running":
            n["status"] = "done"
    view["_t0"] = None
    view["status"] = status
