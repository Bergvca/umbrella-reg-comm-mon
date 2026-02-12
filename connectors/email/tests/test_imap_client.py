"""Tests for umbrella_email.imap_client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from umbrella_email.config import ImapConfig
from umbrella_email.imap_client import AsyncImapClient, FetchedEmail


@pytest.fixture
def client(imap_config: ImapConfig) -> AsyncImapClient:
    return AsyncImapClient(imap_config)


def _make_mock_imap(
    *,
    search_uids: list[bytes] | None = None,
    fetch_data: dict[bytes, bytes] | None = None,
) -> MagicMock:
    """Create a mock imaplib.IMAP4_SSL with programmed responses."""
    mock = MagicMock()
    mock.login.return_value = ("OK", [b"Logged in"])
    mock.select.return_value = ("OK", [b"1"])
    mock.close.return_value = ("OK", [b"Closed"])
    mock.logout.return_value = ("BYE", [b"Bye"])
    mock.noop.return_value = ("OK", [b""])

    uid_data = b" ".join(search_uids) if search_uids else b""
    mock.uid.side_effect = _make_uid_handler(uid_data, fetch_data or {})
    return mock


def _make_uid_handler(search_data: bytes, fetch_data: dict[bytes, bytes]):
    """Build a side_effect function for mock.uid() that handles SEARCH and FETCH."""

    def handler(command: str, *args):
        if command == "SEARCH":
            return ("OK", [search_data])
        elif command == "FETCH":
            uid = args[0].encode() if isinstance(args[0], str) else args[0]
            raw = fetch_data.get(uid, b"")
            if raw:
                return ("OK", [(b"1 (RFC822 {%d})" % len(raw), raw)])
            return ("OK", [None])
        return ("OK", [b""])

    return handler


class TestAsyncImapClientConnect:
    @pytest.mark.asyncio
    async def test_connect_ssl(self, client: AsyncImapClient):
        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            mock_conn = _make_mock_imap()
            MockSSL.return_value = mock_conn
            await client.connect()
            MockSSL.assert_called_once_with("imap.test.com", 993)
            mock_conn.login.assert_called_once_with("testuser", "testpass")
            mock_conn.select.assert_called_once_with("INBOX")

    @pytest.mark.asyncio
    async def test_connect_non_ssl(self, imap_config: ImapConfig):
        config = ImapConfig(
            host="imap.test.com",
            port=143,
            use_ssl=False,
            username="u",
            password="p",
        )
        client = AsyncImapClient(config)
        with patch("umbrella_email.imap_client.imaplib.IMAP4") as MockIMAP:
            mock_conn = _make_mock_imap()
            MockIMAP.return_value = mock_conn
            await client.connect()
            MockIMAP.assert_called_once_with("imap.test.com", 143)


class TestAsyncImapClientPoll:
    @pytest.mark.asyncio
    async def test_poll_empty(self, client: AsyncImapClient):
        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            MockSSL.return_value = _make_mock_imap(search_uids=[])
            await client.connect()
            results = await client.poll_new_messages()
            assert results == []

    @pytest.mark.asyncio
    async def test_poll_returns_messages(self, client: AsyncImapClient, plain_eml_bytes: bytes):
        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            MockSSL.return_value = _make_mock_imap(
                search_uids=[b"1", b"2"],
                fetch_data={b"1": plain_eml_bytes, b"2": plain_eml_bytes},
            )
            await client.connect()
            results = await client.poll_new_messages()
            assert len(results) == 2
            assert all(isinstance(r, FetchedEmail) for r in results)
            assert results[0].uid == "1"
            assert results[1].uid == "2"

    @pytest.mark.asyncio
    async def test_poll_updates_last_uid(self, client: AsyncImapClient, plain_eml_bytes: bytes):
        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            MockSSL.return_value = _make_mock_imap(
                search_uids=[b"5", b"10"],
                fetch_data={b"5": plain_eml_bytes, b"10": plain_eml_bytes},
            )
            await client.connect()
            await client.poll_new_messages()
            assert client.last_uid == "10"

    @pytest.mark.asyncio
    async def test_poll_skips_already_seen(self, client: AsyncImapClient, plain_eml_bytes: bytes):
        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            MockSSL.return_value = _make_mock_imap(
                search_uids=[b"5"],
                fetch_data={b"5": plain_eml_bytes},
            )
            await client.connect()
            # First poll
            results1 = await client.poll_new_messages()
            assert len(results1) == 1

            # Re-mock with same UID (IMAP UID range is inclusive)
            MockSSL.return_value = _make_mock_imap(
                search_uids=[b"5"],
                fetch_data={b"5": plain_eml_bytes},
            )
            await client.connect()
            results2 = await client.poll_new_messages()
            assert len(results2) == 0


class TestAsyncImapClientSearch:
    @pytest.mark.asyncio
    async def test_search_by_date_range(self, client: AsyncImapClient, plain_eml_bytes: bytes):
        from datetime import datetime, timezone

        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            mock_conn = _make_mock_imap(
                search_uids=[b"1"],
                fetch_data={b"1": plain_eml_bytes},
            )
            MockSSL.return_value = mock_conn
            await client.connect()

            since = datetime(2025, 1, 1, tzinfo=timezone.utc)
            before = datetime(2025, 1, 31, tzinfo=timezone.utc)
            results = await client.search_by_date_range(since, before)
            assert len(results) == 1

            # Verify the SEARCH criteria format
            mock_conn.uid.assert_any_call("SEARCH", None, "SINCE 01-Jan-2025 BEFORE 31-Jan-2025")


class TestAsyncImapClientDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect(self, client: AsyncImapClient):
        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            mock_conn = _make_mock_imap()
            MockSSL.return_value = mock_conn
            await client.connect()
            await client.disconnect()
            mock_conn.close.assert_called_once()
            mock_conn.logout.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, client: AsyncImapClient):
        await client.disconnect()  # should not raise


class TestAsyncImapClientHealth:
    @pytest.mark.asyncio
    async def test_is_connected_true(self, client: AsyncImapClient):
        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            MockSSL.return_value = _make_mock_imap()
            await client.connect()
            assert await client.is_connected() is True

    @pytest.mark.asyncio
    async def test_is_connected_false_when_not_connected(self, client: AsyncImapClient):
        assert await client.is_connected() is False

    @pytest.mark.asyncio
    async def test_is_connected_false_on_error(self, client: AsyncImapClient):
        import imaplib

        with patch("umbrella_email.imap_client.imaplib.IMAP4_SSL") as MockSSL:
            mock_conn = _make_mock_imap()
            mock_conn.noop.side_effect = imaplib.IMAP4.error("broken")
            MockSSL.return_value = mock_conn
            await client.connect()
            assert await client.is_connected() is False
