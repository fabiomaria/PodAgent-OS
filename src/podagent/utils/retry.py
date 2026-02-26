"""Retry decorators using tenacity."""

from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def retry_api(max_attempts: int = 3):
    """Retry decorator for API calls with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
        reraise=True,
    )
