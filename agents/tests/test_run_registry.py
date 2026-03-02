"""Tests for the RunRegistry."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from umbrella_agents.run_registry import RunRegistry


def _make_task() -> asyncio.Task:
    """Create a dummy task."""

    async def noop():
        await asyncio.sleep(3600)

    return asyncio.create_task(noop())


@pytest.mark.asyncio
async def test_register_and_get():
    registry = RunRegistry()
    run_id = uuid.uuid4()
    queue = asyncio.Queue()
    cancelled = asyncio.Event()
    task = _make_task()

    managed = registry.register(run_id, task, queue, cancelled)
    assert managed.run_id == run_id
    assert registry.get(run_id) is managed
    assert registry.active_count == 1

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_get_missing_returns_none():
    registry = RunRegistry()
    assert registry.get(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_cancel_sets_event():
    registry = RunRegistry()
    run_id = uuid.uuid4()
    queue = asyncio.Queue()
    cancelled = asyncio.Event()
    task = _make_task()

    registry.register(run_id, task, queue, cancelled)
    assert not cancelled.is_set()

    result = registry.cancel(run_id)
    assert result is True
    assert cancelled.is_set()

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_cancel_missing_returns_false():
    registry = RunRegistry()
    assert registry.cancel(uuid.uuid4()) is False


@pytest.mark.asyncio
async def test_remove():
    registry = RunRegistry()
    run_id = uuid.uuid4()
    queue = asyncio.Queue()
    cancelled = asyncio.Event()
    task = _make_task()

    registry.register(run_id, task, queue, cancelled)
    assert registry.active_count == 1

    registry.remove(run_id)
    assert registry.active_count == 0
    assert registry.get(run_id) is None

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_cancel_all():
    registry = RunRegistry()
    tasks = []
    for _ in range(3):
        run_id = uuid.uuid4()
        queue = asyncio.Queue()
        cancelled = asyncio.Event()
        task = _make_task()
        tasks.append(task)
        registry.register(run_id, task, queue, cancelled)

    assert registry.active_count == 3
    await registry.cancel_all()
    assert registry.active_count == 0

    for t in tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass
        assert t.cancelled()


@pytest.mark.asyncio
async def test_active_count_tracks_registrations():
    registry = RunRegistry()

    ids = []
    tasks = []
    for _ in range(3):
        run_id = uuid.uuid4()
        ids.append(run_id)
        task = _make_task()
        tasks.append(task)
        registry.register(run_id, task, asyncio.Queue(), asyncio.Event())

    assert registry.active_count == 3

    registry.remove(ids[0])
    assert registry.active_count == 2

    for t in tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
