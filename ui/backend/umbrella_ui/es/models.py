"""Pydantic models for Elasticsearch documents."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ESParticipant(BaseModel):
    id: str
    name: str
    role: str


class ESAttachment(BaseModel):
    name: str
    content_type: str
    s3_uri: str


class ESEntity(BaseModel):
    text: str
    label: str
    start: int | None = None
    end: int | None = None


class ESMessage(BaseModel):
    """A message document from the ``messages-*`` index."""

    message_id: str
    channel: str
    direction: str | None = None
    timestamp: datetime
    participants: list[ESParticipant] = []
    body_text: str | None = None
    audio_ref: str | None = None
    attachments: list[ESAttachment] = []
    transcript: str | None = None
    language: str | None = None
    translated_text: str | None = None
    entities: list[ESEntity] = []
    sentiment: str | None = None
    sentiment_score: float | None = None
    risk_score: float | None = None
    matched_policies: list[str] = []
    processing_status: str | None = None


class ESMessageHit(BaseModel):
    """A single search hit with optional highlights."""

    message: ESMessage
    index: str
    score: float | None = None
    highlights: dict[str, list[str]] = {}


class ESAlert(BaseModel):
    """An alert document from the ``alerts-*`` index."""

    alert_id: str
    message_id: str | None = None
    channel: str | None = None
    timestamp: datetime | None = None
    alert_type: str | None = None
    severity: str | None = None
    risk_score: float | None = None
    matched_policies: list[str] = []
    matched_terms: list[str] = []
    excerpt: str | None = None
    participants: list[ESParticipant] = []
    review_status: str | None = None


class AlertStatsBucket(BaseModel):
    key: str
    doc_count: int


class AlertTimePoint(BaseModel):
    key_as_string: str
    doc_count: int


class AlertStats(BaseModel):
    by_severity: list[AlertStatsBucket] = []
    by_channel: list[AlertStatsBucket] = []
    by_status: list[AlertStatsBucket] = []
    over_time: list[AlertTimePoint] = []
