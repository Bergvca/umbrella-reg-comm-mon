"""Tests for umbrella_ingestion.normalizers.email (EmailNormalizer)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from umbrella_schema import Channel, Direction

from umbrella_ingestion.normalizers.email import EmailNormalizer

from tests.conftest import make_parsed_email


@pytest.fixture
def normalizer() -> EmailNormalizer:
    return EmailNormalizer(monitored_domains=["acme.com", "acme.co.uk"])


class TestDirectionDetection:
    def test_inbound(self, normalizer: EmailNormalizer):
        data = make_parsed_email(
            from_address="external@gmail.com",
            to=["user@acme.com"],
        )
        result = normalizer.normalize(data)
        assert result.direction == Direction.INBOUND

    def test_outbound(self, normalizer: EmailNormalizer):
        data = make_parsed_email(
            from_address="user@acme.com",
            to=["external@gmail.com"],
        )
        result = normalizer.normalize(data)
        assert result.direction == Direction.OUTBOUND

    def test_internal(self, normalizer: EmailNormalizer):
        data = make_parsed_email(
            from_address="alice@acme.com",
            to=["bob@acme.co.uk"],
        )
        result = normalizer.normalize(data)
        assert result.direction == Direction.INTERNAL

    def test_neither_defaults_inbound(self, normalizer: EmailNormalizer):
        data = make_parsed_email(
            from_address="a@external.com",
            to=["b@other.com"],
        )
        result = normalizer.normalize(data)
        assert result.direction == Direction.INBOUND

    def test_cc_triggers_internal(self, normalizer: EmailNormalizer):
        data = make_parsed_email(
            from_address="user@acme.com",
            to=["external@gmail.com"],
            cc=["colleague@acme.co.uk"],
        )
        result = normalizer.normalize(data)
        assert result.direction == Direction.INTERNAL

    def test_bcc_triggers_internal(self, normalizer: EmailNormalizer):
        data = make_parsed_email(
            from_address="user@acme.com",
            to=["external@gmail.com"],
            bcc=["compliance@acme.com"],
        )
        result = normalizer.normalize(data)
        assert result.direction == Direction.INTERNAL

    def test_case_insensitive_domain(self):
        normalizer = EmailNormalizer(monitored_domains=["ACME.COM"])
        data = make_parsed_email(
            from_address="user@acme.com",
            to=["external@gmail.com"],
        )
        result = normalizer.normalize(data)
        assert result.direction == Direction.OUTBOUND


class TestParticipants:
    def test_sender_and_recipients(self, normalizer: EmailNormalizer):
        data = make_parsed_email(
            from_address="Alice <alice@acme.com>",
            to=["Bob <bob@example.com>"],
            cc=["Carol <carol@example.com>"],
        )
        result = normalizer.normalize(data)

        assert len(result.participants) == 3

        sender = result.participants[0]
        assert sender.role == "sender"
        assert sender.id == "alice@acme.com"
        assert sender.name == "Alice"

        to_p = result.participants[1]
        assert to_p.role == "to"
        assert to_p.id == "bob@example.com"
        assert to_p.name == "Bob"

        cc_p = result.participants[2]
        assert cc_p.role == "cc"

    def test_bare_email_address(self, normalizer: EmailNormalizer):
        data = make_parsed_email(from_address="user@acme.com")
        result = normalizer.normalize(data)
        sender = result.participants[0]
        assert sender.id == "user@acme.com"
        assert sender.name == "user@acme.com"

    def test_bcc_participants(self, normalizer: EmailNormalizer):
        data = make_parsed_email(bcc=["hidden@acme.com"])
        result = normalizer.normalize(data)
        bcc_participants = [p for p in result.participants if p.role == "bcc"]
        assert len(bcc_participants) == 1
        assert bcc_participants[0].id == "hidden@acme.com"


class TestAttachments:
    def test_attachment_from_s3_uri(self, normalizer: EmailNormalizer):
        refs = ["s3://bucket/attachments/100/abc123def456_report.pdf"]
        data = make_parsed_email(attachment_refs=refs)
        result = normalizer.normalize(data)

        assert len(result.attachments) == 1
        att = result.attachments[0]
        assert att.name == "report.pdf"
        assert att.content_type == "application/pdf"
        assert att.s3_uri == refs[0]

    def test_multiple_attachments(self, normalizer: EmailNormalizer):
        refs = [
            "s3://bucket/att/abc123def456_doc.xlsx",
            "s3://bucket/att/fed987abc654_image.png",
        ]
        data = make_parsed_email(attachment_refs=refs)
        result = normalizer.normalize(data)
        assert len(result.attachments) == 2
        assert result.attachments[0].name == "doc.xlsx"
        assert result.attachments[1].name == "image.png"

    def test_no_attachments(self, normalizer: EmailNormalizer):
        data = make_parsed_email(attachment_refs=[])
        result = normalizer.normalize(data)
        assert result.attachments == []

    def test_unknown_extension_octet_stream(self, normalizer: EmailNormalizer):
        refs = ["s3://bucket/att/hash_file.xyz123"]
        data = make_parsed_email(attachment_refs=refs)
        result = normalizer.normalize(data)
        assert result.attachments[0].content_type == "application/octet-stream"


class TestTimestamp:
    def test_rfc2822_parsed_to_utc(self, normalizer: EmailNormalizer):
        data = make_parsed_email(date="Mon, 01 Jun 2025 12:00:00 +0000")
        result = normalizer.normalize(data)
        assert result.timestamp == datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)

    def test_non_utc_converted(self, normalizer: EmailNormalizer):
        data = make_parsed_email(date="Mon, 01 Jun 2025 08:00:00 -0400")
        result = normalizer.normalize(data)
        assert result.timestamp == datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)


class TestMetadata:
    def test_metadata_preserved(self, normalizer: EmailNormalizer):
        data = make_parsed_email(
            subject="Important",
            body_html="<p>Hi</p>",
            raw_eml_s3_uri="s3://b/k",
            raw_message_id="raw-99",
        )
        result = normalizer.normalize(data)
        assert result.metadata["subject"] == "Important"
        assert result.metadata["body_html"] == "<p>Hi</p>"
        assert result.metadata["raw_eml_s3_uri"] == "s3://b/k"
        assert result.metadata["raw_message_id"] == "raw-99"


class TestChannelField:
    def test_channel_is_email(self, normalizer: EmailNormalizer):
        data = make_parsed_email()
        result = normalizer.normalize(data)
        assert result.channel == Channel.EMAIL


class TestTimestampEdgeCases:
    def test_empty_date_falls_back_to_now(self, normalizer: EmailNormalizer):
        """Empty date string → fallback to current UTC time."""
        data = make_parsed_email(date="")
        result = normalizer.normalize(data)
        # Should be a recent UTC datetime (within last 5 seconds)
        now = datetime.now(timezone.utc)
        delta = abs((now - result.timestamp).total_seconds())
        assert delta < 5

    def test_garbage_date_falls_back_to_now(self, normalizer: EmailNormalizer):
        """Unparseable date string → fallback to current UTC time."""
        data = make_parsed_email(date="this is not a date")
        result = normalizer.normalize(data)
        now = datetime.now(timezone.utc)
        delta = abs((now - result.timestamp).total_seconds())
        assert delta < 5


class TestFilenameExtractionEdgeCases:
    def test_uri_without_hash_prefix(self, normalizer: EmailNormalizer):
        """S3 URI where the last segment has no {hash}_ prefix."""
        refs = ["s3://bucket/attachments/plainfile.pdf"]
        data = make_parsed_email(attachment_refs=refs)
        result = normalizer.normalize(data)
        assert result.attachments[0].name == "plainfile.pdf"

    def test_uri_with_uppercase_hash(self, normalizer: EmailNormalizer):
        """Uppercase hex should NOT match the lowercase-only hash regex."""
        refs = ["s3://bucket/attachments/ABCDEF_report.pdf"]
        data = make_parsed_email(attachment_refs=refs)
        result = normalizer.normalize(data)
        # Uppercase hex doesn't match [a-f0-9]+, so the whole segment is returned
        assert result.attachments[0].name == "ABCDEF_report.pdf"

    def test_uri_with_no_path(self, normalizer: EmailNormalizer):
        """Degenerate URI with no slashes."""
        refs = ["just_a_filename.txt"]
        data = make_parsed_email(attachment_refs=refs)
        result = normalizer.normalize(data)
        # No slash → rsplit returns the whole string; no hex prefix → full segment
        assert result.attachments[0].name == "just_a_filename.txt"


class TestParticipantEdgeCases:
    def test_malformed_from_address_no_at(self, normalizer: EmailNormalizer):
        """from_address with no @ → domain extraction returns '', direction defaults to inbound."""
        data = make_parsed_email(from_address="notanemail")
        result = normalizer.normalize(data)
        # No domain means not monitored, so sender is not from monitored org
        # Recipients default to recipient@example.com which is also not monitored
        # → direction defaults to inbound
        assert result.direction == Direction.INBOUND
        # Participant should still be created
        sender = result.participants[0]
        assert sender.role == "sender"
        # parseaddr for a plain string returns ('', 'notanemail') if no <> format
        assert sender.id == "notanemail"

    def test_empty_to_cc_bcc(self, normalizer: EmailNormalizer):
        """All recipient lists empty → only sender participant."""
        # Build the dict directly because make_parsed_email defaults empty to=[] to a fallback
        data = {
            "raw_message_id": "raw-001",
            "channel": "email",
            "message_id": "<abc@example.com>",
            "subject": "Test",
            "from": "user@acme.com",
            "to": [],
            "cc": [],
            "bcc": [],
            "date": "Mon, 01 Jun 2025 12:00:00 +0000",
            "body_text": "Hello",
            "body_html": "",
            "headers": {},
            "attachment_refs": [],
            "raw_eml_s3_uri": "s3://bucket/raw/email/100.eml",
        }
        result = normalizer.normalize(data)
        assert len(result.participants) == 1
        assert result.participants[0].role == "sender"
        # Sender is from monitored org, no recipients → outbound
        assert result.direction == Direction.OUTBOUND
