"""Tests for umbrella_ingestion.normalizers.registry."""

from __future__ import annotations

from umbrella_schema import Channel, NormalizedMessage

from umbrella_ingestion.normalizers.base import BaseNormalizer
from umbrella_ingestion.normalizers.registry import NormalizerRegistry


class FakeNormalizer(BaseNormalizer):
    """Minimal normalizer for registry testing."""

    def __init__(self, ch: Channel) -> None:
        self._channel = ch

    @property
    def channel(self) -> Channel:
        return self._channel

    def normalize(self, parsed: dict) -> NormalizedMessage:
        raise NotImplementedError


class TestNormalizerRegistry:
    def test_register_and_get(self):
        registry = NormalizerRegistry()
        normalizer = FakeNormalizer(Channel.EMAIL)
        registry.register(normalizer)

        assert registry.get("email") is normalizer

    def test_get_unknown_returns_none(self):
        registry = NormalizerRegistry()
        assert registry.get("teams_chat") is None

    def test_supported_channels(self):
        registry = NormalizerRegistry()
        registry.register(FakeNormalizer(Channel.EMAIL))
        registry.register(FakeNormalizer(Channel.TEAMS_CHAT))

        channels = registry.supported_channels
        assert "email" in channels
        assert "teams_chat" in channels
        assert len(channels) == 2

    def test_supported_channels_empty(self):
        registry = NormalizerRegistry()
        assert registry.supported_channels == []

    def test_register_overwrites_existing(self):
        registry = NormalizerRegistry()
        first = FakeNormalizer(Channel.EMAIL)
        second = FakeNormalizer(Channel.EMAIL)
        registry.register(first)
        registry.register(second)

        assert registry.get("email") is second
