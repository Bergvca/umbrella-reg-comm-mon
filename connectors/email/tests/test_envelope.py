"""Tests for umbrella_email.envelope."""

from __future__ import annotations

from tests.conftest import _build_plain_email

from umbrella_email.envelope import extract_envelope


class TestExtractEnvelope:
    def test_basic_headers(self, plain_eml_bytes: bytes):
        env = extract_envelope(plain_eml_bytes)
        assert env["message_id"] == "<test-001@example.com>"
        assert env["subject"] == "Test Subject"
        assert env["from"] == "sender@example.com"
        assert env["to"] == ["recipient@example.com"]
        assert env["date"] == "Mon, 01 Jun 2025 12:00:00 +0000"

    def test_cc_and_bcc(self):
        raw = _build_plain_email(
            cc="cc1@example.com, cc2@example.com",
            bcc="bcc@example.com",
        )
        env = extract_envelope(raw)
        assert env["cc"] == ["cc1@example.com", "cc2@example.com"]
        assert env["bcc"] == ["bcc@example.com"]

    def test_no_cc_bcc(self, plain_eml_bytes: bytes):
        env = extract_envelope(plain_eml_bytes)
        assert env["cc"] == []
        assert env["bcc"] == []

    def test_missing_message_id(self):
        from email.mime.text import MIMEText

        msg = MIMEText("body")
        msg["Subject"] = "No ID"
        msg["From"] = "a@b.com"
        msg["To"] = "c@d.com"
        raw = msg.as_bytes()
        env = extract_envelope(raw)
        assert env["message_id"] == ""

    def test_display_name_addresses(self):
        raw = _build_plain_email(
            from_addr="Alice <alice@example.com>",
            to_addr="Bob <bob@example.com>, Charlie <charlie@example.com>",
        )
        env = extract_envelope(raw)
        assert env["from"] == "Alice <alice@example.com>"
        assert env["to"] == ["bob@example.com", "charlie@example.com"]

    def test_multipart_does_not_walk_body(self, multipart_eml_bytes: bytes):
        """Envelope extraction should be fast — it must not parse the body."""
        env = extract_envelope(multipart_eml_bytes)
        assert env["subject"] == "Multipart Email"
        # Should still extract headers correctly
        assert env["from"] == "sender@example.com"
