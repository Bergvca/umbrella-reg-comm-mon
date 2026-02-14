"""UI backend configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level settings for the UI backend.

    All env vars are prefixed with ``UMBRELLA_UI_``.
    Example: ``UMBRELLA_UI_JWT_SECRET=mysecret``
    """

    model_config = SettingsConfigDict(env_prefix="UMBRELLA_UI_")

    # --- Database -----------------------------------------------------------
    iam_database_url: str = Field(
        description="Async SQLAlchemy URL for the iam_rw role",
    )
    policy_database_url: str = Field(
        description="Async SQLAlchemy URL for the policy_rw role",
    )
    alert_database_url: str = Field(
        description="Async SQLAlchemy URL for the alert_rw role",
    )
    review_database_url: str = Field(
        description="Async SQLAlchemy URL for the review_rw role",
    )

    # --- JWT ----------------------------------------------------------------
    jwt_secret: str = Field(
        description="Secret key used to sign JWT tokens",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="Access token lifetime in minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token lifetime in days",
    )

    # --- Elasticsearch ---------------------------------------------------
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch base URL",
    )

    # --- S3 / MinIO ------------------------------------------------------
    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        description="S3-compatible endpoint URL",
    )
    s3_bucket: str = Field(
        default="umbrella",
        description="S3 bucket name for attachments and audio",
    )
    s3_region: str = Field(
        default="us-east-1",
        description="S3 region",
    )
    s3_presigned_url_expiry: int = Field(
        default=3600,
        description="Pre-signed URL expiry in seconds",
    )

    # --- Server -------------------------------------------------------------
    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=8000, description="Bind port")
    log_level: str = Field(default="INFO", description="Log level")
    log_json: bool = Field(
        default=True,
        description="Use JSON log output (True for prod, False for dev)",
    )
