"""Abstract base class for channel normalizers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from umbrella_schema import Channel, NormalizedMessage


class BaseNormalizer(ABC):
    """Transform a channel-specific parsed message into a NormalizedMessage."""

    @property
    @abstractmethod
    def channel(self) -> Channel:
        """The channel this normalizer handles."""

    @abstractmethod
    def normalize(self, parsed: dict) -> NormalizedMessage:
        """Convert a parsed message dict into a NormalizedMessage.

        Synchronous — normalization is pure data transformation, no I/O.
        """
