"""S3 storage for raw EML files and parsed attachments.

All boto3 calls are wrapped with ``asyncio.to_thread()`` to avoid blocking.
"""

from __future__ import annotations

import asyncio
import hashlib
import re

import boto3
import structlog

from .config import S3Config
from .parser import ParsedAttachment

logger = structlog.get_logger()


class S3Store:
    """Upload raw EML bytes, download for processing, and upload parsed attachments."""

    def __init__(self, config: S3Config) -> None:
        self._config = config
        self._client = None  # type: ignore[assignment]

    async def start(self) -> None:
        """Create the boto3 S3 client."""
        kwargs: dict = {"region_name": self._config.region}
        if self._config.endpoint_url:
            kwargs["endpoint_url"] = self._config.endpoint_url
        self._client = await asyncio.to_thread(boto3.client, "s3", **kwargs)
        logger.info("s3_store_started", bucket=self._config.bucket)

    async def stop(self) -> None:
        """Clean up the boto3 client."""
        self._client = None
        logger.info("s3_store_stopped")

    # ------------------------------------------------------------------
    # Raw EML (Stage 1: upload, Stage 2: download)
    # ------------------------------------------------------------------

    async def upload_raw_eml(self, uid: str, raw_bytes: bytes) -> str:
        """Upload raw EML bytes to S3.  Returns the ``s3://`` URI."""
        assert self._client is not None, "S3 client not started"
        key = f"{self._config.prefix}/{uid}.eml"
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._config.bucket,
            Key=key,
            Body=raw_bytes,
            ContentType="message/rfc822",
        )
        uri = f"s3://{self._config.bucket}/{key}"
        logger.debug("raw_eml_uploaded", uid=uid, uri=uri, size=len(raw_bytes))
        return uri

    async def download_raw_eml(self, s3_uri: str) -> bytes:
        """Download raw EML bytes from an ``s3://`` URI."""
        assert self._client is not None, "S3 client not started"
        bucket, key = _parse_s3_uri(s3_uri)
        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=bucket,
            Key=key,
        )
        raw_bytes: bytes = await asyncio.to_thread(response["Body"].read)
        logger.debug("raw_eml_downloaded", uri=s3_uri, size=len(raw_bytes))
        return raw_bytes

    # ------------------------------------------------------------------
    # Parsed attachments (Stage 2)
    # ------------------------------------------------------------------

    async def upload_attachment(
        self,
        email_uid: str,
        attachment: ParsedAttachment,
    ) -> str:
        """Upload a single parsed attachment. Returns the ``s3://`` URI."""
        assert self._client is not None, "S3 client not started"
        content_hash = hashlib.sha256(attachment.payload).hexdigest()[:12]
        safe_name = _sanitize_filename(attachment.filename)
        key = f"{self._config.attachments_prefix}/{email_uid}/{content_hash}_{safe_name}"

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._config.bucket,
            Key=key,
            Body=attachment.payload,
            ContentType=attachment.content_type,
        )
        uri = f"s3://{self._config.bucket}/{key}"
        logger.debug(
            "attachment_uploaded",
            email_uid=email_uid,
            filename=attachment.filename,
            uri=uri,
        )
        return uri

    async def upload_attachments(
        self,
        email_uid: str,
        attachments: list[ParsedAttachment],
    ) -> list[str]:
        """Upload all attachments for an email. Returns list of S3 URIs."""
        uris: list[str] = []
        for att in attachments:
            uri = await self.upload_attachment(email_uid, att)
            uris.append(uri)
        return uris


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse ``s3://bucket/key`` into (bucket, key)."""
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    without_scheme = uri[5:]
    bucket, _, key = without_scheme.partition("/")
    return bucket, key


def _sanitize_filename(name: str) -> str:
    """Remove characters unsafe for S3 keys."""
    return re.sub(r"[^\w.\-]", "_", name)
