"""A copy of one's own data (T-9.6, D-502): asked for through the API, written
by the worker, linked for 24 hours, then deleted. Nothing in it is anyone
else's, and nothing of it reaches the logs (rule 15)."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.enums import Gender
from app.core.providers.storage import FakeStorage
from app.core.queue import EXPIRE_EXPORT, EXPORT_DATA, FakeQueue
from app.core.security import decrypt_phone, make_access_token
from app.modules.account import service as account_service
from app.modules.account.models import DataExport
from app.modules.users.models import User
from app.workers.tasks import export_data as export_job
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.account.test_erasure import NOW
from tests.modules.onboarding.test_guard import _alembic
from tests.modules.photos.test_moderate import Sessions

SETTINGS = make_test_settings()
PRIVATE = SETTINGS.R2_BUCKET_PRIVATE
DAY_S = 86_400


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _ask(client: AsyncClient, token: str) -> Response:
    return await client.post("/v1/me/export", headers=_auth(token))


async def _write(
    db: AsyncSession, storage: FakeStorage, queue: FakeQueue, export_id: str
) -> str:
    return await account_service.write_export(
        Sessions(db),  # type: ignore[arg-type]
        export_id=uuid.UUID(export_id),
        storage=storage,
        settings=SETTINGS,
        queue=queue,
    )


async def _expire(db: AsyncSession, storage: FakeStorage, export_id: str) -> str:
    return await account_service.expire_export(
        Sessions(db),  # type: ignore[arg-type]
        export_id=uuid.UUID(export_id),
        storage=storage,
        settings=SETTINGS,
    )


def _document(storage: FakeStorage) -> tuple[str, dict[str, Any]]:
    [(bucket, key)] = list(storage.objects)
    assert bucket == PRIVATE
    raw = storage.objects[(bucket, key)].data.decode()
    document: dict[str, Any] = json.loads(raw)
    return raw, document


# --- Asking (the API) ---------------------------------------------------------------


async def test_nothing_asked_for_yet_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()

    response = await client.get("/v1/me/export", headers=_auth(token))

    assert response.status_code == 404
    assert _error(response) == {
        "code": "NOT_FOUND",
        "message": "You haven't asked for a copy of your data.",
    }


async def test_asking_queues_one_export_and_asking_again_returns_it(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_queue: FakeQueue,
    test_redis: Redis,
) -> None:
    _, token = await make_user()

    first = await _ask(client, token)
    second = await _ask(client, token)

    assert first.status_code == second.status_code == 202
    body = first.json()
    assert body["status"] == "pending"
    assert (body["url"], body["expires_at"]) == (None, None)
    assert second.json()["id"] == body["id"]
    [queued] = fake_queue.named(EXPORT_DATA)
    assert queued.job_id == f"{EXPORT_DATA}:{body['id']}"
    assert queued.kwargs == {"export_id": body["id"]}
    seen = await client.get("/v1/me/export", headers=_auth(token))
    assert seen.json() == body


async def test_a_stuck_export_is_replaced_after_an_hour(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_queue: FakeQueue,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(NOW)
    _, token = await make_user()
    first = (await _ask(client, token)).json()
    await db.execute(
        text("update data_exports set created_at = :at where id = :id"),
        {"at": NOW - timedelta(hours=1), "id": first["id"]},
    )

    second = (await _ask(client, token)).json()

    assert second["id"] != first["id"]
    assert len(fake_queue.named(EXPORT_DATA)) == 2


async def test_five_asks_a_day_then_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, test_redis: Redis
) -> None:
    _, token = await make_user()
    for _ in range(5):
        assert (await _ask(client, token)).status_code == 202

    response = await _ask(client, token)

    assert response.status_code == 429
    assert _error(response)["code"] == "RATE_LIMITED"
    assert 0 < _error(response)["details"]["retry_after_s"] <= DAY_S


# --- Writing it (the worker) -----------------------------------------------------------

MARKERS = {
    "first_name": "Zorawar",
    "username": "zz.marker",
    "about": "An about that is the other person's alone, never in an export.",
    "hometown": "Markertown",
    "city": "Markercity",
}
THEIR_WORDS = "words the other person wrote, theirs alone"
MY_WORDS = "words I wrote myself"
# On the 0.01° grid positions are stored on (D-490).
THEIR_POINT = (31.23, 75.78)  # lat, lng: theirs
MY_POINT = (31.22, 75.77)


async def _a_conversation(db: AsyncSession, me: User, other: User) -> None:
    for column, value in MARKERS.items():
        await db.execute(
            text(f"update profiles set {column} = :v where user_id = :u"),
            {"v": value, "u": other.id},
        )
    for user, (lat, lng) in ((other, THEIR_POINT), (me, MY_POINT)):
        await db.execute(
            text(
                "update profiles set location = "
                "st_snaptogrid(st_setsrid(st_makepoint(:lng, :lat), 4326), 0.01)::geography, "
                "location_updated_at = now() where user_id = :u"
            ),
            {"lat": lat, "lng": lng, "u": user.id},
        )
    low, high = sorted((me.id, other.id))
    thread = await db.scalar(
        text(
            "insert into threads (user_low, user_high, origin, opened_by, expires_at) "
            "values (:low, :high, 'match', :o, now() + interval '1 day') returning id"
        ),
        {"low": low, "high": high, "o": other.id},
    )
    for sender, words in ((other.id, THEIR_WORDS), (me.id, MY_WORDS)):
        await db.execute(
            text(
                "insert into messages (thread_id, sender_id, kind, body, body_raw, "
                "client_msg_id) values (:t, :s, 'text', :w, :w, gen_random_uuid())"
            ),
            {"t": thread, "s": sender, "w": words},
        )
    for a, b in ((me.id, other.id), (other.id, me.id)):
        for statement in (
            "insert into swipes (swiper_id, target_id, dir) values (:a, :b, 'like')",
            "insert into blocks (blocker_id, blocked_id) values (:a, :b)",
            (
                "insert into kudos (from_id, to_id, kind, thread_id) "
                "values (:a, :b, 'genuinely_funny', :t)"
            ),
            (
                "insert into reports (reporter_id, reported_id, reason, details) "
                "values (:a, :b, 'other', :details)"
            ),
        ):
            await db.execute(
                text(statement),
                {"a": a, "b": b, "t": thread, "details": f"a report, written by {a}"},
            )
    await db.flush()


@pytest.mark.critical
async def test_the_export_is_all_mine_and_nothing_of_theirs(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_queue: FakeQueue,
    test_redis: Redis,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    clock.freeze(NOW)
    me, token = await make_user(credits=6)
    other, _ = await make_user(Gender.FEMALE)
    await _a_conversation(db, me, other)
    assert me.phone_enc is not None and other.phone_enc is not None
    my_phone = decrypt_phone(me.phone_enc, SETTINGS)
    their_phone = decrypt_phone(other.phone_enc, SETTINGS)
    export_id = (await _ask(client, token)).json()["id"]
    storage, queue = FakeStorage(), FakeQueue()

    assert await _write(db, storage, queue, export_id) == "ready"

    raw, document = _document(storage)
    # Theirs: nowhere, in any form.
    for theirs in [
        *MARKERS.values(),
        THEIR_WORDS,
        their_phone,
        their_phone.removeprefix("+91"),
        other.phone_hash,
        str(other.id),
        str(THEIR_POINT[0]),
        str(THEIR_POINT[1]),
        str(other.id).split("-")[0],
    ]:
        assert theirs not in raw, theirs
    # Not moderation's: who reported me, or that anyone did.
    assert [r["details"] for r in document["reports_filed"]] == [
        f"a report, written by {me.id}"
    ]
    # Mine: there.
    assert document["account"]["phone"] == my_phone
    assert document["account"]["id"] == str(me.id)
    assert document["profile"]["first_name"] == "Test"
    assert document["profile"]["location"]["latitude"] == pytest.approx(MY_POINT[0])
    assert [m["body"] for m in document["messages_sent"]] == [MY_WORDS]
    assert document["messages_sent"][0]["thread"] == 1
    assert document["threads"][0]["opened_by_you"] is False
    assert document["balance"] == 6
    assert [e["delta"] for e in document["ledger"]] == [6]
    assert set(document["ledger"][0]) == {
        "reason",
        "delta",
        "balance_after",
        "created_at",
    }
    assert len(document["swipes"]) == len(document["blocks"]) == 1
    # When, made and lifted (D-860), never whom.
    assert set(document["blocks"][0]) == {"created_at", "unblocked_at"}
    assert [k["kind"] for k in document["kudos_received"]] == ["genuinely_funny"]
    # Logs: by id only (rule 15).
    for secret in (my_phone, "exports/", "fake-storage://", MY_WORDS):
        assert secret not in captured_logs.text
    assert export_id in captured_logs.text
    captured_logs.assert_listening()


async def test_ready_for_24_hours_then_expired_and_its_file_deleted(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(NOW)
    user, token = await make_user()
    export_id = (await _ask(client, token)).json()["id"]
    storage, queue = FakeStorage(), FakeQueue()
    await _write(db, storage, queue, export_id)
    [expiry] = queue.named(EXPIRE_EXPORT)
    assert expiry.defer_by == timedelta(hours=24)
    assert expiry.kwargs == {"export_id": export_id}
    [(_, key)] = list(storage.objects)
    assert key.startswith("exports/") and export_id in key

    async def seen() -> dict[str, Any]:
        # A token signed now: an access token lasts 15 minutes (D-024).
        fresh = make_access_token(user.id, user.role, SETTINGS, auth_time=clock.now())
        response = await client.get("/v1/me/export", headers=_auth(fresh))
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        return body

    ready = await seen()
    assert ready["status"] == "ready"
    assert ready["url"] == f"fake-storage://{PRIVATE}/{key}?method=GET&ttl={DAY_S}"
    clock.freeze(NOW + timedelta(hours=23))
    later = await seen()
    assert later["url"].endswith("ttl=3600"), "the link never outlives the file"
    assert await _expire(db, storage, export_id) == "not yet"
    assert storage.objects

    clock.freeze(NOW + timedelta(hours=24))
    before_the_job = await seen()
    assert (before_the_job["status"], before_the_job["url"]) == ("expired", None)
    assert await _expire(db, storage, export_id) == "expired"
    assert storage.objects == {}
    row = await db.get(DataExport, uuid.UUID(export_id))
    assert row is not None
    await db.refresh(row)
    assert (row.status, row.file_key) == ("expired", None)
    # Expired, a new one can be asked for.
    fresh = make_access_token(user.id, user.role, SETTINGS, auth_time=clock.now())
    again = await _ask(client, fresh)
    assert again.json()["id"] != export_id


async def test_the_daily_job_expires_what_its_own_job_left(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(NOW)
    _, token = await make_user()
    export_id = (await _ask(client, token)).json()["id"]
    storage = FakeStorage()
    await _write(db, storage, FakeQueue(), export_id)
    clock.freeze(NOW + timedelta(hours=25))

    expired = await account_service.expire_due_exports(
        Sessions(db),  # type: ignore[arg-type]
        storage=storage,
        settings=SETTINGS,
    )

    assert expired == 1
    assert storage.objects == {}


async def test_a_file_that_wont_go_is_never_called_gone(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    """A delete that answers success isn't proof: read back, still there, the
    row keeps its key for the next try."""
    clock.freeze(NOW)
    _, token = await make_user()
    export_id = (await _ask(client, token)).json()["id"]
    storage = FakeStorage()
    await _write(db, storage, FakeQueue(), export_id)
    clock.freeze(NOW + timedelta(hours=24))

    async def silently_keeps(bucket: str, key: str) -> None:
        return None

    storage.delete = silently_keeps  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="1 of 1 files are still stored"):
        await _expire(db, storage, export_id)

    row = await db.get(DataExport, uuid.UUID(export_id))
    assert row is not None
    await db.refresh(row)
    assert row.status == "ready" and row.file_key is not None


async def test_the_last_failed_try_marks_it_failed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    test_redis: Redis,
) -> None:
    _, token = await make_user()
    export_id = (await _ask(client, token)).json()["id"]
    storage = FakeStorage()

    async def down(*args: Any, **kwargs: Any) -> None:
        raise OSError("storage is down")

    storage.put_bytes = down  # type: ignore[method-assign]
    ctx = {
        "sessionmaker": Sessions(db),
        "storage": storage,
        "settings": SETTINGS,
        "queue": FakeQueue(),
    }

    with pytest.raises(Exception, match="Retry"):
        await export_job.export_data({**ctx, "job_try": 1}, export_id=export_id)
    assert (
        await export_job.export_data(
            {**ctx, "job_try": export_job.EXPORT_TRIES}, export_id=export_id
        )
        == "failed"
    )

    seen = await client.get("/v1/me/export", headers=_auth(token))
    assert seen.json()["status"] == "failed"
    again = await _ask(client, token)
    assert again.json()["id"] != export_id


async def test_a_deleted_or_missing_export_is_nothing_to_do(db: AsyncSession) -> None:
    storage, queue = FakeStorage(), FakeQueue()

    assert await _write(db, storage, queue, str(uuid.uuid4())) == "nothing to do"
    assert await _expire(db, storage, str(uuid.uuid4())) == "nothing to do"
    assert storage.objects == {} and queue.jobs == []


BEFORE = "a3c12afe34d5"


async def test_the_downgrade_refuses_while_an_export_may_have_its_file(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    await db.execute(
        text("insert into data_exports (user_id, file_key) values (:u, 'exports/x')"),
        {"u": user.id},
    )

    with pytest.raises(RuntimeError, match="1 data exports may still have a file"):
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)
