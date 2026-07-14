#!/usr/bin/env python3
"""
Eval suite runner for the Note Agent prompt evaluation framework.

Usage:
    # Run all eval tests (snapshot + node logic + apply_patches)
    python -m tests.eval.runner

    # Update snapshots after intentional prompt changes
    python -m tests.eval.runner --update-snapshots

    # Run with E2E quality tests (requires API keys)
    python -m tests.eval.runner --e2e

    # Run only specific test categories
    python -m tests.eval.runner --snapshots-only
    python -m tests.eval.runner --nodes-only
    python -m tests.eval.runner --patches-only

    # Run with verbose output
    python -m tests.eval.runner -v

    # Quick mode — only the cheapest tests
    python -m tests.eval.runner --quick
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).parent
PROJECT_DIR = EVAL_DIR.parent.parent


def run_tests(test_paths: list[str], extra_args: list[str] | None = None) -> int:
    """Run pytest on the given test paths and return exit code."""
    args = [
        sys.executable, "-m", "pytest",
        *test_paths,
        "-p", "no:warnings",
        "--tb=short",
        "--color=yes",
        *(extra_args or []),
    ]
    result = subprocess.run(args, cwd=str(PROJECT_DIR))
    return result.returncode


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Note Agent Prompt Eval Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--update-snapshots", action="store_true",
        help="Accept new prompt outputs as the reference snapshot"
    )
    parser.add_argument(
        "--e2e", action="store_true",
        help="Run end-to-end quality tests with real LLM calls"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose pytest output"
    )
    parser.add_argument(
        "--snapshots-only", action="store_true",
        help="Only run snapshot tests"
    )
    parser.add_argument(
        "--nodes-only", action="store_true",
        help="Only run node logic tests"
    )
    parser.add_argument(
        "--patches-only", action="store_true",
        help="Only run _apply_patches tests"
    )
    parser.add_argument(
        "--e2e-only", action="store_true",
        help="Only run E2E quality tests"
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: skip snapshot and E2E, only unit tests"
    )
    parser.add_argument(
        "-k", "--keyword", type=str, default=None,
        help="Only run tests matching this keyword expression"
    )

    args = parser.parse_args()

    # Build test file list
    test_files = []
    if args.quick:
        test_files = [
            str(EVAL_DIR / "test_apply_patches.py"),
            str(EVAL_DIR / "test_node_logic.py"),
        ]
    elif args.snapshots_only:
        test_files = [str(EVAL_DIR / "test_prompt_snapshots.py")]
    elif args.nodes_only:
        test_files = [str(EVAL_DIR / "test_node_logic.py")]
    elif args.patches_only:
        test_files = [str(EVAL_DIR / "test_apply_patches.py")]
    elif args.e2e_only:
        test_files = [str(EVAL_DIR / "test_e2e_quality.py")]
    else:
        # Default: all eval tests
        test_files = [
            str(EVAL_DIR / "test_apply_patches.py"),
            str(EVAL_DIR / "test_node_logic.py"),
            str(EVAL_DIR / "test_prompt_snapshots.py"),
        ]
        if args.e2e:
            test_files.append(str(EVAL_DIR / "test_e2e_quality.py"))

    # Build extra pytest args
    pytest_args = []
    if args.update_snapshots:
        pytest_args.append("--update-snapshots")
    if args.e2e:
        pytest_args.append("--e2e")
    if args.verbose:
        pytest_args.append("-v")
    if args.keyword:
        pytest_args.extend(["-k", args.keyword])

    print(f"\n{'='*60}")
    if args.update_snapshots:
        print("  UPDATE MODE — snapshots will be overwritten")
    if args.e2e:
        print("  E2E MODE — real LLM calls will be made (slow, costs tokens)")
    print(f"  Test files: {len(test_files)}")
    for tf in test_files:
        print(f"    - {Path(tf).name}")
    print(f"{'='*60}\n")

    exit_code = run_tests(test_files, pytest_args)

    if exit_code == 0:
        print("\n✓ All eval tests passed.")
    else:
        print(f"\n✗ Some tests failed (exit code: {exit_code}).")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
