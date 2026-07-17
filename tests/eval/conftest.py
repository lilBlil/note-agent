"""
Shared fixtures and mock infrastructure for eval tests.

Provides:
- mock_ask_llm: context manager to mock ask_llm with a sequence of responses
- mock_all_io: composite mock for all I/O side effects
- snapshots_dir, update_snapshots: snapshot testing support
- sample_note, sample_references: reusable test data
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest


# ============================================================================
# Snapshot testing
# ============================================================================

@pytest.fixture(scope="session")
def snapshots_dir() -> Path:
    return Path(__file__).parent / "snapshots"


def pytest_addoption(parser):
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Overwrite snapshot files with current prompt output",
    )
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests with real LLM calls (requires API keys)",
    )


@pytest.fixture
def update_snapshots(request) -> bool:
    return request.config.getoption("--update-snapshots")


def assert_snapshot(snapshots_dir: Path, test_id: str, actual: str, update: bool) -> None:
    """Compare `actual` against stored snapshot; auto-create on first run or --update.

    Uses SHA256 for compact storage — diffs are displayed via pytest's assertion
    when hashes mismatch, and the full diff is printed by the test function.
    """
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    hash_file = snapshots_dir / f"{test_id}.sha256"

    actual_hash = hashlib.sha256(actual.encode("utf-8")).hexdigest()

    if update or not hash_file.exists():
        hash_file.write_text(actual_hash, encoding="utf-8")
        # Also write the full prompt text for human diffing
        text_file = snapshots_dir / f"{test_id}.txt"
        text_file.write_text(actual, encoding="utf-8")
        if not update:
            pytest.skip(f"Snapshot created for {test_id} (first run). Re-run to verify.")
        return

    expected_hash = hash_file.read_text(encoding="utf-8").strip()

    if actual_hash != expected_hash:
        # Write the CURRENT actual to a .new file for diff comparison
        new_file = snapshots_dir / f"{test_id}.new.txt"
        new_file.write_text(actual, encoding="utf-8")
        old_file = snapshots_dir / f"{test_id}.txt"
        pytest.fail(
            f"Snapshot mismatch for '{test_id}'.\n"
            f"  Old hash: {expected_hash}\n"
            f"  New hash: {actual_hash}\n"
            f"  Old text: {old_file}\n"
            f"  New text: {new_file}\n"
            f"  To accept: run with --update-snapshots"
        )


# ============================================================================
# Mock ask_llm — returns pre-configured responses in sequence
# ============================================================================

@contextmanager
def mock_ask_llm_sequence(responses: list[str]):
    """Mock `ask_llm` to return `responses` one by one.

    Usage:
        with mock_ask_llm_sequence(['{"note_type":"X",...}', "# Note content", ...]):
            result = some_node_function(state)
    """
    call_count = [0]  # mutable counter for closure

    def fake_ask_llm(prompt: str = "", provider: str = "deepseek", stream: bool = False) -> str:
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(responses):
            return responses[idx]
        raise RuntimeError(
            f"mock_ask_llm called more times ({call_count[0]}) than provided responses ({len(responses)}).\n"
            f"Last prompt (first 300 chars): {prompt[:300]}"
        )

    with patch("note_agent.agent.graph.ask_llm", side_effect=fake_ask_llm):
        yield call_count


@contextmanager
def mock_graph_io(base_path: Path | None = None):
    """Mock all I/O side effects used by graph nodes.

    Mocks: emit_node_start, emit_event, save_intermediate_note,
           append_event, retrieve_references, format_references_for_prompt,
           collect_reference_urls.
    """
    with patch("note_agent.agent.graph.emit_node_start") as mock_ens, \
         patch("note_agent.agent.graph.emit_event") as mock_ee, \
         patch("note_agent.agent.graph.save_intermediate_note", return_value="/tmp/mock_note.md") as mock_save, \
         patch("note_agent.agent.graph.retrieve_references", return_value=[]) as mock_retrieve, \
         patch("note_agent.agent.graph.format_references_for_prompt", return_value="(no references)") as mock_format, \
         patch("note_agent.agent.graph.collect_reference_urls", return_value=[]) as mock_collect:
        yield {
            "emit_node_start": mock_ens,
            "emit_event": mock_ee,
            "save_intermediate_note": mock_save,
            "retrieve_references": mock_retrieve,
            "format_references_for_prompt": mock_format,
            "collect_reference_urls": mock_collect,
        }


@contextmanager
def mock_entire_pipeline(responses: list[str]):
    """Combined mock: ask_llm + I/O. Convenience for node logic tests."""
    with mock_graph_io() as io_mocks:
        with mock_ask_llm_sequence(responses):
            yield io_mocks


# ============================================================================
# Reusable test data
# ============================================================================

@pytest.fixture
def sample_note() -> str:
    return """# 分布式系统CAP定理深入理解

## 概述
CAP定理是分布式系统设计中的核心理论，由Eric Brewer于2000年提出。

## C —— 一致性 (Consistency)
一致性要求所有节点在同一时刻看到相同的数据。在分布式系统中...

## A —— 可用性 (Availability)
可用性要求每个非故障节点都能在合理时间内返回响应...

## P —— 分区容错性 (Partition Tolerance)
当网络分区发生时，系统必须继续运行...

## CP vs AP 系统
前面已经讨论了CAP定理的基本定义...

## 实践要点
在实际系统设计中，需要根据业务场景权衡选择...
"""


@pytest.fixture
def sample_references() -> str:
    return """[R1] Brewer, E. (2000). Towards Robust Distributed Systems. PODC.
摘要: 提出了CAP猜想，讨论了分布式系统中一致性、可用性和分区容错性之间的权衡。

[R2] Gilbert, S. & Lynch, N. (2002). Brewer's Conjecture and the Feasibility of Consistent,
Available, Partition-Tolerant Web Services. ACM SIGACT News.
摘要: 形式化证明了CAP定理，证明在异步网络中三者不可兼得。

[R3] Abadi, D. (2012). Consistency Tradeoffs in Modern Distributed Database System Design.
IEEE Computer.
摘要: 提出了PACELC扩展模型，讨论了分区情况下的一致性与延迟权衡。"""


@pytest.fixture
def sample_outline() -> list[dict[str, str]]:
    return [
        {"title": "概述", "purpose": "介绍CAP定理的背景和核心问题"},
        {"title": "C —— 一致性", "purpose": "形式化定义一致性概念"},
        {"title": "A —— 可用性", "purpose": "形式化定义可用性概念"},
        {"title": "P —— 分区容错性", "purpose": "形式化定义分区容错性"},
        {"title": "CP vs AP 系统", "purpose": "对比CP和AP系统的设计取舍"},
        {"title": "PACELC扩展", "purpose": "介绍CAP的扩展理论"},
        {"title": "实践要点", "purpose": "总结实际应用建议"},
    ]


@pytest.fixture
def base_state() -> dict:
    """Minimal valid state for testing graph nodes."""
    from note_agent.domain.models import new_run_id
    return {
        "run_id": new_run_id(),
        "raw_input": "测试输入",
        "max_iterations": 2,
        "iteration_count": 0,
        "llm_provider": "deepseek",
        "search_api": "duckduckgo",
        "enable_assets": True,
        "enable_notion": False,
        "note_type": "",
        "note_outline": [],
        "current_note": "",
        "reference_queries": [],
        "used_reference_queries": [],
        "reference_results": [],
        "evidence_items": [],
        "sources": [],
        "verification_report": "",
        "final_note": "",
        "note_title": "",
        "saved_path": "",
        "notion_url": "",
        "intermediate_paths": [],
        "asset_plan": [],
        "generated_assets": {},
        "asset_paths": [],
        "messages": [],
    }
