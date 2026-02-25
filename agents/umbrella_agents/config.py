"""Agent runtime configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the agent runtime service.

    All env vars are prefixed with ``AGENTS_``.
    """

    model_config = SettingsConfigDict(env_prefix="AGENTS_")

    database_url: str = Field(
        description="Async SQLAlchemy URL for the agent_rw role",
    )
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch base URL",
    )
    default_timeout: int = Field(
        default=120,
        description="Max execution time per agent run in seconds",
    )
    max_concurrent_runs: int = Field(
        default=10,
        description="Concurrency limit for agent runs",
    )
    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=8001, description="Bind port")
    log_level: str = Field(default="INFO", description="Log level")
    log_json: bool = Field(
        default=True,
        description="Use JSON log output (True for prod, False for dev)",
    )
