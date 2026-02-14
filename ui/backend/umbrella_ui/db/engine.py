"""Async SQLAlchemy engines — one per database role."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from umbrella_ui.config import Settings


def _make_engine(url: str):
    return create_async_engine(url, echo=False, pool_size=5, max_overflow=10)


def _make_session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class DatabaseEngines:
    """Holds all four engines and their session factories.

    Created once at startup and stored on ``app.state``.
    """

    def __init__(self, settings: Settings) -> None:
        self.iam_engine = _make_engine(settings.iam_database_url)
        self.policy_engine = _make_engine(settings.policy_database_url)
        self.alert_engine = _make_engine(settings.alert_database_url)
        self.review_engine = _make_engine(settings.review_database_url)

        self.iam_session = _make_session_factory(self.iam_engine)
        self.policy_session = _make_session_factory(self.policy_engine)
        self.alert_session = _make_session_factory(self.alert_engine)
        self.review_session = _make_session_factory(self.review_engine)

    async def close(self) -> None:
        await self.iam_engine.dispose()
        await self.policy_engine.dispose()
        await self.alert_engine.dispose()
        await self.review_engine.dispose()
