"""`POST /v1/ws/ticket` (T-7.4): a ticket for one socket, kept in Redis by
its hash for 30 seconds, naming the user; taken once."""

from __future__ import annotations

import hashlib

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from app.modules.realtime import service
from app.modules.realtime.router import TICKETS_PER_MINUTE
from tests.conftest import MakeUser
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("db")


async def test_a_ticket_names_its_user_for_thirty_seconds_by_its_hash(
    client: AsyncClient, make_user: MakeUser, test_redis: Redis
) -> None:
    user, token = await make_user()

    response = await client.post("/v1/ws/ticket", headers=bearer(token))

    assert response.status_code == 200
    assert set(response.json()) == {"ticket"}
    ticket = response.json()["ticket"]
    assert len(ticket) >= 40
    key = service.TICKET_PREFIX + hashlib.sha256(ticket.encode()).hexdigest()
    assert await test_redis.get(key) == str(user.id).encode()
    assert 0 < await test_redis.ttl(key) <= 30
    # Only its hash is kept: the ticket itself is nowhere in Redis.
    assert [k async for k in test_redis.scan_iter(match=f"*{ticket}*")] == []


async def test_a_ticket_opens_once(test_redis: Redis, make_user: MakeUser) -> None:
    user, _ = await make_user()
    ticket = await service.issue(test_redis, user.id)

    first = await service.redeem(test_redis, ticket)
    second = await service.redeem(test_redis, ticket)

    assert (first, second) == (user.id, None)


@pytest.mark.parametrize("ticket", [None, "", "x" * 101, "never-written"])
async def test_no_ticket_names_nobody(test_redis: Redis, ticket: str | None) -> None:
    assert await service.redeem(test_redis, ticket) is None


async def test_onboarding_comes_first(client: AsyncClient, make_user: MakeUser) -> None:
    _, token = await make_user(onboarded=False)

    response = await client.post("/v1/ws/ticket", headers=bearer(token))

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"


async def test_signing_in_comes_first(client: AsyncClient) -> None:
    response = await client.post("/v1/ws/ticket")

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


async def test_tickets_are_rate_limited(
    client: AsyncClient, make_user: MakeUser, test_redis: Redis
) -> None:
    _, token = await make_user()
    for _ in range(TICKETS_PER_MINUTE):
        await client.post("/v1/ws/ticket", headers=bearer(token))

    response = await client.post("/v1/ws/ticket", headers=bearer(token))

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"
