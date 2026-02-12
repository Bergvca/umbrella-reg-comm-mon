"""Email normalizer — transforms EmailProcessor output into NormalizedMessage."""

from __future__ import annotations

import email.utils
import mimetypes
import re
from datetime import datetime, timezone

import structlog

from umbrella_schema import (
    Attachment,
    Channel,
    Direction,
    NormalizedMessage,
    Participant,
)

from ..models import ParsedEmailMessage
from .base import BaseNormalizer

logger = structlog.get_logger()


class EmailNormalizer(BaseNormalizer):
    """Normalize parsed email messages into the canonical schema."""

    def __init__(self, monitored_domains: list[str]) -> None:
        self._monitored_domains = {d.lower() for d in monitored_domains}

    @property
    def channel(self) -> Channel:
        return Channel.EMAIL

    def normalize(self, parsed: dict) -> NormalizedMessage:
        msg = ParsedEmailMessage.model_validate(parsed)

        direction = self._detect_direction(msg)
        participants = self._build_participants(msg)
        attachments = self._build_attachments(msg.attachment_refs)
        timestamp = self._parse_timestamp(msg.date)

        return NormalizedMessage(
            message_id=msg.message_id,
            channel=Channel.EMAIL,
            direction=direction,
            timestamp=timestamp,
            participants=participants,
            body_text=msg.body_text,
            attachments=attachments,
            metadata={
                "subject": msg.subject,
                "body_html": msg.body_html,
                "raw_eml_s3_uri": msg.raw_eml_s3_uri,
                "raw_message_id": msg.raw_message_id,
            },
        )

    # ------------------------------------------------------------------
    # Direction detection
    # ------------------------------------------------------------------

    def _detect_direction(self, msg: ParsedEmailMessage) -> Direction:
        sender_domain = self._extract_domain(msg.from_address)
        sender_monitored = sender_domain in self._monitored_domains

        all_recipients = msg.to + msg.cc + msg.bcc
        recipient_monitored = any(
            self._extract_domain(addr) in self._monitored_domains
            for addr in all_recipients
        )

        if sender_monitored and recipient_monitored:
            return Direction.INTERNAL
        if sender_monitored:
            return Direction.OUTBOUND
        if recipient_monitored:
            return Direction.INBOUND
        # Conservative default for compliance — treat unknown as inbound
        return Direction.INBOUND

    def _extract_domain(self, address: str) -> str:
        """Extract the domain from an email address, handling 'Name <addr>' format."""
        _, addr = email.utils.parseaddr(address)
        if "@" in addr:
            return addr.split("@", 1)[1].lower()
        return ""

    # ------------------------------------------------------------------
    # Participants
    # ------------------------------------------------------------------

    def _build_participants(self, msg: ParsedEmailMessage) -> list[Participant]:
        participants: list[Participant] = []

        # Sender
        name, addr = email.utils.parseaddr(msg.from_address)
        participants.append(Participant(
            id=addr or msg.from_address,
            name=name or addr or msg.from_address,
            role="sender",
        ))

        # To, CC, BCC recipients
        for address, role in [
            (msg.to, "to"),
            (msg.cc, "cc"),
            (msg.bcc, "bcc"),
        ]:
            for raw_addr in address:
                name, addr = email.utils.parseaddr(raw_addr)
                participants.append(Participant(
                    id=addr or raw_addr,
                    name=name or addr or raw_addr,
                    role=role,
                ))

        return participants

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def _build_attachments(self, attachment_refs: list[str]) -> list[Attachment]:
        attachments: list[Attachment] = []
        for s3_uri in attachment_refs:
            filename = self._extract_filename_from_uri(s3_uri)
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            attachments.append(Attachment(
                name=filename,
                content_type=content_type,
                s3_uri=s3_uri,
            ))
        return attachments

    @staticmethod
    def _extract_filename_from_uri(s3_uri: str) -> str:
        """Extract original filename from S3 URI pattern ``{hash}_{filename}``."""
        # Get the last path component
        last_segment = s3_uri.rsplit("/", 1)[-1]
        # Pattern: {hash}_{filename} — split on first underscore
        match = re.match(r"^[a-f0-9]+_(.+)$", last_segment)
        if match:
            return match.group(1)
        return last_segment

    # ------------------------------------------------------------------
    # Timestamp
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_timestamp(date_str: str) -> datetime:
        """Parse RFC 2822 date string to UTC datetime."""
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc)
