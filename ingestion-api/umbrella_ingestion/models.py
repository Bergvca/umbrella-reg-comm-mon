"""Input models — validate parsed messages from channel-specific processors."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedEmailMessage(BaseModel):
    """Validates the JSON output of the EmailProcessor (Stage 2).

    Uses ``Field(alias="from")`` because ``"from"`` is a Python reserved word.
    ``populate_by_name=True`` allows construction via either key.
    """

    model_config = {"populate_by_name": True}

    raw_message_id: str
    channel: str
    message_id: str
    subject: str
    from_address: str = Field(alias="from")
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    date: str
    body_text: str | None = None
    body_html: str | None = None
    headers: dict = Field(default_factory=dict)
    attachment_refs: list[str] = Field(default_factory=list)
    raw_eml_s3_uri: str
