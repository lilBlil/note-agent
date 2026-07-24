"""Network retry helpers for transient HTTP / provider failures."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def is_retryable_network_error(error: BaseException) -> bool:
    """Return True for transient transport / provider errors."""
    status = getattr(error, "status", None)
    if status in _RETRYABLE_STATUS_CODES:
        return True

    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code in _RETRYABLE_STATUS_CODES:
        return True

    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return True

    try:
        import httpx
    except ImportError:
        httpx = None
    else:
        if isinstance(error, (httpx.TransportError, httpx.TimeoutException)):
            return True

    try:
        import requests
    except ImportError:
        return False

    retryable = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.RetryError,
    )
    return isinstance(error, retryable)


def call_with_retries(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    delay_seconds: float = 1.0,
    label: str = "request",
) -> T:
    """Run a callable with bounded exponential backoff on transient failures."""
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as error:
            last_error = error
            if attempt >= attempts or not is_retryable_network_error(error):
                raise
            time.sleep(delay_seconds * (2 ** (attempt - 1)))

    raise RuntimeError(f"{label} failed without an exception") from last_error
