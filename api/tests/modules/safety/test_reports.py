"""`POST /v1/reports` (T-9.1, D-863): a report goes to moderation, ten a day
per person; `also_block` blocks in the same transaction; anyone with an
account may be reported, a block standing either way or not; `thread_id` is
the pair's own Thread or `NOT_FOUND`; every refusal comes before anything is
written; the reported person is never told. A report's evidence is the whole
Thread, whatever the reporter cleared (D-006, D-610)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, MessageKind, ReportReason, ReportStatus
from app.modules.messages.models import Message
from app.modules.notifications.models import Notification
from app.modules.safety import service as safety_service
from app.modules.safety.models import Report
from app.modules.safety.router import REPORTS_PER_DAY
from app.modules.safety.schemas import DETAILS_MAX
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, error
from tests.modules.safety.support import blocked, report, rows

pytestmark = pytest.mark.usefixtures("test_redis")


async def _reports(db: AsyncSession, reporter: uuid.UUID) -> list[Report]:
    found = await db.scalars(
        select(Report).where(Report.reporter_id == reporter).order_by(Report.created_at)
    )
    return list(found)


async def test_a_report_is_filed_for_moderation(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    thread = await make_thread(him, me, messages=1)
    me_id, him_id, thread_id = me.id, him.id, thread.id

    response = await report(
        client,
        token,
        him_id,
        reason="scam",
        details="Asked me to pay him on UPI.",
        thread_id=str(thread_id),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"id", "created_at"}
    [row] = await _reports(db, me_id)
    assert str(row.id) == body["id"]
    assert (row.reported_id, row.reason, row.thread_id, row.status) == (
        him_id,
        ReportReason.SCAM,
        thread_id,
        ReportStatus.OPEN,
    )
    assert row.details == "Asked me to pay him on UPI."
    assert await rows(db, me_id) == []


async def test_also_block_blocks_in_the_same_request(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    me_id, him_id = me.id, him.id

    response = await report(client, token, him_id, also_block=True)

    assert response.status_code == 201, response.text
    [block] = await rows(db, me_id)
    assert (block.blocked_id, block.unblocked_at) == (him_id, None)
    assert len(await _reports(db, me_id)) == 1
    profile = await client.get(f"/v1/users/{him_id}", headers=bearer(token))
    assert profile.status_code == 404


async def test_anyone_may_be_reported_across_a_block_either_way(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The answer never says whether a block stands: blocked by them, or
    blocking them, the report is filed as any other is."""
    me, token = await make_user(Gender.FEMALE)
    blocker, blocker_token = await make_user()
    mine, _ = await make_user()
    me_id = me.id
    await blocked(client, blocker_token, me_id)
    await blocked(client, token, mine.id)

    for other in (blocker.id, mine.id):
        response = await report(client, token, other)
        assert response.status_code == 201, response.text
    assert len(await _reports(db, me_id)) == 2


async def test_reporting_the_same_person_again_is_a_new_report(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-863: harassed again, she reports again; the day's ten bound it."""
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    me_id, him_id = me.id, him.id

    for _ in range(2):
        assert (await report(client, token, him_id)).status_code == 201

    assert len(await _reports(db, me_id)) == 2


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"details": "x" * (DETAILS_MAX + 1)}, "details"),
        ({"details": ""}, "details"),
        ({"reason": "rude"}, "reason"),
        ({"also_block": None}, "also_block"),
        ({"also_block": "yes"}, "also_block"),
        ({"extra": 1}, "extra"),
    ],
)
async def test_a_malformed_report_is_refused_and_nothing_is_written(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    body: dict[str, object],
    field: str,
) -> None:
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    me_id = me.id

    response = await report(client, token, him.id, **body)

    assert response.status_code == 400, response.text
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert [f["field"] for f in error(response)["details"]["fields"]] == [field]
    assert await _reports(db, me_id) == []


async def test_also_block_must_be_said(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()

    response = await client.post(
        "/v1/reports",
        json={"reported_id": str(him.id), "reason": "fake"},
        headers=bearer(token),
    )

    assert response.status_code == 400
    assert error(response)["details"]["fields"] == [
        {"field": "also_block", "problem": "Field required"}
    ]


async def test_500_characters_of_details_is_enough(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    me_id = me.id

    response = await report(client, token, him.id, details="é" * DETAILS_MAX)

    assert response.status_code == 201, response.text
    [row] = await _reports(db, me_id)
    assert row.details == "é" * 500


async def test_nobody_is_not_found_and_yourself_is_not_allowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(Gender.FEMALE)
    me_id = me.id

    nobody = await report(client, token, uuid.uuid4(), also_block=True)
    assert nobody.status_code == 404
    assert error(nobody)["code"] == "NOT_FOUND"
    yourself = await report(client, token, me_id, also_block=True)
    assert yourself.status_code == 422
    assert error(yourself)["code"] == "NOT_ALLOWED"
    assert error(yourself)["details"] == {"why": "yourself"}
    assert await _reports(db, me_id) == []
    assert await rows(db, me_id) == []


async def test_a_thread_that_isnt_theirs_is_not_found_and_blocks_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    other, _ = await make_user(Gender.FEMALE)
    theirs = await make_thread(him, other)
    me_id, him_id = me.id, him.id

    for thread_id in (theirs.id, uuid.uuid4()):
        response = await report(
            client, token, him_id, thread_id=str(thread_id), also_block=True
        )
        assert response.status_code == 404, response.text
        assert error(response)["code"] == "NOT_FOUND"
    assert await _reports(db, me_id) == []
    assert await rows(db, me_id) == []


async def test_their_thread_counts_across_a_block(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """She blocked him yesterday and reports today: the Thread is hidden from
    both, and still theirs to name."""
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    thread = await make_thread(him, me, messages=1)
    me_id, him_id, thread_id = me.id, him.id, thread.id
    await blocked(client, token, him_id)

    response = await report(client, token, him_id, thread_id=str(thread_id))

    assert response.status_code == 201, response.text
    [row] = await _reports(db, me_id)
    assert row.thread_id == thread_id


async def test_ten_a_day_then_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(Gender.FEMALE)
    me_id = me.id
    people = [(await make_user())[0].id for _ in range(REPORTS_PER_DAY + 1)]
    assert REPORTS_PER_DAY == 10

    for other in people[:REPORTS_PER_DAY]:
        assert (await report(client, token, other)).status_code == 201
    response = await report(client, token, people[-1], also_block=True)

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"
    assert error(response)["details"]["retry_after_s"] > 23 * 3600
    assert len(await _reports(db, me_id)) == REPORTS_PER_DAY
    assert await rows(db, me_id) == []


async def test_reporting_needs_onboarding_done(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await report(client, token, uuid.uuid4())

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"


@pytest.mark.critical
async def test_the_reported_person_is_never_told(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    """Nothing is published to anyone and no notification is written, with
    `also_block` or without; their Thread, as they see it, is unchanged."""
    me, token = await make_user(Gender.FEMALE)
    him, his_token = await make_user()
    other, _ = await make_user()
    thread = await make_thread(him, me, messages=1)
    thread_id = thread.id
    everyone = (me.id, him.id, other.id)
    before = await client.get(f"/v1/threads/{thread_id}", headers=bearer(his_token))

    assert (
        await report(client, token, him.id, thread_id=str(thread_id))
    ).status_code == 201
    assert (await report(client, token, other.id, also_block=True)).status_code == 201

    assert published == []
    written = select(func.count()).where(Notification.user_id.in_(everyone))
    assert await db.scalar(written) == 0
    after = await client.get(f"/v1/threads/{thread_id}", headers=bearer(his_token))
    # Her requests move her `last_active_at` (once a minute), so "online" is
    # her being here, never the report: everything else is unchanged.
    seen = [r.json() for r in (before, after)]
    for thread in seen:
        thread["other"].pop("is_online")
    assert seen[0] == seen[1]


# --- The evidence ---------------------------------------------------------------------


@pytest.mark.critical
async def test_the_evidence_is_every_message_whatever_the_reporter_cleared(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """She clears the chat, then reports him with a block: her own view of the
    Thread is empty and hidden, and the report's evidence is still every
    message, his words as he wrote them (`body_raw`) included."""
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    thread = await make_thread(him, me, messages=3)
    db.add(
        Message(
            thread_id=thread.id,
            sender_id=him.id,
            kind=MessageKind.TEXT,
            body="Call me on ••••••••••",
            body_raw="Call me on 9876543210",
            masked=True,
            client_msg_id=uuid.uuid4(),
        )
    )
    await db.flush()
    thread_id, him_id = thread.id, him.id
    every = {
        m.id
        for m in await db.scalars(select(Message).where(Message.thread_id == thread_id))
    }
    assert len(every) == 4
    cleared = await client.post(f"/v1/threads/{thread_id}/clear", headers=bearer(token))
    assert cleared.status_code == 204
    mine = await client.get(f"/v1/threads/{thread_id}/messages", headers=bearer(token))
    assert mine.json()["items"] == []

    response = await report(
        client, token, him_id, thread_id=str(thread_id), also_block=True
    )
    assert response.status_code == 201, response.text

    evidence = await safety_service.report_evidence(
        db, uuid.UUID(response.json()["id"])
    )
    assert {m.id for m in evidence} == every
    assert "Call me on 9876543210" in [m.body_raw for m in evidence]


async def test_a_report_with_no_thread_has_no_evidence(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    response = await report(client, token, him.id)

    assert (
        await safety_service.report_evidence(db, uuid.UUID(response.json()["id"])) == []
    )
