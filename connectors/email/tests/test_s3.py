"""Tests for umbrella_email.s3."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from umbrella_email.config import S3Config
from umbrella_email.parser import ParsedAttachment
from umbrella_email.s3 import S3Store, _parse_s3_uri, _sanitize_filename


@pytest.fixture
def store(s3_config: S3Config) -> S3Store:
    return S3Store(s3_config)


class TestS3StoreLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_client(self, store: S3Store):
        with patch("umbrella_email.s3.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            await store.start()
            mock_boto3.client.assert_called_once_with(
                "s3", region_name="us-east-1"
            )

    @pytest.mark.asyncio
    async def test_start_with_endpoint_url(self):
        config = S3Config(bucket="b", endpoint_url="http://minio:9000")
        store = S3Store(config)
        with patch("umbrella_email.s3.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            await store.start()
            mock_boto3.client.assert_called_once_with(
                "s3", region_name="us-east-1", endpoint_url="http://minio:9000"
            )

    @pytest.mark.asyncio
    async def test_stop(self, store: S3Store):
        with patch("umbrella_email.s3.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            await store.start()
            await store.stop()
            assert store._client is None


class TestS3StoreUploadRawEml:
    @pytest.mark.asyncio
    async def test_upload_raw_eml(self, store: S3Store):
        mock_client = MagicMock()
        with patch("umbrella_email.s3.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            await store.start()

            uri = await store.upload_raw_eml("42", b"raw email bytes")

            assert uri == "s3://test-bucket/raw/email/42.eml"
            mock_client.put_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="raw/email/42.eml",
                Body=b"raw email bytes",
                ContentType="message/rfc822",
            )


class TestS3StoreDownloadRawEml:
    @pytest.mark.asyncio
    async def test_download_raw_eml(self, store: S3Store):
        mock_body = MagicMock()
        mock_body.read.return_value = b"downloaded bytes"
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": mock_body}

        with patch("umbrella_email.s3.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            await store.start()

            data = await store.download_raw_eml("s3://test-bucket/raw/email/42.eml")

            assert data == b"downloaded bytes"
            mock_client.get_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="raw/email/42.eml",
            )


class TestS3StoreUploadAttachment:
    @pytest.mark.asyncio
    async def test_upload_single_attachment(self, store: S3Store):
        mock_client = MagicMock()
        with patch("umbrella_email.s3.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            await store.start()

            att = ParsedAttachment(
                filename="report.pdf",
                content_type="application/pdf",
                payload=b"fake pdf",
            )
            uri = await store.upload_attachment("42", att)

            assert uri.startswith("s3://test-bucket/raw/email/attachments/42/")
            assert uri.endswith("_report.pdf")
            mock_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_multiple_attachments(self, store: S3Store):
        mock_client = MagicMock()
        with patch("umbrella_email.s3.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            await store.start()

            attachments = [
                ParsedAttachment(filename="a.txt", content_type="text/plain", payload=b"aaa"),
                ParsedAttachment(filename="b.txt", content_type="text/plain", payload=b"bbb"),
            ]
            uris = await store.upload_attachments("99", attachments)

            assert len(uris) == 2
            assert all(u.startswith("s3://") for u in uris)
            assert mock_client.put_object.call_count == 2


class TestS3Helpers:
    def test_parse_s3_uri(self):
        bucket, key = _parse_s3_uri("s3://my-bucket/path/to/file.eml")
        assert bucket == "my-bucket"
        assert key == "path/to/file.eml"

    def test_parse_s3_uri_invalid(self):
        with pytest.raises(ValueError, match="Invalid S3 URI"):
            _parse_s3_uri("https://not-s3/path")

    def test_sanitize_filename(self):
        assert _sanitize_filename("report.pdf") == "report.pdf"
        assert _sanitize_filename("my file (1).doc") == "my_file__1_.doc"
        assert _sanitize_filename("../../etc/passwd") == ".._.._etc_passwd"
