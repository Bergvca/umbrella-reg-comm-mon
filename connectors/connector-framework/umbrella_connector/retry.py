"""Tenacity retry wrapper driven by RetryConfig."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import RetryConfig

T = TypeVar("T")


def with_retry(
    config: RetryConfig,
    *,
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """Return a tenacity retry decorator configured from *config*.

    Usage::

        @with_retry(config.retry)
        async def deliver(msg: RawMessage) -> None: ...
    """
    return retry(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_exponential(
            multiplier=config.multiplier,
            min=config.initial_wait_seconds,
            max=config.max_wait_seconds,
        ),
        retry=retry_if_exception_type(retryable_exceptions),
        reraise=True,
    )
