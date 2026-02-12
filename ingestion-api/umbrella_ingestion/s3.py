"""S3 storage for normalized messages.

All boto3 calls are wrapped with ``asyncio.to_thread()`` to avoid blocking.
"""

from __future__ import annotations

import asyncio
import json

import structlog

from umbrella_schema import NormalizedMessage

from .config import S3Config

logger = structlog.get_logger()


class NormalizedS3Store:
    """Persist normalized messages as JSON to S3."""

    def __init__(self, config: S3Config) -> None:
        self._config = config
        self._client = None  # type: ignore[assignment]

    async def start(self) -> None:
        """Create the boto3 S3 client."""
        import boto3

        kwargs: dict = {"region_name": self._config.region}
        if self._config.endpoint_url:
            kwargs["endpoint_url"] = self._config.endpoint_url
        self._client = await asyncio.to_thread(boto3.client, "s3", **kwargs)
        logger.info("normalized_s3_store_started", bucket=self._config.bucket)

    async def stop(self) -> None:
        """Clean up the boto3 client."""
        self._client = None
        logger.info("normalized_s3_store_stopped")

    async def store(self, message: NormalizedMessage) -> str:
        """Persist a normalized message to S3.

        Key format: ``{prefix}/{channel}/{YYYY/MM/DD}/{message_id}.json``

        Returns the ``s3://`` URI.
        """
        assert self._client is not None, "S3 client not started"

        channel = message.channel.value
        date_path = message.timestamp.strftime("%Y/%m/%d")
        safe_id = message.message_id.replace("<", "").replace(">", "").replace("/", "_")
        key = f"{self._config.prefix}/{channel}/{date_path}/{safe_id}.json"

        body = message.model_dump_json(indent=2)
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._config.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )

        uri = f"s3://{self._config.bucket}/{key}"
        logger.debug("normalized_message_stored", uri=uri, message_id=message.message_id)
        return uri
