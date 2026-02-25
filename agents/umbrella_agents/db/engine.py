"""Async SQLAlchemy engine for the agent schema."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from umbrella_agents.config import Settings


class AgentEngine:
    """Holds the engine and session factory for the agent schema.

    Created once at startup and stored on ``app.state``.
    """

    def __init__(self, settings: Settings) -> None:
        self._engine = create_async_engine(
            settings.database_url, echo=False, pool_size=5, max_overflow=10,
        )
        self.session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False,
        )

    async def close(self) -> None:
        await self._engine.dispose()
