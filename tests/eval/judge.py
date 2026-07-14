"""
LLM-as-judge for scoring the QUALITY of generated learning notes.

The snapshot / node-logic tests only tell you a prompt *changed* or that output
is structurally valid. They cannot tell you whether a note is actually *good*.
This module fills that gap: it scores a note on the dimensions that make a
learning note genuinely valuable, and — crucially — returns actionable feedback
aimed at the PROMPT, so you can iterate toward a better prompt.

Usage:
    from tests.eval.judge import judge_note
    result = judge_note(raw_input, note, provider="deepseek")
    print(result["overall"], result["scores"], result["prompt_feedback"])
"""

from __future__ import annotations

import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Scoring rubric — dimensions + weights (weights sum to 1.0)
# ---------------------------------------------------------------------------
# Each dimension is scored 1-5 by the judge. `overall` is the weighted mean,
# computed in code (never trust the model to do arithmetic).

RUBRIC: dict[str, dict[str, Any]] = {
    "factual_accuracy": {
        "weight": 0.25,
        "zh": "事实准确性",
        "desc": "内容是否正确、无幻觉、无违背领域共识的断言。编造的事实/数据/引用是最严重的扣分项。",
    },
    "depth_and_mechanism": {
        "weight": 0.20,
        "zh": "深度与机制",
        "desc": "是否解释了原理、推导、内在机制，而非仅罗列结论。是否达到能真正学会的深度。",
    },
    "completeness": {
        "weight": 0.15,
        "zh": "完整性",
        "desc": "是否覆盖了用户输入明确要求的所有关键点，没有遗漏核心子主题。",
    },
    "structure_coherence": {
        "weight": 0.15,
        "zh": "结构与连贯",
        "desc": "章节划分是否合理、逻辑是否层层递进、前后是否一致、无重复啰嗦。",
    },
    "pedagogy_readability": {
        "weight": 0.15,
        "zh": "教学性与可读性",
        "desc": "是否好懂、节奏合理、术语有解释、举例得当，读完能学到东西而非被术语淹没。",
    },
    "asset_appropriateness": {
        "weight": 0.10,
        "zh": "资产恰当性",
        "desc": "公式/代码/图表是否用在真正需要的地方且正确；纯文字够用处不硬塞，该有的地方不缺。",
    },
}

SCORE_ANCHORS = """评分锚点（每个维度 1-5 分，可给整数）：
- 5 = 优秀：达到可直接发布的高质量学习资料水平
- 4 = 良好：小瑕疵，基本合格
- 3 = 及格：能用但有明显短板
- 2 = 较差：短板严重，需大幅返工
- 1 = 差：该维度基本不达标
严格打分，不要因为"看起来还行"就给高分。发现幻觉/编造直接把 factual_accuracy 压到 1-2。"""


def build_judge_prompt(raw_input: str, note: str, note_type: str = "") -> str:
    dims_text = "\n".join(
        f"- {key}（{cfg['zh']}）：{cfg['desc']}"
        for key, cfg in RUBRIC.items()
    )
    type_line = f"\n笔记类型：{note_type}\n" if note_type else ""
    return f"""你是一位严格的技术教育内容评审专家。请评估下面这篇由 AI 生成的学习笔记的质量。

你的评估必须服务于一个目标：判断"生成这篇笔记的 prompt"是否能指导出真实有价值的学习笔记。
{type_line}
## 用户的原始需求
{raw_input}

## 待评估的笔记
{note}

## 评分维度
{dims_text}

{SCORE_ANCHORS}

## 特别要求
1. factual_accuracy：主动怀疑。指出任何看起来像编造的具体数据、不存在的引用、违背常识的断言。宁可严格。
2. prompt_feedback 是本次评审最重要的产出：不要评价这一篇笔记的个别措辞，而要指出"为了让 prompt 每次都生成更好的笔记，prompt 本身应该增加/修改什么约束"。要具体、可执行。

## 输出格式（严格 JSON，不要代码块包裹，不要解释）
{{
  "scores": {{
    "factual_accuracy": 3,
    "depth_and_mechanism": 3,
    "completeness": 3,
    "structure_coherence": 3,
    "pedagogy_readability": 3,
    "asset_appropriateness": 3
  }},
  "hallucinations": ["具体列出疑似编造/错误的内容，没有则空数组"],
  "strengths": ["这篇笔记做得好的地方"],
  "weaknesses": ["这篇笔记的主要问题"],
  "prompt_feedback": ["为改进 prompt 的具体建议，指向 prompt 而非这一篇笔记"]
}}
"""


def _parse_judge_json(text: str) -> dict[str, Any] | None:
    """Robustly extract the judge's JSON object from raw LLM text."""
    cleaned = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", text.strip(), flags=re.DOTALL)
    # Grab the outermost {...}
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def compute_overall(scores: dict[str, Any]) -> float:
    """Weighted mean over rubric dimensions. Missing dims are skipped and the
    remaining weights are renormalized so the scale stays 1-5."""
    total_w = 0.0
    acc = 0.0
    for key, cfg in RUBRIC.items():
        val = scores.get(key)
        if isinstance(val, (int, float)):
            acc += float(val) * cfg["weight"]
            total_w += cfg["weight"]
    if total_w == 0:
        return 0.0
    return round(acc / total_w, 3)


def judge_note(
    raw_input: str,
    note: str,
    note_type: str = "",
    provider: str = "deepseek",
) -> dict[str, Any]:
    """Score a single note. Returns a dict with per-dimension scores, weighted
    `overall`, and qualitative feedback. On judge failure returns overall=0.0
    with an `error` field so the harness can surface it instead of crashing."""
    from note_agent.config.llm import ask_llm

    prompt = build_judge_prompt(raw_input, note, note_type)
    try:
        raw = ask_llm(prompt, provider=provider, stream=False)
    except Exception as e:  # network / provider errors shouldn't kill a whole run
        return {"overall": 0.0, "scores": {}, "error": f"judge call failed: {e}"}

    data = _parse_judge_json(raw)
    if data is None:
        return {"overall": 0.0, "scores": {}, "error": "judge returned unparseable JSON",
                "raw": raw[:500]}

    scores = data.get("scores", {}) or {}
    return {
        "overall": compute_overall(scores),
        "scores": scores,
        "hallucinations": data.get("hallucinations", []),
        "strengths": data.get("strengths", []),
        "weaknesses": data.get("weaknesses", []),
        "prompt_feedback": data.get("prompt_feedback", []),
    }
