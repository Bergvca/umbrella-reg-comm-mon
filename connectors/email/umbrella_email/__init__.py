"""Umbrella Email Connector — two-stage IMAP ingestion with claim-check pattern."""

from .config import EmailConnectorConfig, EmailProcessorConfig, ImapConfig, S3Config
from .connector import EmailConnector
from .envelope import extract_envelope
from .imap_client import AsyncImapClient, FetchedEmail
from .parser import MimeParser, ParsedAttachment, ParsedEmail
from .processor import EmailProcessor
from .s3 import S3Store

__all__ = [
    "AsyncImapClient",
    "EmailConnector",
    "EmailConnectorConfig",
    "EmailProcessor",
    "EmailProcessorConfig",
    "FetchedEmail",
    "ImapConfig",
    "MimeParser",
    "ParsedAttachment",
    "ParsedEmail",
    "S3Config",
    "S3Store",
    "extract_envelope",
]
