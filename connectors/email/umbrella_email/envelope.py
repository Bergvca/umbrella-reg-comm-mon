"""Lightweight envelope extraction from raw EML bytes.

Uses ``email.parser.BytesHeaderParser`` which parses *only* the headers
without walking the MIME body.  This is O(header-size), not O(message-size),
making it suitable for Stage 1 where raw EML can be 3–20 MB.
"""

from __future__ import annotations

import email.parser
import email.utils
from typing import Any


def extract_envelope(raw_bytes: bytes) -> dict[str, Any]:
    """Extract envelope headers from raw RFC 822 bytes.

    Returns a dict with: subject, from, to, cc, bcc, date, message_id.
    """
    parser = email.parser.BytesHeaderParser()
    headers = parser.parsebytes(raw_bytes)

    return {
        "message_id": headers.get("Message-ID", ""),
        "subject": headers.get("Subject", ""),
        "from": headers.get("From", ""),
        "to": _parse_address_list(headers.get("To")),
        "cc": _parse_address_list(headers.get("Cc")),
        "bcc": _parse_address_list(headers.get("Bcc")),
        "date": headers.get("Date", ""),
    }


def _parse_address_list(header_value: str | None) -> list[str]:
    """Parse an RFC 2822 address list into a list of email addresses."""
    if not header_value:
        return []
    return [addr for _, addr in email.utils.getaddresses([header_value]) if addr]
