"""Channel normalizers for the ingestion service."""

from .base import BaseNormalizer
from .email import EmailNormalizer
from .registry import NormalizerRegistry
from .trade_data import TradeDataNormalizer

__all__ = [
    "BaseNormalizer",
    "EmailNormalizer",
    "NormalizerRegistry",
    "TradeDataNormalizer",
]
