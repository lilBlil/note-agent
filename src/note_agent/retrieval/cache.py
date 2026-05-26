"""Reference retrieval cache — SHA1-keyed JSON files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from note_agent.domain.models import ReferenceItem
from note_agent.utils import to_plain_data

REFERENCE_CACHE_DIR = Path(".cache") / "references"


def _cache_key(*parts: object) -> str:
    raw = "::".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def load_reference_cache(
    *,
    source_name: str,
    query: str,
    max_results: int,
) -> list[ReferenceItem] | None:
    path = REFERENCE_CACHE_DIR / f"{_cache_key(source_name, query, max_results)}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [ReferenceItem(**item) for item in data]
    except Exception:
        return None


def save_reference_cache(
    *,
    source_name: str,
    query: str,
    max_results: int,
    results: list[ReferenceItem],
) -> None:
    path = REFERENCE_CACHE_DIR / f"{_cache_key(source_name, query, max_results)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_plain_data(results), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
