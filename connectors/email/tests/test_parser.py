"""Tests for umbrella_email.parser."""

from __future__ import annotations

import pytest

from tests.conftest import _build_html_email, _build_multipart_email, _build_plain_email

from umbrella_email.parser import MimeParser


@pytest.fixture
def parser() -> MimeParser:
    return MimeParser()


class TestMimeParserPlainText:
    def test_parse_plain_email(self, parser: MimeParser, plain_eml_bytes: bytes):
        result = parser.parse(plain_eml_bytes)
        assert result.message_id == "<test-001@example.com>"
        assert result.subject == "Test Subject"
        assert result.from_address == "sender@example.com"
        assert result.to_addresses == ["recipient@example.com"]
        assert result.body_text == "Hello, World!"
        assert result.body_html is None
        assert result.attachments == []

    def test_headers_dict(self, parser: MimeParser, plain_eml_bytes: bytes):
        result = parser.parse(plain_eml_bytes)
        assert "Subject" in result.headers
        assert "From" in result.headers


class TestMimeParserHtml:
    def test_parse_html_email(self, parser: MimeParser, html_eml_bytes: bytes):
        result = parser.parse(html_eml_bytes)
        assert result.body_text is None
        assert result.body_html == "<p>Hello</p>"


class TestMimeParserMultipart:
    def test_parse_multipart_bodies(self, parser: MimeParser):
        raw = _build_multipart_email(
            body_text="Plain text",
            body_html="<p>HTML</p>",
        )
        result = parser.parse(raw)
        assert result.body_text == "Plain text"
        assert result.body_html == "<p>HTML</p>"

    def test_parse_multipart_with_attachments(
        self, parser: MimeParser, multipart_eml_bytes: bytes
    ):
        result = parser.parse(multipart_eml_bytes)
        assert len(result.attachments) == 2
        filenames = [a.filename for a in result.attachments]
        assert "report.pdf" in filenames
        assert "data.csv" in filenames

    def test_attachment_content_types(self, parser: MimeParser, multipart_eml_bytes: bytes):
        result = parser.parse(multipart_eml_bytes)
        types = {a.filename: a.content_type for a in result.attachments}
        assert types["report.pdf"] == "application/pdf"
        assert types["data.csv"] == "text/csv"

    def test_attachment_payloads_are_bytes(self, parser: MimeParser, multipart_eml_bytes: bytes):
        result = parser.parse(multipart_eml_bytes)
        for att in result.attachments:
            assert isinstance(att.payload, bytes)
            assert len(att.payload) > 0


class TestMimeParserEdgeCases:
    def test_no_message_id(self, parser: MimeParser):
        from email.mime.text import MIMEText

        msg = MIMEText("body")
        msg["Subject"] = "No ID"
        msg["From"] = "a@b.com"
        msg["To"] = "c@d.com"
        result = parser.parse(msg.as_bytes())
        assert result.message_id == ""

    def test_multiple_recipients(self, parser: MimeParser):
        raw = _build_plain_email(to_addr="a@b.com, c@d.com, e@f.com")
        result = parser.parse(raw)
        assert len(result.to_addresses) == 3

    def test_empty_body(self, parser: MimeParser):
        raw = _build_plain_email(body="")
        result = parser.parse(raw)
        assert result.body_text == ""

    def test_cc_and_bcc(self, parser: MimeParser):
        raw = _build_plain_email(cc="cc@example.com", bcc="bcc@example.com")
        result = parser.parse(raw)
        assert result.cc_addresses == ["cc@example.com"]
        assert result.bcc_addresses == ["bcc@example.com"]
