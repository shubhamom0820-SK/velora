"""The E2E's local-only expiry (T-7.13, D-930): a Thread's hour run out now,
by its `expires_at` alone, no clock moved. Served behind T-3.13's gate, where
ENV is local and the SMS is the fake's, never in OpenAPI.

What it makes is the expiry the clock makes (D-097, D-560): his send refused
and hers delivered, a re-open at exactly 2, the sweep catching the status up.
Nothing it can't run out (a Knot, a private message, an expired Thread, no
Thread) is changed."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.db import get_session
from app.core.enums import Gender, LedgerReason, ThreadOrigin, ThreadStatus
from app.core.providers import FakeProviders
from app.main import close_resources, create_app
from app.modules.threads import service as threads_service
from app.modules.threads.models import Thread
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.infra import session_for_the_app
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("test_redis")


def _expire(thread_id: uuid.UUID) -> str:
    return f"/v1/test/threads/{thread_id}/expire"


async def _thread(db: AsyncSession, thread_id: uuid.UUID) -> Thread:
    found = await db.scalar(
        select(Thread)
        .where(Thread.id == thread_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _send(client: AsyncClient, token: str, thread_id: uuid.UUID) -> Response:
    return await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "kind": "text", "body": "Hello"},
        headers=bearer(token),
    )


async def _pair(
    make_user: MakeUser, make_thread: MakeThread, *, credits: int = 0
) -> tuple[tuple[uuid.UUID, str], tuple[uuid.UUID, str], uuid.UUID]:
    """(him, her, their Thread from a match), opened by him, its hour running:
    ids and tokens, never rows, which expire once a request's transaction ends."""
    man, his = await make_user(credits=credits)
    woman, hers = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    return (man.id, his), (woman.id, hers), thread.id


async def test_its_hour_ends_at_the_call_and_nothing_else_moves(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    """At the call, never before it: a message sent a moment earlier stays
    inside the hour (the E2E's voice note, 0.85 s before, didn't when the hour
    ended a second early)."""
    _, _, thread_id = await _pair(make_user, make_thread)
    before = clock.now()

    response = await client.post(_expire(thread_id))

    called = clock.now()
    assert response.status_code == 200, response.text
    after = await _thread(db, thread_id)
    assert after.expires_at is not None
    assert before <= after.expires_at <= called
    assert response.json() == {
        "expires_at": after.expires_at.isoformat().replace("+00:00", "Z")
    }
    # The status is the sweep's to catch up, as when an hour passes (D-560).
    assert after.status is ThreadStatus.ACTIVE


async def test_it_is_the_clocks_expiry_his_send_refused_and_hers_delivered(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    """D-097 and 06-TESTING's case 12, by the route's expiry alone: before the
    sweep runs, his send is `THREAD_EXPIRED` and hers goes through, moving
    nothing; then the sweep finds it due."""
    (_, his), (_, hers), thread_id = await _pair(make_user, make_thread)
    assert (await _send(client, his, thread_id)).status_code == 200

    assert (await client.post(_expire(thread_id))).status_code == 200
    ended = (await _thread(db, thread_id)).expires_at
    refused = await _send(client, his, thread_id)
    delivered = await _send(client, hers, thread_id)

    assert error(refused)["code"] == "THREAD_EXPIRED"
    assert delivered.status_code == 200, delivered.text
    assert (await _thread(db, thread_id)).expires_at == ended
    if db.in_transaction():
        await db.commit()
    assert await threads_service.expire_batch(db) == 1
    events.take_committed(db)
    assert (await _thread(db, thread_id)).status is ThreadStatus.EXPIRED


async def test_his_reopen_after_it_charges_exactly_two(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    """J7's re-open (D-098): 2 Velas, read from the ledger, and a fresh hour."""
    (man_id, his), _, thread_id = await _pair(make_user, make_thread, credits=2)
    assert (await client.post(_expire(thread_id))).status_code == 200

    reopened = await client.post(
        f"/v1/threads/{thread_id}/reopen",
        json={"shown_price": 2},
        headers={**bearer(his), "Idempotency-Key": uuid.uuid4().hex},
    )

    assert reopened.status_code == 200, reopened.text
    debits = (
        await db.scalars(
            select(LedgerEntry.delta).where(
                LedgerEntry.user_id == man_id,
                LedgerEntry.reason == LedgerReason.THREAD_REOPEN,
            )
        )
    ).all()
    assert debits == [-2]
    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.user_id == man_id)
        .execution_options(populate_existing=True)
    )
    assert wallet is not None and wallet.balance == 0
    after = await _thread(db, thread_id)
    assert after.expires_at is not None and after.expires_at > clock.now()
    assert (await _send(client, his, thread_id)).status_code == 200


@pytest.mark.parametrize(
    ("status", "origin"),
    [
        (ThreadStatus.KNOTTED, ThreadOrigin.MATCH),
        (ThreadStatus.ACTIVE, ThreadOrigin.DM),
        (ThreadStatus.EXPIRED, ThreadOrigin.MATCH),
    ],
    ids=["knotted", "private-message", "already-expired"],
)
async def test_a_thread_with_no_hour_to_run_out_is_not_found_and_unchanged(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    status: ThreadStatus,
    origin: ThreadOrigin,
) -> None:
    """A Knot is permanent (D-003), a private message never expires (D-550),
    and an expired Thread has already run out: none is given a past hour."""
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status=status, origin=origin)
    thread_id, before = thread.id, (thread.status, thread.expires_at)

    response = await client.post(_expire(thread_id))

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"
    after = await _thread(db, thread_id)
    assert (after.status, after.expires_at) == before


async def test_no_such_thread_is_not_found(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.post(_expire(uuid.uuid4()))

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"


# The route's own refusal of an id it can't run out; a missing route's 404
# carries the framework's message instead (core/errors.py).
OWN_REFUSAL = "No such Thread with an hour."


async def _answer(app: FastAPI) -> Response:
    """The app's answer to an expiry of an id nobody holds."""
    app.dependency_overrides[get_session] = session_for_the_app
    app.state.providers = FakeProviders().as_providers()
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(_expire(uuid.uuid4()))
    finally:
        await close_resources(app)


async def test_is_served_where_the_e2e_runs(db: AsyncSession) -> None:
    """ENV local and the fake SMS, as `tests/e2e_server.py` and CI's E2E run:
    an unknown id is the route's own `NOT_FOUND`, not a missing route's."""
    response = await _answer(create_app(make_test_settings()))

    assert response.status_code == 404
    assert error(response)["message"] == OWN_REFUSAL


@pytest.mark.parametrize(
    "update",
    [
        {"ENV": "staging"},
        {"ENV": "production"},
        {"ENV": "preview"},
        # A name nobody has listed: a blacklist would wave it through (rule 16).
        {"ENV": "env-nobody-has-named-2031"},
        {"SMS_PROVIDER": "msg91"},
    ],
    ids=lambda update: ",".join(f"{k}={v}" for k, v in update.items()),
)
async def test_isnt_served_anywhere_else(
    db: AsyncSession, update: dict[str, str]
) -> None:
    """T-3.13's gate (D-930): local and the fake SMS, nothing else. Anywhere
    else it would let anyone end anyone's hour."""
    settings = make_test_settings().model_copy(update=update)

    response = await _answer(create_app(settings))

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"
    assert error(response)["message"] != OWN_REFUSAL


def test_is_never_in_the_schema() -> None:
    paths = create_app(make_test_settings()).openapi()["paths"]

    assert not [path for path in paths if path.startswith("/v1/test")]
