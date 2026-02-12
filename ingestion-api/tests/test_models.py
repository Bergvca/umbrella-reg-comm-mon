"""Tests for umbrella_ingestion.models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from umbrella_ingestion.models import ParsedEmailMessage

from tests.conftest import make_parsed_email


class TestParsedEmailMessage:
    def test_from_dict_with_from_key(self):
        data = make_parsed_email()
        msg = ParsedEmailMessage.model_validate(data)
        assert msg.from_address == "sender@example.com"
        assert msg.channel == "email"
        assert msg.raw_message_id == "raw-001"

    def test_from_dict_with_from_address_key(self):
        data = make_parsed_email()
        data["from_address"] = data.pop("from")
        msg = ParsedEmailMessage.model_validate(data)
        assert msg.from_address == "sender@example.com"

    def test_defaults(self):
        data = {
            "raw_message_id": "r1",
            "channel": "email",
            "message_id": "<id>",
            "subject": "s",
            "from": "a@b.com",
            "to": ["c@d.com"],
            "date": "Mon, 01 Jun 2025 12:00:00 +0000",
            "raw_eml_s3_uri": "s3://b/k",
        }
        msg = ParsedEmailMessage.model_validate(data)
        assert msg.cc == []
        assert msg.bcc == []
        assert msg.body_text is None
        assert msg.body_html is None
        assert msg.headers == {}
        assert msg.attachment_refs == []

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            ParsedEmailMessage.model_validate({"channel": "email"})

    def test_attachment_refs_preserved(self):
        refs = ["s3://bucket/att/hash_file.pdf", "s3://bucket/att/hash_img.png"]
        data = make_parsed_email(attachment_refs=refs)
        msg = ParsedEmailMessage.model_validate(data)
        assert msg.attachment_refs == refs
