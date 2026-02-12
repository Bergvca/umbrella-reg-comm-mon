"""Async IMAP client wrapping stdlib imaplib with asyncio.to_thread."""

from __future__ import annotations

import asyncio
import imaplib
from dataclasses import dataclass
from datetime import datetime

import structlog

from .config import ImapConfig

logger = structlog.get_logger()


@dataclass
class FetchedEmail:
    """Raw email data fetched from IMAP."""

    uid: str
    raw_bytes: bytes


class AsyncImapClient:
    """Async-friendly IMAP client.

    All blocking ``imaplib`` operations are wrapped with
    ``asyncio.to_thread()`` to avoid blocking the event loop.
    """

    def __init__(self, config: ImapConfig) -> None:
        self._config = config
        self._conn: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None
        self._last_uid: str = "0"

    @property
    def last_uid(self) -> str:
        return self._last_uid

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect, login, and select the configured mailbox."""
        await asyncio.to_thread(self._connect_sync)
        logger.info(
            "imap_connected",
            host=self._config.host,
            mailbox=self._config.mailbox,
        )

    def _connect_sync(self) -> None:
        if self._config.use_ssl:
            self._conn = imaplib.IMAP4_SSL(self._config.host, self._config.port)
        else:
            self._conn = imaplib.IMAP4(self._config.host, self._config.port)
        self._conn.login(self._config.username, self._config.password.get_secret_value())
        self._conn.select(self._config.mailbox)

    async def disconnect(self) -> None:
        """Close mailbox and logout."""
        if self._conn is not None:
            await asyncio.to_thread(self._disconnect_sync)
            self._conn = None
            logger.info("imap_disconnected")

    def _disconnect_sync(self) -> None:
        assert self._conn is not None
        try:
            self._conn.close()
        except imaplib.IMAP4.error:
            pass
        try:
            self._conn.logout()
        except imaplib.IMAP4.error:
            pass

    async def is_connected(self) -> bool:
        """Check connection liveness with a NOOP command."""
        if self._conn is None:
            return False
        try:
            status, _ = await asyncio.to_thread(self._conn.noop)
            return status == "OK"
        except (imaplib.IMAP4.error, OSError):
            return False

    # ------------------------------------------------------------------
    # Message retrieval
    # ------------------------------------------------------------------

    async def poll_new_messages(self) -> list[FetchedEmail]:
        """Fetch messages with UID greater than the last seen UID.

        Updates ``last_uid`` after each successful poll.
        """
        assert self._conn is not None, "Not connected"
        next_uid = str(int(self._last_uid) + 1)
        criteria = f"UID {next_uid}:*"
        return await asyncio.to_thread(self._search_and_fetch, criteria)

    async def search_by_date_range(
        self,
        since: datetime,
        before: datetime,
    ) -> list[FetchedEmail]:
        """Search for messages within a date range (for backfill).

        IMAP date search is day-granular (not timestamp-granular).
        """
        assert self._conn is not None, "Not connected"
        since_str = since.strftime("%d-%b-%Y")
        before_str = before.strftime("%d-%b-%Y")
        criteria = f"SINCE {since_str} BEFORE {before_str}"
        return await asyncio.to_thread(self._search_and_fetch, criteria)

    # ------------------------------------------------------------------
    # Synchronous helpers (run in thread)
    # ------------------------------------------------------------------

    def _search_and_fetch(self, criteria: str) -> list[FetchedEmail]:
        assert self._conn is not None
        status, data = self._conn.uid("SEARCH", None, criteria)
        if status != "OK" or not data[0]:
            return []

        uid_list = data[0].split()
        results: list[FetchedEmail] = []

        for uid_bytes in uid_list:
            uid = uid_bytes.decode()
            # Skip UIDs we've already seen (IMAP UID ranges are inclusive
            # and may return the last_uid itself)
            if int(uid) <= int(self._last_uid):
                continue

            status, msg_data = self._conn.uid("FETCH", uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw_bytes: bytes = msg_data[0][1]  # type: ignore[index]
            results.append(FetchedEmail(uid=uid, raw_bytes=raw_bytes))

            if int(uid) > int(self._last_uid):
                self._last_uid = uid

        logger.debug("imap_poll_complete", fetched=len(results), last_uid=self._last_uid)
        return results
