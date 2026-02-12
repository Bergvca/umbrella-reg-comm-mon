"""Stage 1 — EmailConnector: poll IMAP, upload raw EML to S3, yield
lightweight RawMessage references to Kafka.
"""

from __future__ import annotations

import asyncio
import imaplib
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import structlog

from umbrella_connector import BackfillRequest, BaseConnector, RawMessage
from umbrella_schema import Channel

from .config import EmailConnectorConfig
from .envelope import extract_envelope
from .imap_client import AsyncImapClient, FetchedEmail
from .s3 import S3Store

logger = structlog.get_logger()


class EmailConnector(BaseConnector):
    """Email connector — IMAP polling with S3 claim-check pattern.

    Uploads raw EML bytes to S3 immediately (no data loss), then yields
    a lightweight ``RawMessage`` (~1–2 KB) with envelope headers and the
    S3 URI.  Full MIME parsing happens in Stage 2 (``EmailProcessor``).
    """

    def __init__(self, config: EmailConnectorConfig) -> None:
        super().__init__(config)
        self._email_config = config
        self._imap = AsyncImapClient(config.imap)
        self._s3 = S3Store(config.s3)
        self._last_poll_time: datetime | None = None
        self._messages_ingested: int = 0

    async def ingest(self) -> AsyncIterator[RawMessage]:
        """Poll IMAP indefinitely, yield RawMessage for each email."""
        await self._imap.connect()
        await self._s3.start()

        try:
            while True:
                try:
                    fetched = await self._imap.poll_new_messages()
                except imaplib.IMAP4.error:
                    logger.warning("imap_connection_lost, reconnecting")
                    await self._imap.connect()
                    continue

                self._last_poll_time = datetime.now(UTC)

                for email_data in fetched:
                    raw_msg = await self._process_email(email_data)
                    self._messages_ingested += 1
                    yield raw_msg

                await asyncio.sleep(self._email_config.imap.poll_interval_seconds)
        finally:
            await self._imap.disconnect()
            await self._s3.stop()

    async def _process_email(self, email_data: FetchedEmail) -> RawMessage:
        """Upload raw EML to S3 and extract envelope headers."""
        # Claim-check: persist raw bytes to S3 first
        s3_uri = await self._s3.upload_raw_eml(email_data.uid, email_data.raw_bytes)

        # Lightweight header-only extraction (no MIME walk)
        envelope = extract_envelope(email_data.raw_bytes)

        raw_message_id = envelope.get("message_id") or f"imap-uid-{email_data.uid}"

        return RawMessage(
            raw_message_id=raw_message_id,
            channel=Channel.EMAIL,
            raw_payload={
                "envelope": envelope,
                "s3_uri": s3_uri,
                "size_bytes": len(email_data.raw_bytes),
            },
            raw_format="eml_ref",
            metadata={
                "imap_uid": email_data.uid,
                "mailbox": self._email_config.imap.mailbox,
                "imap_host": self._email_config.imap.host,
            },
        )

    async def health_check(self) -> dict[str, object]:
        connected = await self._imap.is_connected()
        return {
            "imap_connected": connected,
            "imap_host": self._email_config.imap.host,
            "imap_mailbox": self._email_config.imap.mailbox,
            "last_poll_time": (
                self._last_poll_time.isoformat() if self._last_poll_time else None
            ),
            "last_uid": self._imap.last_uid,
            "messages_ingested": self._messages_ingested,
        }

    async def backfill(self, request: BackfillRequest) -> AsyncIterator[RawMessage]:
        """Backfill emails from IMAP by date range."""
        await self._imap.connect()
        await self._s3.start()

        try:
            fetched = await self._imap.search_by_date_range(request.start, request.end)
            logger.info(
                "backfill_fetched",
                count=len(fetched),
                start=request.start.isoformat(),
                end=request.end.isoformat(),
            )
            for email_data in fetched:
                yield await self._process_email(email_data)
        finally:
            await self._imap.disconnect()
            await self._s3.stop()
