"""
Snapshot tests for all prompt functions.

Each test generates the prompt text from a function in `prompts.py` with
representative inputs, then compares against a stored snapshot. When a
prompt changes, the test fails and shows which prompt was modified.

Usage:
    pytest tests/eval/test_prompt_snapshots.py -v              # verify
    pytest tests/eval/test_prompt_snapshots.py --update-snapshots  # accept changes
"""

from __future__ import annotations

import json


from note_agent.agent.prompts import (
    finalize_note_prompt,
    generate_assets_prompt,
    generate_initial_note_prompt,
    generate_reference_queries_prompt,
    generate_title_prompt,
    infer_type_and_outline_prompt,
    plan_assets_prompt,
    verify_and_refine_prompt,
)
from tests.eval.conftest import assert_snapshot

# ---------------------------------------------------------------------------
# Shared test inputs
# ---------------------------------------------------------------------------

SAMPLE_RAW = "解释分布式系统中的CAP定理，包括一致性、可用性和分区容错性的定义和权衡"
SAMPLE_NOTE_TYPE = "学习笔记"
SAMPLE_OUTLINE = json.dumps([
    {"title": "概述", "purpose": "介绍CAP定理背景"},
    {"title": "C —— 一致性", "purpose": "一致性的严格定义"},
    {"title": "A —— 可用性", "purpose": "可用性的严格定义"},
    {"title": "P —— 分区容错性", "purpose": "分区容错性的含义"},
    {"title": "三者权衡", "purpose": "为什么不能三者兼得"},
], ensure_ascii=False)
SAMPLE_CURRENT_NOTE = """# CAP定理详解

## 概述
CAP定理是分布式系统设计的基石理论，由Eric Brewer在2000年提出，
后被Gilbert和Lynch形式化证明。

## C —— 一致性
一致性（Consistency）要求所有节点在同一时刻看到相同的数据...

## A —— 可用性
可用性（Availability）要求每个非故障节点都能返回响应...

## P —— 分区容错性
分区容错性（Partition Tolerance）要求系统在网络分区时仍能运行...

## 三者权衡
由于网络分区不可避免，系统必须在C和A之间做选择...
"""
SAMPLE_REFERENCES = "[R1] Brewer (2000). Towards Robust Distributed Systems.\n[R2] Gilbert & Lynch (2002). ACM SIGACT."
SAMPLE_VERIFICATION = "### 事实错误\n无\n### 事实冲突\n无\n### 无据断言\n无\n### 遗漏信息\n无"
SAMPLE_SOURCES = ["https://example.com/cap-theorem", "https://dl.acm.org/doi/10.1145/12345"]
SAMPLE_ASSET_PLAN = json.dumps([
    {"asset_type": "formula", "purpose": "CAP定理形式化表达", "priority": "high"}
], ensure_ascii=False)

# English sample
EN_RAW = "Explain the Transformer architecture and its self-attention mechanism in detail."
EN_CURRENT_NOTE = """# Transformer Architecture

## Overview
The Transformer, introduced in "Attention Is All You Need" (Vaswani et al., 2017),
revolutionized sequence modeling by replacing recurrence with attention.

## Self-Attention
Self-attention computes weighted representations of each position...
"""

# Short/vague sample
SHORT_RAW = "什么是闭包？"
VAGUE_RAW = "想了解一下AI"


class TestInferTypeAndOutline:
    def test_chinese_medium(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = infer_type_and_outline_prompt(SAMPLE_RAW)
        assert_snapshot(snapshots_dir, "infer_type_cn", prompt, update_snapshots)

    def test_english(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = infer_type_and_outline_prompt(EN_RAW)
        assert_snapshot(snapshots_dir, "infer_type_en", prompt, update_snapshots)

    def test_short(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = infer_type_and_outline_prompt(SHORT_RAW)
        assert_snapshot(snapshots_dir, "infer_type_short", prompt, update_snapshots)

    def test_vague(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = infer_type_and_outline_prompt(VAGUE_RAW)
        assert_snapshot(snapshots_dir, "infer_type_vague", prompt, update_snapshots)


class TestGenerateInitialNote:
    def test_chinese(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = generate_initial_note_prompt(SAMPLE_RAW, SAMPLE_NOTE_TYPE, SAMPLE_OUTLINE)
        assert_snapshot(snapshots_dir, "gen_initial_cn", prompt, update_snapshots)

    def test_english(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = generate_initial_note_prompt(EN_RAW, "learning_note", json.dumps([
            {"title": "Overview", "purpose": "Introduce Transformer"}
        ], ensure_ascii=False))
        assert_snapshot(snapshots_dir, "gen_initial_en", prompt, update_snapshots)

    def test_complex_outline(self, snapshots_dir: str, update_snapshots: str) -> None:
        """Outline with many sections (10+) — tests prompt handles large structures."""
        large_outline = json.dumps([
            {"title": f"第{i}章", "purpose": f"内容{i}"} for i in range(1, 12)
        ], ensure_ascii=False)
        prompt = generate_initial_note_prompt(SAMPLE_RAW, "研究综述笔记", large_outline)
        assert_snapshot(snapshots_dir, "gen_initial_large", prompt, update_snapshots)


class TestVerifyAndRefine:
    def test_with_references(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = verify_and_refine_prompt(SAMPLE_RAW, SAMPLE_CURRENT_NOTE, SAMPLE_REFERENCES)
        assert_snapshot(snapshots_dir, "verify_refine_with_refs", prompt, update_snapshots)

    def test_empty_references(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = verify_and_refine_prompt(SAMPLE_RAW, SAMPLE_CURRENT_NOTE, "暂无参考信息")
        assert_snapshot(snapshots_dir, "verify_refine_empty_refs", prompt, update_snapshots)

    def test_short_note(self, snapshots_dir: str, update_snapshots: str) -> None:
        short_note = "# 闭包\n\n闭包是指函数可以访问其外部作用域的变量。"
        prompt = verify_and_refine_prompt(SHORT_RAW, short_note, "暂无参考信息")
        assert_snapshot(snapshots_dir, "verify_refine_short", prompt, update_snapshots)


class TestReferenceQueries:
    def test_with_gaps(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = generate_reference_queries_prompt(SAMPLE_CURRENT_NOTE, [])
        assert_snapshot(snapshots_dir, "ref_queries_gaps", prompt, update_snapshots)

    def test_with_used(self, snapshots_dir: str, update_snapshots: str) -> None:
        used = ["CAP定理 形式化证明", "分布式系统 一致性模型"]
        prompt = generate_reference_queries_prompt(SAMPLE_CURRENT_NOTE, used)
        assert_snapshot(snapshots_dir, "ref_queries_used", prompt, update_snapshots)

    def test_complete_note(self, snapshots_dir: str, update_snapshots: str) -> None:
        """A very complete note should return empty queries."""
        complete_note = """# CAP定理完全指南

## 形式化证明
根据Gilbert和Lynch (2002)的证明，在异步网络模型中...

## 一致性模型详解
线性一致性、顺序一致性、因果一致性...

## 实践案例
Google Spanner (CP), Amazon Dynamo (AP), etcd (CP)...

## PACELC扩展
Abadi (2012)提出的扩展模型...
"""
        prompt = generate_reference_queries_prompt(complete_note, [])
        assert_snapshot(snapshots_dir, "ref_queries_complete", prompt, update_snapshots)


class TestFinalizeNote:
    def test_with_sources(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = finalize_note_prompt(SAMPLE_CURRENT_NOTE, SAMPLE_SOURCES)
        assert_snapshot(snapshots_dir, "finalize_with_sources", prompt, update_snapshots)

    def test_no_sources(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = finalize_note_prompt(SAMPLE_CURRENT_NOTE, [])
        assert_snapshot(snapshots_dir, "finalize_no_sources", prompt, update_snapshots)

    def test_english(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = finalize_note_prompt(EN_CURRENT_NOTE, ["https://arxiv.org/abs/1706.03762"])
        assert_snapshot(snapshots_dir, "finalize_en", prompt, update_snapshots)


class TestPlanAssets:
    def test_theory_note(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = plan_assets_prompt(SAMPLE_CURRENT_NOTE, "学习笔记")
        assert_snapshot(snapshots_dir, "plan_assets_theory", prompt, update_snapshots)

    def test_code_note(self, snapshots_dir: str, update_snapshots: str) -> None:
        code_note = """# Python装饰器详解

## 基础装饰器
装饰器本质上是一个接受函数并返回函数的可调用对象...

## 带参数装饰器
当装饰器自身需要参数时，需要再嵌套一层...

```python
def repeat(n):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(n):
                func(*args, **kwargs)
        return wrapper
    return decorator
```
"""
        prompt = plan_assets_prompt(code_note, "学习笔记")
        assert_snapshot(snapshots_dir, "plan_assets_code", prompt, update_snapshots)

    def test_pure_text_note(self, snapshots_dir: str, update_snapshots: str) -> None:
        """Pure text concept — should plan no assets."""
        text_note = """# 什么是技术债务

## 定义
技术债务是Ward Cunningham提出的隐喻...

## 分类
技术债务可分为代码债务、设计债务和架构债务...

## 偿还策略
定期重构、分配专门的技术债务迭代...
"""
        prompt = plan_assets_prompt(text_note, "学习笔记")
        assert_snapshot(snapshots_dir, "plan_assets_pure_text", prompt, update_snapshots)


class TestGenerateAssets:
    def test_formula_plan(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = generate_assets_prompt(SAMPLE_CURRENT_NOTE, SAMPLE_ASSET_PLAN)
        assert_snapshot(snapshots_dir, "gen_assets_formula", prompt, update_snapshots)

    def test_multi_asset_plan(self, snapshots_dir: str, update_snapshots: str) -> None:
        multi_plan = json.dumps([
            {"asset_type": "formula", "purpose": "CAP定理形式化表达", "priority": "high"},
            {"asset_type": "mermaid", "purpose": "CP vs AP决策流程图", "priority": "high"},
            {"asset_type": "code", "purpose": "etcd一致性配置示例", "priority": "medium"},
        ], ensure_ascii=False)
        prompt = generate_assets_prompt(SAMPLE_CURRENT_NOTE, multi_plan)
        assert_snapshot(snapshots_dir, "gen_assets_multi", prompt, update_snapshots)

    def test_empty_plan(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = generate_assets_prompt(SAMPLE_CURRENT_NOTE, "[]")
        assert_snapshot(snapshots_dir, "gen_assets_empty", prompt, update_snapshots)


class TestGenerateTitle:
    def test_chinese(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = generate_title_prompt(SAMPLE_CURRENT_NOTE)
        assert_snapshot(snapshots_dir, "title_cn", prompt, update_snapshots)

    def test_english(self, snapshots_dir: str, update_snapshots: str) -> None:
        prompt = generate_title_prompt(EN_CURRENT_NOTE)
        assert_snapshot(snapshots_dir, "title_en", prompt, update_snapshots)

    def test_long_note(self, snapshots_dir: str, update_snapshots: str) -> None:
        long_note = SAMPLE_CURRENT_NOTE * 5  # simulate very long note
        prompt = generate_title_prompt(long_note)
        assert_snapshot(snapshots_dir, "title_long", prompt, update_snapshots)
