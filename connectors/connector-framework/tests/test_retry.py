"""Tests for umbrella_connector.retry."""

from __future__ import annotations

import pytest
from tenacity import RetryError

from umbrella_connector.config import RetryConfig
from umbrella_connector.retry import with_retry


class TestWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        config = RetryConfig(max_attempts=3, initial_wait_seconds=0.01, max_wait_seconds=0.1)
        call_count = 0

        @with_retry(config)
        async def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        config = RetryConfig(max_attempts=3, initial_wait_seconds=0.01, max_wait_seconds=0.1)
        call_count = 0

        @with_retry(config)
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = await fn()
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausts_retries_and_raises(self):
        config = RetryConfig(max_attempts=3, initial_wait_seconds=0.01, max_wait_seconds=0.1)
        call_count = 0

        @with_retry(config)
        async def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            await fn()
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self):
        config = RetryConfig(max_attempts=5, initial_wait_seconds=0.01, max_wait_seconds=0.1)
        call_count = 0

        @with_retry(config, retryable_exceptions=(ConnectionError,))
        async def fn():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")

        # TypeError is not in the retryable set, so it should fail immediately
        with pytest.raises(TypeError):
            await fn()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_single_attempt(self):
        config = RetryConfig(max_attempts=1, initial_wait_seconds=0.01, max_wait_seconds=0.1)
        call_count = 0

        @with_retry(config)
        async def fn():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await fn()
        assert call_count == 1
