"""A block and a grant at once (T-9.1): never a grant left standing across a
block. The block locks every request between the two whatever its status, and
`decide` asks for a block under the request's lock, so either the block waits
for the grant and revokes it, or the grant waits for the block and sees it.

Rows are committed for real, on two connections. The requester is a woman, so
nothing writes a ledger row (06-TESTING, "Tests that commit rows"), and the
owner is a fresh man with two private photos (`album/test_race.py`'s `pair`).
The request and the blocks are taken back at the end.

Each order is forced and proved (concurrency-tests-must-prove-overlap): the
side that waits is seen blocked on the other's lock by Postgres itself
(`pg_blocking_pids`) before the holder lets go. With the lock taken by status
(`granted` only), the first order leaves a grant standing; with `decide`'s
check gone, the second does.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import AlbumRequestStatus
from app.core.errors import AppError
from app.core.queue import FakeQueue
from app.modules.album import repository as album_repository
from app.modules.album import service as album_service
from app.modules.album.models import AlbumRequest
from app.modules.safety import service as safety_service
from app.modules.safety.models import Block
from app.modules.users.models import User
from tests.conftest import make_test_settings
from tests.modules.album.test_race import pair  # noqa: F401  (the fixture)
from tests.modules.threads.test_clear_race import _blocked, _pid

RACE_TIMEOUT_S = 10.0


@pytest.fixture
async def pending(
    test_engine: AsyncEngine,
    pair: tuple[uuid.UUID, uuid.UUID],  # noqa: F811
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """(her, him, her pending request for his album). Blocks between them are
    taken back after; `pair` takes back the request."""
    woman, man = pair
    async with AsyncSession(test_engine) as session, session.begin():
        row = AlbumRequest(requester_id=woman, owner_id=man)
        session.add(row)
        await session.flush()
        request_id = row.id
    try:
        yield woman, man, request_id
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(
                delete(Block).where(
                    or_(Block.blocker_id == man, Block.blocker_id == woman)
                )
            )


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    *,
    before: Callable[[AsyncSession], Awaitable[None]] | None = None,
    after: Callable[[AsyncSession], Awaitable[None]] | None = None,
) -> None:
    real = getattr(album_repository, name)

    async def patched(session: AsyncSession, *args: Any, **kw: Any) -> Any:
        if before is not None:
            await before(session)
        found = await real(session, *args, **kw)
        if after is not None:
            await after(session)
        return found

    monkeypatch.setattr(album_repository, name, patched)


async def _user(session: AsyncSession, user_id: uuid.UUID) -> User:
    async with session.begin():
        user = await session.get(User, user_id)
    assert user is not None
    return user


async def _grant(engine: AsyncEngine, owner: uuid.UUID, request_id: uuid.UUID) -> Any:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = await _user(session, owner)
        return await album_service.decide(
            session,
            user,
            request_id,
            True,
            queue=FakeQueue(),
            settings=make_test_settings(),
        )


async def _block(engine: AsyncEngine, blocker: uuid.UUID, other: uuid.UUID) -> Any:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = await _user(session, blocker)
        return await safety_service.block(
            session, user, other, queue=FakeQueue(), settings=make_test_settings()
        )


async def _both(*steps: Awaitable[Any]) -> list[Any]:
    tasks = [asyncio.ensure_future(step) for step in steps]
    try:
        async with asyncio.timeout(RACE_TIMEOUT_S):
            return await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _status(engine: AsyncEngine, request_id: uuid.UUID) -> AlbumRequestStatus:
    async with AsyncSession(engine) as session:
        found = await session.scalar(
            select(AlbumRequest.status).where(AlbumRequest.id == request_id)
        )
    assert found is not None
    return found


@pytest.mark.parametrize("who_blocks", ["him", "her"])
async def test_a_block_waiting_on_a_grant_revokes_it(
    test_engine: AsyncEngine,
    pending: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
    who_blocks: str,
) -> None:
    """The grant holds the request; the block waits for it, then finds it
    granted and revokes it."""
    woman, man, request_id = pending
    holding = asyncio.Event()
    block_pid: list[int] = []
    waited: list[bool] = []

    async def hold_until_the_block_waits(session: AsyncSession) -> None:
        holding.set()
        while not block_pid:
            await asyncio.sleep(0.01)
        await _blocked(test_engine, block_pid[0])
        waited.append(True)

    async def note_pid(session: AsyncSession) -> None:
        block_pid.append(await _pid(session))

    _patch(monkeypatch, "request_for_update", after=hold_until_the_block_waits)
    _patch(monkeypatch, "between_for_update", before=note_pid)
    blocker, other = (man, woman) if who_blocks == "him" else (woman, man)

    async def block_once_held() -> Any:
        await holding.wait()
        return await _block(test_engine, blocker, other)

    granted, done = await _both(_grant(test_engine, man, request_id), block_once_held())

    assert waited == [True]
    assert not isinstance(done, BaseException), done
    assert not isinstance(granted, BaseException), granted
    assert granted.status is AlbumRequestStatus.GRANTED
    assert await _status(test_engine, request_id) is AlbumRequestStatus.REVOKED


@pytest.mark.parametrize("who_blocks", ["him", "her"])
async def test_a_grant_waiting_on_a_block_sees_it(
    test_engine: AsyncEngine,
    pending: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
    who_blocks: str,
) -> None:
    """The block holds the requests; the grant waits for it, then finds the
    block and is `NOT_FOUND`: the request still pending, nothing granted."""
    woman, man, request_id = pending
    holding = asyncio.Event()
    grant_pid: list[int] = []
    waited: list[bool] = []

    async def hold_until_the_grant_waits(session: AsyncSession) -> None:
        holding.set()
        while not grant_pid:
            await asyncio.sleep(0.01)
        await _blocked(test_engine, grant_pid[0])
        waited.append(True)

    async def note_pid(session: AsyncSession) -> None:
        grant_pid.append(await _pid(session))

    _patch(monkeypatch, "between_for_update", after=hold_until_the_grant_waits)
    _patch(monkeypatch, "request_for_update", before=note_pid)
    blocker, other = (man, woman) if who_blocks == "him" else (woman, man)

    async def grant_once_held() -> Any:
        await holding.wait()
        return await _grant(test_engine, man, request_id)

    done, granted = await _both(_block(test_engine, blocker, other), grant_once_held())

    assert waited == [True]
    assert not isinstance(done, BaseException), done
    assert isinstance(granted, AppError) and granted.code == "NOT_FOUND", granted
    assert await _status(test_engine, request_id) is AlbumRequestStatus.PENDING
