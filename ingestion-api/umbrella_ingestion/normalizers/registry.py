"""Normalizer registry — maps channel names to normalizer instances."""

from __future__ import annotations

import structlog

from .base import BaseNormalizer

logger = structlog.get_logger()


class NormalizerRegistry:
    """Registry of channel normalizers, keyed by channel value string."""

    def __init__(self) -> None:
        self._normalizers: dict[str, BaseNormalizer] = {}

    def register(self, normalizer: BaseNormalizer) -> None:
        """Register a normalizer for its channel."""
        key = normalizer.channel.value
        self._normalizers[key] = normalizer
        logger.info("normalizer_registered", channel=key)

    def get(self, channel: str) -> BaseNormalizer | None:
        """Look up a normalizer by channel string. Returns None if unsupported."""
        return self._normalizers.get(channel)

    @property
    def supported_channels(self) -> list[str]:
        """List of channel strings that have registered normalizers."""
        return list(self._normalizers.keys())
