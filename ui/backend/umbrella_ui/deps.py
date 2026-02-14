"""FastAPI dependency-injection helpers for database sessions."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from elasticsearch import AsyncElasticsearch
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_iam_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.db.iam_session() as session:
        yield session


async def get_policy_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.db.policy_session() as session:
        yield session


async def get_alert_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.db.alert_session() as session:
        yield session


async def get_review_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.db.review_session() as session:
        yield session


async def get_es(request: Request) -> AsyncElasticsearch:
    return request.app.state.es.client


def get_settings(request: Request):
    from umbrella_ui.config import Settings
    return request.app.state.settings
