"""Her side of the album (T-8.4): the requests waiting on her, her answer, and
taking a grant back. A decline returns nothing (D-230); a grant queues the
copies, a revoke their deletion, each under a job id of its own."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender
from app.core.queue import WATERMARK_ALBUM, FakeQueue
from app.modules.album.router import ANSWERS_PER_MINUTE
from tests.conftest import MakeUser
from tests.modules.album.support import (
    album_of,
    asked,
    decide,
    requests_between,
    revoke,
)
from tests.modules.discovery.support import bearer, block, error
from tests.modules.gifts.support import balance, ledger, token_for

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 9, 6, 30, tzinfo=UTC)
HOUR = timedelta(hours=1)


def _refused(response: Response, code: str, status: int) -> dict[str, Any]:
    assert response.status_code == status, response.text
    found = error(response)
    assert found["code"] == code
    return found


async def _pair(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> tuple[uuid.UUID, str, uuid.UUID, str, str]:
    """A man who asked to see a woman's album: (his id, his token, her id, her
    token, the request's id)."""
    man, token = await make_user(credits=3)
    woman, woman_token = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)
    request = await asked(client, token, woman_id)
    return man_id, token, woman_id, woman_token, request["id"]


def _decided(published: list[events.Event]) -> list[events.Event]:
    return [e for e in published if e.type == "album.decided"]


def _jobs(queue: FakeQueue) -> list[tuple[str | None, dict[str, Any]]]:
    return [(job.job_id, job.kwargs) for job in queue.named(WATERMARK_ALBUM)]


# --- Her answer -------------------------------------------------------------------------


async def test_a_grant_tells_him_and_queues_his_copies(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    fake_queue: FakeQueue,
    published: list[events.Event],
) -> None:
    clock.freeze(NOON)
    man_id, _, woman_id, _, request_id = await _pair(db, client, make_user)
    clock.freeze(NOON + HOUR)

    response = await decide(client, token_for(woman_id), request_id, True)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["status"], body["owner_id"]) == (
        request_id,
        "granted",
        str(woman_id),
    )
    assert body["requester"]["id"] == str(man_id)
    assert datetime.fromisoformat(body["decided_at"]) == NOON + HOUR
    [row] = await requests_between(db, man_id, woman_id)
    assert (row.status, row.decided_at) == ("granted", NOON + HOUR)
    assert [(e.user_id, e.type, e.data) for e in _decided(published)] == [
        (
            man_id,
            "album.decided",
            {"album_request_id": request_id, "user_id": str(woman_id), "granted": True},
        )
    ]
    assert _jobs(fake_queue) == [
        (f"watermark_album:{request_id}", {"request_id": request_id})
    ]


@pytest.mark.critical
async def test_a_decline_returns_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_queue: FakeQueue,
    published: list[events.Event],
) -> None:
    """D-230: the Vela he paid stays spent. `refund_album_declined` is never
    written, nor any credit."""
    man_id, _, woman_id, woman_token, request_id = await _pair(db, client, make_user)

    response = await decide(client, woman_token, request_id, False)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "declined"
    [row] = await requests_between(db, man_id, woman_id)
    assert (row.status, row.credits_charged) == ("declined", 1)
    assert await ledger(db, man_id) == [("album_request", -1, row.id)]
    assert await balance(db, man_id) == 2
    assert _jobs(fake_queue) == []
    assert [(e.type, e.data["granted"]) for e in _decided(published)] == [
        ("album.decided", False)
    ]


@pytest.mark.parametrize("grant", [True, False])
async def test_the_same_answer_again_changes_nothing_and_the_other_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_queue: FakeQueue,
    published: list[events.Event],
    grant: bool,
) -> None:
    man_id, _, woman_id, woman_token, request_id = await _pair(db, client, make_user)
    first = (await decide(client, woman_token, request_id, grant)).json()

    again = await decide(client, woman_token, request_id, grant)

    assert again.status_code == 200 and again.json() == first
    found = _refused(
        await decide(client, woman_token, request_id, not grant), "NOT_ALLOWED", 422
    )
    assert found["details"] == {"why": "already_decided"}
    [row] = await requests_between(db, man_id, woman_id)
    assert row.status == ("granted" if grant else "declined")
    assert len(_decided(published)) == 1
    assert len(_jobs(fake_queue)) == (1 if grant else 0)


async def test_only_she_answers_and_anyone_else_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man_id, token, woman_id, _, request_id = await _pair(db, client, make_user)
    _stranger, stranger_token = await make_user(Gender.FEMALE)
    expected = error(await decide(client, token, str(uuid.uuid4()), True))

    assert error(await decide(client, token, request_id, True)) == expected
    assert error(await decide(client, stranger_token, request_id, True)) == expected
    assert error(await revoke(client, token, request_id)) == expected
    assert error(await revoke(client, stranger_token, request_id)) == expected
    assert expected["code"] == "NOT_FOUND"
    [row] = await requests_between(db, man_id, woman_id)
    assert row.status == "pending"


async def test_a_malformed_answer_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, _, _, woman_token, request_id = await _pair(db, client, make_user)
    for body in ({}, {"grant": "maybe"}, {"grant": True, "refund": True}):
        response = await client.post(
            f"/v1/album-requests/{request_id}/decide",
            json=body,
            headers=bearer(woman_token),
        )
        _refused(response, "VALIDATION_ERROR", 400)
    response = await client.post(
        "/v1/album-requests/not-an-id/decide",
        json={"grant": True},
        headers=bearer(woman_token),
    )
    _refused(response, "VALIDATION_ERROR", 400)


async def test_answers_are_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, _, _, woman_token, request_id = await _pair(db, client, make_user)
    for _ in range(ANSWERS_PER_MINUTE):
        assert (await decide(client, woman_token, request_id, True)).status_code == 200

    _refused(await decide(client, woman_token, request_id, True), "RATE_LIMITED", 429)


# --- Taking it back -------------------------------------------------------------------------


async def test_a_revoke_closes_it_and_queues_its_copies_deletion(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    fake_queue: FakeQueue,
) -> None:
    """Under a job id of its own: ARQ refuses an id it finished within the
    hour, so sharing the grant's would drop the deletion."""
    clock.freeze(NOON)
    man_id, _, woman_id, woman_token, request_id = await _pair(db, client, make_user)
    await decide(client, woman_token, request_id, True)
    clock.freeze(NOON + HOUR)

    response = await revoke(client, token_for(woman_id), request_id)

    assert response.status_code == 204 and response.content == b""
    [row] = await requests_between(db, man_id, woman_id)
    assert (row.status, row.decided_at) == ("revoked", NOON + HOUR)
    assert _jobs(fake_queue) == [
        (f"watermark_album:{request_id}", {"request_id": request_id}),
        (f"watermark_album:{request_id}:revoked", {"request_id": request_id}),
    ]
    assert await ledger(db, man_id) == [("album_request", -1, row.id)]

    again = await revoke(client, token_for(woman_id), request_id)

    assert again.status_code == 204
    assert len(_jobs(fake_queue)) == 2


@pytest.mark.parametrize("grant", [None, False])
async def test_only_a_grant_can_be_revoked(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, grant: bool | None
) -> None:
    man_id, _, woman_id, woman_token, request_id = await _pair(db, client, make_user)
    if grant is not None:
        await decide(client, woman_token, request_id, grant)

    found = _refused(await revoke(client, woman_token, request_id), "NOT_ALLOWED", 422)

    assert found["details"] == {"why": "not_granted"}
    [row] = await requests_between(db, man_id, woman_id)
    assert row.status == ("pending" if grant is None else "declined")


# --- The requests waiting on her ---------------------------------------------------------


async def _incoming(client: AsyncClient, token: str, **params: Any) -> Any:
    response = await client.get(
        "/v1/album-requests/incoming", params=params, headers=bearer(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_her_list_is_her_pending_and_granted_newest_first(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """Never what he paid, nor anyone across a block, nor another's requests;
    a decline or revoke leaves it."""
    clock.freeze(NOON)
    woman, _woman_token = await make_user(Gender.FEMALE)
    other_woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id
    await album_of(db, woman)
    await album_of(db, other_woman)
    men = []
    for n in range(5):
        clock.freeze(NOON + n * HOUR)
        man, token = await make_user(credits=3)
        men.append(man)
        men_request = await asked(client, token, woman_id)
        man.request_id = men_request["id"]  # type: ignore[attr-defined]
    await asked(client, token_for(men[0].id), other_woman.id)
    clock.freeze(NOON + 6 * HOUR)
    her = token_for(woman_id)
    ids = [m.request_id for m in men]  # type: ignore[attr-defined]
    await decide(client, her, ids[1], True)
    await decide(client, her, ids[2], False)
    await decide(client, her, ids[3], True)
    await revoke(client, her, ids[3])
    await block(db, woman, men[4])

    page = await _incoming(client, her)

    assert [item["id"] for item in page["items"]] == [ids[1], ids[0]]
    assert [item["status"] for item in page["items"]] == ["granted", "pending"]
    assert page["next_cursor"] is None
    first = page["items"][1]
    assert first["requester"]["id"] == str(men[0].id)
    assert set(first) == {
        "id",
        "requester",
        "owner_id",
        "status",
        "created_at",
        "decided_at",
    }
    assert set(first["requester"]) == {
        "id",
        "first_name",
        "username",
        "main_photo_url",
        "shows_badge",
        "is_online",
        "deleted",
    }


async def test_her_list_pages(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    woman, _woman_token = await make_user(Gender.FEMALE)
    woman_id = woman.id
    await album_of(db, woman)
    ids = []
    for n in range(3):
        clock.freeze(NOON + n * HOUR)
        _, token = await make_user(credits=3)
        ids.append((await asked(client, token, woman_id))["id"])
    her = token_for(woman_id)

    one = await _incoming(client, her, limit=2)
    two = await _incoming(client, her, limit=2, cursor=one["next_cursor"])

    assert [i["id"] for i in one["items"]] == [ids[2], ids[1]]
    assert [i["id"] for i in two["items"]] == [ids[0]]
    assert two["next_cursor"] is None
    response = await client.get(
        "/v1/album-requests/incoming", params={"limit": 51}, headers=bearer(her)
    )
    _refused(response, "VALIDATION_ERROR", 400)
