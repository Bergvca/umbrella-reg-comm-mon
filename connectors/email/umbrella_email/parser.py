"""Full MIME parser for Stage 2 — walks the entire message to extract
body text, HTML, attachments, and all headers.
"""

from __future__ import annotations

import email
import email.policy
import email.utils
from dataclasses import dataclass, field


@dataclass
class ParsedAttachment:
    """A single attachment extracted from a MIME email."""

    filename: str
    content_type: str
    payload: bytes


@dataclass
class ParsedEmail:
    """Structured representation of a fully parsed email."""

    message_id: str
    subject: str
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    bcc_addresses: list[str]
    date: str
    body_text: str | None
    body_html: str | None
    headers: dict[str, str]
    attachments: list[ParsedAttachment] = field(default_factory=list)


class MimeParser:
    """Stateless parser: raw RFC 822 bytes → ParsedEmail."""

    def parse(self, raw_bytes: bytes) -> ParsedEmail:
        msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

        body_text, body_html = self._extract_bodies(msg)
        attachments = self._extract_attachments(msg)

        return ParsedEmail(
            message_id=msg.get("Message-ID", ""),
            subject=msg.get("Subject", ""),
            from_address=msg.get("From", ""),
            to_addresses=self._parse_address_list(msg.get("To")),
            cc_addresses=self._parse_address_list(msg.get("Cc")),
            bcc_addresses=self._parse_address_list(msg.get("Bcc")),
            date=msg.get("Date", ""),
            body_text=body_text,
            body_html=body_html,
            headers={k: str(v) for k, v in msg.items()},
            attachments=attachments,
        )

    def _extract_bodies(self, msg: email.message.Message) -> tuple[str | None, str | None]:
        """Walk MIME parts and return (plain_text, html_text)."""
        body_text: str | None = None
        body_html: str | None = None

        if not msg.is_multipart():
            content_type = msg.get_content_type()
            payload = msg.get_content()
            if content_type == "text/plain" and isinstance(payload, str):
                body_text = payload
            elif content_type == "text/html" and isinstance(payload, str):
                body_html = payload
            return body_text, body_html

        for part in msg.walk():
            # Skip multipart containers — they have no content of their own
            if part.get_content_maintype() == "multipart":
                continue

            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            # Skip attachment parts
            if "attachment" in disposition:
                continue

            payload = part.get_content()
            if content_type == "text/plain" and isinstance(payload, str) and body_text is None:
                body_text = payload
            elif content_type == "text/html" and isinstance(payload, str) and body_html is None:
                body_html = payload

        return body_text, body_html

    def _extract_attachments(self, msg: email.message.Message) -> list[ParsedAttachment]:
        """Walk MIME parts and collect attachments."""
        attachments: list[ParsedAttachment] = []

        for part in msg.walk():
            disposition = str(part.get("Content-Disposition", ""))
            filename = part.get_filename()

            # Attachment: has Content-Disposition: attachment, or is a named non-text part
            if "attachment" in disposition or (
                filename and part.get_content_maintype() != "multipart"
            ):
                payload = part.get_content()
                if isinstance(payload, bytes):
                    raw = payload
                elif isinstance(payload, str):
                    raw = payload.encode("utf-8")
                else:
                    continue

                attachments.append(
                    ParsedAttachment(
                        filename=filename or "unnamed",
                        content_type=part.get_content_type(),
                        payload=raw,
                    )
                )

        return attachments

    def _parse_address_list(self, header_value: str | None) -> list[str]:
        if not header_value:
            return []
        return [addr for _, addr in email.utils.getaddresses([header_value]) if addr]
