"""A block revokes every album grant between the two (T-9.1), either way: his
copies are deleted by `watermark_album`, as her own revoke's are (D-730), and
nobody is told. A grant can't be made across a block: `decide` is `NOT_FOUND`.
A pending request is left as it was, hidden with everything else, so
unblocking brings it back still waiting on her."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AlbumRequestStatus, Gender
from app.core.providers import FakeProviders
from app.core.queue import WATERMARK_ALBUM, FakeQueue
from app.modules.album.models import AlbumRequest
from app.modules.album.rules import revoke_job_id
from tests.conftest import MakeUser
from tests.modules.album.support import album_of, asked, copies_of, decide
from tests.modules.album.test_album import _granted, _sync
from tests.modules.discovery.support import bearer, error
from tests.modules.safety.support import blocked, report, unblocked

pytestmark = pytest.mark.usefixtures("test_redis")


async def _request(db: AsyncSession, request_id: str | uuid.UUID) -> AlbumRequest:
    found = await db.scalar(
        select(AlbumRequest)
        .where(AlbumRequest.id == uuid.UUID(str(request_id)))
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


@pytest.mark.parametrize("who_blocks", ["her", "him"])
async def test_a_block_revokes_the_grant_and_its_copies_go(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
    who_blocks: str,
) -> None:
    storage = fake_providers.storage
    man, token, woman, woman_token, request_id = await _granted(
        db, client, make_user, storage
    )
    man_id, woman_id = man.id, woman.id
    await _sync(db, storage, request_id)
    assert len(await copies_of(db, uuid.UUID(request_id))) == 2
    fake_queue.jobs.clear()

    if who_blocks == "her":
        await blocked(client, woman_token, man_id)
    else:
        await blocked(client, token, woman_id)

    row = await _request(db, request_id)
    assert row.status is AlbumRequestStatus.REVOKED
    assert row.decided_at is not None
    [job] = fake_queue.named(WATERMARK_ALBUM)
    assert (job.job_id, job.kwargs) == (
        revoke_job_id(uuid.UUID(request_id)),
        {"request_id": request_id},
    )
    assert await _sync(db, storage, request_id) == "deleted 2"
    assert await copies_of(db, uuid.UUID(request_id)) == []


async def test_grants_both_ways_are_revoked_by_one_block(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Each may have granted the other: one block revokes both."""
    man, token = await make_user(credits=3)
    woman, woman_token = await make_user(Gender.FEMALE)
    await album_of(db, woman)
    await album_of(db, man)
    man_id, woman_id = man.id, woman.id
    his = await asked(client, token, woman_id)
    hers = await asked(client, woman_token, man_id, shown=0)
    assert (await decide(client, woman_token, his["id"], True)).status_code == 200
    assert (await decide(client, token, hers["id"], True)).status_code == 200

    await blocked(client, woman_token, man_id)

    for request_id in (his["id"], hers["id"]):
        assert (await _request(db, request_id)).status is AlbumRequestStatus.REVOKED


async def test_a_report_with_also_block_revokes_too(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    man, _, _, woman_token, request_id = await _granted(
        db, client, make_user, fake_providers.storage
    )
    await _sync(db, fake_providers.storage, request_id)
    fake_queue.jobs.clear()

    response = await report(client, woman_token, man.id, also_block=True)

    assert response.status_code == 201, response.text
    assert (await _request(db, request_id)).status is AlbumRequestStatus.REVOKED
    assert len(fake_queue.named(WATERMARK_ALBUM)) == 1


async def test_blocking_again_queues_the_copies_deletion_again(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    """Asked again after an enqueue that never landed, the block finds the
    revoked request still holding copies and queues their deletion again."""
    man, _, _, woman_token, request_id = await _granted(
        db, client, make_user, fake_providers.storage
    )
    man_id = man.id
    await _sync(db, fake_providers.storage, request_id)
    await blocked(client, woman_token, man_id)
    fake_queue.jobs.clear()

    await blocked(client, woman_token, man_id)

    assert len(fake_queue.named(WATERMARK_ALBUM)) == 1


@pytest.mark.parametrize("who_blocks", ["her", "him"])
async def test_she_cant_grant_across_a_block_and_a_pending_one_waits_it_out(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list,  # type: ignore[type-arg]
    who_blocks: str,
) -> None:
    man, token = await make_user(credits=3)
    woman, woman_token = await make_user(Gender.FEMALE)
    await album_of(db, woman)
    man_id, woman_id = man.id, woman.id
    pending = await asked(client, token, woman_id)
    published.clear()
    if who_blocks == "her":
        await blocked(client, woman_token, man_id)
    else:
        await blocked(client, token, woman_id)

    for grant in (True, False):
        response = await decide(client, woman_token, pending["id"], grant)
        assert response.status_code == 404, response.text
        assert error(response)["code"] == "NOT_FOUND"
    incoming = await client.get(
        "/v1/album-requests/incoming", headers=bearer(woman_token)
    )
    assert incoming.json()["items"] == []
    assert (await _request(db, pending["id"])).status is AlbumRequestStatus.PENDING
    assert published == []

    blocker = woman_token if who_blocks == "her" else token
    await unblocked(client, blocker, woman_id if who_blocks == "him" else man_id)

    incoming = await client.get(
        "/v1/album-requests/incoming", headers=bearer(woman_token)
    )
    assert [item["id"] for item in incoming.json()["items"]] == [pending["id"]]
    assert (await decide(client, woman_token, pending["id"], True)).status_code == 200


async def test_unblocking_never_brings_a_grant_back(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """A revoked grant stays revoked, its cooldown running (D-731)."""
    man, token, woman, woman_token, request_id = await _granted(
        db, client, make_user, fake_providers.storage
    )
    man_id, woman_id = man.id, woman.id
    await blocked(client, woman_token, man_id)
    await unblocked(client, woman_token, man_id)

    assert (await _request(db, request_id)).status is AlbumRequestStatus.REVOKED
    album = await client.get(f"/v1/users/{woman_id}/album", headers=bearer(token))
    assert album.json() == {"status": "revoked", "photos": []}
