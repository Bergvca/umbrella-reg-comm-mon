"""Umbrella Ingestion Service — normalize parsed messages into canonical schema."""

from .normalizers.email import EmailNormalizer
from .normalizers.registry import NormalizerRegistry
from .service import IngestionService

__all__ = [
    "EmailNormalizer",
    "IngestionService",
    "NormalizerRegistry",
]
