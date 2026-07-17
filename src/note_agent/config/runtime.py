"""Runtime knobs for speed/quality tradeoffs."""

from __future__ import annotations

import os


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int = 20) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def max_reference_queries() -> int:
    return _env_int("MAX_REFERENCE_QUERIES", 3, minimum=1, maximum=8)


def max_results_per_source() -> int:
    return _env_int("MAX_RESULTS_PER_SOURCE", 3, minimum=1, maximum=10)


def max_retrieval_workers() -> int:
    return _env_int("MAX_RETRIEVAL_WORKERS", 3, minimum=1, maximum=8)


def request_timeout(default: int = 15) -> int:
    return _env_int("REFERENCE_REQUEST_TIMEOUT", default, minimum=3, maximum=120)
