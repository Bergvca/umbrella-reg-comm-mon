"""Schemas for export endpoints."""

from __future__ import annotations

from enum import Enum


class ExportFormat(str, Enum):
    csv = "csv"
    json = "json"
