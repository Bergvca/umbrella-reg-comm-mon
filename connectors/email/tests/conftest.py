"""Shared test fixtures for the email connector test suite."""

from __future__ import annotations

from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

import pytest

from umbrella_email.config import (
    EmailConnectorConfig,
    EmailProcessorConfig,
    ImapConfig,
    S3Config,
)
from umbrella_email.imap_client import FetchedEmail


@pytest.fixture
def imap_config() -> ImapConfig:
    return ImapConfig(
        host="imap.test.com",
        port=993,
        use_ssl=True,
        username="testuser",
        password="testpass",
        mailbox="INBOX",
        poll_interval_seconds=1.0,
    )


@pytest.fixture
def s3_config() -> S3Config:
    return S3Config(
        bucket="test-bucket",
        prefix="raw/email",
        attachments_prefix="raw/email/attachments",
        region="us-east-1",
    )


@pytest.fixture
def connector_config(imap_config: ImapConfig, s3_config: S3Config) -> EmailConnectorConfig:
    return EmailConnectorConfig(
        name="email-test",
        health_port=18080,
        imap=imap_config,
        s3=s3_config,
    )


@pytest.fixture
def processor_config(s3_config: S3Config) -> EmailProcessorConfig:
    return EmailProcessorConfig(
        kafka_bootstrap_servers="localhost:9092",
        source_topic="raw-messages",
        output_topic="parsed-messages",
        consumer_group="email-processor-test",
        s3=s3_config,
    )


# ------------------------------------------------------------------
# Sample EML builders
# ------------------------------------------------------------------


def _build_plain_email(
    *,
    subject: str = "Test Subject",
    from_addr: str = "sender@example.com",
    to_addr: str = "recipient@example.com",
    body: str = "Hello, World!",
    message_id: str = "<test-001@example.com>",
    cc: str | None = None,
    bcc: str | None = None,
) -> bytes:
    """Build a simple plain-text email as raw bytes."""
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Message-ID"] = message_id
    msg["Date"] = "Mon, 01 Jun 2025 12:00:00 +0000"
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    return msg.as_bytes()


def _build_html_email(*, body_html: str = "<p>Hello</p>") -> bytes:
    msg = MIMEText(body_html, "html")
    msg["Subject"] = "HTML Email"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Message-ID"] = "<html-001@example.com>"
    msg["Date"] = "Mon, 01 Jun 2025 12:00:00 +0000"
    return msg.as_bytes()


def _build_multipart_email(
    *,
    body_text: str = "Plain body",
    body_html: str = "<p>HTML body</p>",
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> bytes:
    """Build a multipart email with text, HTML, and optional attachments."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "Multipart Email"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Message-ID"] = "<multi-001@example.com>"
    msg["Date"] = "Mon, 01 Jun 2025 12:00:00 +0000"

    # Text + HTML alternative
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body_text, "plain"))
    alt.attach(MIMEText(body_html, "html"))
    msg.attach(alt)

    # Attachments
    for filename, content_type, payload in attachments or []:
        maintype, subtype = content_type.split("/", 1)
        part = MIMEBase(maintype, subtype)
        part.set_payload(payload)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    return msg.as_bytes()


@pytest.fixture
def plain_eml_bytes() -> bytes:
    return _build_plain_email()


@pytest.fixture
def html_eml_bytes() -> bytes:
    return _build_html_email()


@pytest.fixture
def multipart_eml_bytes() -> bytes:
    return _build_multipart_email(
        attachments=[
            ("report.pdf", "application/pdf", b"%PDF-1.4 fake pdf content"),
            ("data.csv", "text/csv", b"col1,col2\na,b\n"),
        ],
    )


@pytest.fixture
def fetched_email(plain_eml_bytes: bytes) -> FetchedEmail:
    return FetchedEmail(uid="100", raw_bytes=plain_eml_bytes)
