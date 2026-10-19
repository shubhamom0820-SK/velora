"""The push sender (T-9.4, D-850): what waits in `push_outbox`, sent by the
worker. At send time, again: an active account, its setting on, under an hour
old, nobody blocked since (P-760), and for a message, no socket open anywhere
(D-854, Redis's `PUBSUB NUMSUB`). What a push carries is an allowlist: never an
expiry (P-460), never a name with `generic_text`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, Role, UserStatus
from app.core.events import user_channel
from app.core.providers.push import FakePush
from app.modules.notifications import rules, sender
from app.modules.notifications.models import (
    NotificationPrefs,
    PushOutbox,
    PushSubscription,
)
from app.modules.notifications.rules import Kind
from app.modules.notifications.service import notify
from app.modules.profiles.models import Profile
from app.modules.safety.models import Block
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.notifications.support import Sessions, outbox, subscribed

NOON = datetime(2026, 10, 9, 6, 30, tzinfo=UTC)


async def _send(
    db: AsyncSession, redis: Redis, push: FakePush, **kw: Any
) -> dict[str, int]:
    return await sender.send_waiting(Sessions(db), redis, push, **kw)  # type: ignore[arg-type]


async def _named(db: AsyncSession, user: User, name: str) -> None:
    await db.execute(
        update(Profile).where(Profile.user_id == user.id).values(first_name=name)
    )


async def _pair(
    db: AsyncSession, make_user: MakeUser
) -> tuple[User, User, PushSubscription]:
    """Her, subscribed, and him, named Arjun."""
    woman, _ = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    await _named(db, man, "Arjun")
    return woman, man, await subscribed(db, woman.id)


async def test_a_push_carries_the_kind_its_ids_and_the_name(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, man, sub = await _pair(db, make_user)
    thread_id = str(uuid.uuid4())
    await notify(
        db, woman.id, Kind.THREAD, {"thread_id": thread_id, "user_id": str(man.id)}
    )
    push = FakePush()

    assert await _send(db, test_redis, push) == {"sent": 1}

    [(to, data)] = push.sent
    assert to.endpoint == sub.endpoint
    assert data == {
        "kind": "thread",
        "thread_id": thread_id,
        "user_id": str(man.id),
        "name": "Arjun",
    }
    assert await outbox(db, woman.id) == []
    await db.refresh(sub)
    assert sub.last_ok_at is not None


async def test_generic_text_sends_no_name(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, man, _ = await _pair(db, make_user)
    await notify(db, woman.id, Kind.MATCH, {"match_id": "m", "user_id": str(man.id)})
    await db.execute(
        update(NotificationPrefs)
        .where(NotificationPrefs.user_id == woman.id)
        .values(generic_text=True)
    )
    push = FakePush()

    await _send(db, test_redis, push)

    [(_, data)] = push.sent
    assert data == {"kind": "match", "user_id": str(man.id)}


async def test_nothing_about_an_hour_ever_leaves_in_a_push(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    """P-460: the payload a man's warning carries has `expires_at`; the push
    carries the kind and the Thread only, by allowlist."""
    man, _ = await make_user()
    await subscribed(db, man.id)
    payload = {"thread_id": str(uuid.uuid4()), "expires_at": NOON.isoformat()}
    await notify(db, man.id, Kind.THREAD_EXPIRING, payload)
    push = FakePush()

    await _send(db, test_redis, push)

    [(_, data)] = push.sent
    assert data == {"kind": "thread_expiring", "thread_id": payload["thread_id"]}


@pytest.mark.parametrize("kind", list(Kind))
def test_no_kind_may_carry_an_expiry_a_price_or_a_text(kind: Kind) -> None:
    assert not {"expires_at", "price", "balance", "body"} & set(
        rules.PUSHED_FIELDS[kind]
    )


async def test_the_admins_push_carries_the_kind_and_the_person_alone(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    """D-994: no name, no count, no score, whoever is named and however the
    admin set `generic_text`."""
    admin, _ = await make_user(Gender.FEMALE)
    admin.role = Role.ADMIN
    flagged, _ = await make_user(Gender.FEMALE)
    await _named(db, flagged, "Priya")
    await subscribed(db, admin.id)
    payload = {
        "subject_id": str(flagged.id),
        "flags": 2,
        "scores": [0.41, 0.93],
        "first_at": NOON.isoformat(),
        "last_at": NOON.isoformat(),
    }
    await notify(db, admin.id, Kind.MINOR_FLAGS, payload)
    push = FakePush()

    assert await _send(db, test_redis, push) == {"sent": 1}

    [(_, data)] = push.sent
    assert data == {"kind": "minor_flags", "subject_id": str(flagged.id)}


async def test_an_admin_no_longer_one_is_pushed_nothing(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    admin, _ = await make_user(Gender.FEMALE)
    admin.role = Role.ADMIN
    await subscribed(db, admin.id)
    await notify(db, admin.id, Kind.MINOR_FLAGS, {"subject_id": str(uuid.uuid4())})
    await db.execute(update(User).where(User.id == admin.id).values(role=Role.USER))
    push = FakePush()

    assert await _send(db, test_redis, push) == {"skipped": 1}
    assert push.sent == []


async def test_a_setting_turned_off_since_sends_nothing(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, man, _ = await _pair(db, make_user)
    await notify(db, woman.id, Kind.GIFT, {"user_id": str(man.id)})
    await db.execute(
        update(NotificationPrefs)
        .where(NotificationPrefs.user_id == woman.id)
        .values(gift=False)
    )
    push = FakePush()

    assert await _send(db, test_redis, push) == {"skipped": 1}
    assert push.sent == []
    assert await outbox(db, woman.id) == []


async def test_an_account_paused_since_is_sent_nothing(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, man, _ = await _pair(db, make_user)
    await notify(db, woman.id, Kind.MATCH, {"user_id": str(man.id)})
    await db.execute(
        update(User).where(User.id == woman.id).values(status=UserStatus.PAUSED)
    )
    push = FakePush()

    assert await _send(db, test_redis, push) == {"skipped": 1}
    assert push.sent == []


async def test_a_block_since_sends_nothing(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    """P-760: a block between the write and the send."""
    woman, man, _ = await _pair(db, make_user)
    await notify(db, woman.id, Kind.MATCH, {"user_id": str(man.id)})
    db.add(Block(blocker_id=woman.id, blocked_id=man.id))
    await db.flush()
    push = FakePush()

    assert await _send(db, test_redis, push) == {"skipped": 1}
    assert push.sent == []


async def test_a_push_an_hour_old_is_dropped_not_sent(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    woman, man, _ = await _pair(db, make_user)
    await notify(db, woman.id, Kind.MATCH, {"user_id": str(man.id)})
    await db.execute(
        update(PushOutbox)
        .where(PushOutbox.user_id == woman.id)
        .values(created_at=NOON - timedelta(seconds=rules.PUSH_TTL_S))
    )
    push = FakePush()

    assert await _send(db, test_redis, push) == {"stale": 1}
    assert push.sent == []
    assert await outbox(db, woman.id) == []


async def test_a_message_waits_on_presence_by_numsub(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    """D-854: with a subscriber on `user:{id}` anywhere (an API instance
    holding a socket of hers), no push; without, one."""
    woman, man, _ = await _pair(db, make_user)
    message = {"thread_id": str(uuid.uuid4()), "user_id": str(man.id)}
    push = FakePush()

    async with test_redis.pubsub() as pubsub:
        await pubsub.subscribe(user_channel(woman.id))
        await notify(db, woman.id, Kind.MESSAGE, message)
        assert await _send(db, test_redis, push) == {"connected": 1}
    assert push.sent == []

    await db.connection()  # a transaction again, as a request would have
    await notify(db, woman.id, Kind.MESSAGE, message)
    assert await _send(db, test_redis, push) == {"sent": 1}
    assert [data["kind"] for _, data in push.sent] == ["message"]


async def test_only_a_message_waits_on_presence(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, man, _ = await _pair(db, make_user)
    push = FakePush()
    async with test_redis.pubsub() as pubsub:
        await pubsub.subscribe(user_channel(woman.id))
        await notify(db, woman.id, Kind.MATCH, {"user_id": str(man.id)})
        assert await _send(db, test_redis, push) == {"sent": 1}


class _NoRedis:
    async def pubsub_numsub(self, *channels: str) -> list[tuple[str, int]]:
        raise ConnectionError("down")


async def test_presence_unknown_pushes_rather_than_stay_silent(
    db: AsyncSession, make_user: MakeUser
) -> None:
    woman, man, _ = await _pair(db, make_user)
    await notify(db, woman.id, Kind.MESSAGE, {"thread_id": "t", "user_id": str(man.id)})
    push = FakePush()
    assert await _send(db, _NoRedis(), push) == {"sent": 1}  # type: ignore[arg-type]


async def test_a_gone_subscription_is_deleted_and_the_others_still_sent(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, man, gone = await _pair(db, make_user)
    kept = await subscribed(db, woman.id)
    await notify(db, woman.id, Kind.MATCH, {"user_id": str(man.id)})
    push = FakePush()
    push.gone_endpoints.add(gone.endpoint)

    assert await _send(db, test_redis, push) == {"sent": 1}

    left = await db.scalars(
        select(PushSubscription.endpoint).where(PushSubscription.user_id == woman.id)
    )
    assert list(left) == [kept.endpoint]
    assert [to.endpoint for to, _ in push.sent] == [kept.endpoint]


async def test_a_failure_is_tried_three_times_then_dropped(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, man, sub = await _pair(db, make_user)
    await notify(db, woman.id, Kind.MATCH, {"user_id": str(man.id)})
    push = FakePush()
    push.failing_endpoints.add(sub.endpoint)

    outcomes = [await _send(db, test_redis, push) for _ in range(rules.PUSH_ATTEMPTS)]

    assert outcomes == [{"retried": 1}, {"retried": 1}, {"dropped": 1}]
    assert await outbox(db, woman.id) == []
    assert await _send(db, test_redis, push) == {}


async def test_a_claim_gone_stale_is_taken_again(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser, clock: ModuleType
) -> None:
    """A sender that died mid-send left `claimed_at`; five minutes on, the push
    is another sender's."""
    clock.freeze(NOON)
    woman, man, _ = await _pair(db, make_user)
    await notify(db, woman.id, Kind.MATCH, {"user_id": str(man.id)})
    await db.execute(
        update(PushOutbox)
        .where(PushOutbox.user_id == woman.id)
        .values(created_at=NOON, claimed_at=NOON, attempts=1)
    )
    push = FakePush()

    clock.freeze(NOON + timedelta(seconds=rules.CLAIM_STALE_S - 1))
    assert await _send(db, test_redis, push) == {}
    clock.freeze(NOON + timedelta(seconds=rules.CLAIM_STALE_S + 1))
    assert await _send(db, test_redis, push) == {"sent": 1}


async def test_a_kind_nobody_knows_is_dropped(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, _ = await make_user(Gender.FEMALE)
    await subscribed(db, woman.id)
    db.add(PushOutbox(user_id=woman.id, kind="nonsense", payload={}))
    await db.flush()
    push = FakePush()

    assert await _send(db, test_redis, push) == {"unknown": 1}
    assert push.sent == []


async def test_batches_run_until_the_outbox_is_empty(
    db: AsyncSession, test_redis: Redis, make_user: MakeUser
) -> None:
    woman, man, _ = await _pair(db, make_user)
    for _ in range(5):
        await notify(db, woman.id, Kind.MATCH, {"user_id": str(man.id)})
    push = FakePush()

    assert await _send(db, test_redis, push, limit=2) == {"sent": 5}
    assert len(push.sent) == 5
