"""`notify()` (T-9.4): the one way anything tells a person something.

Only an active account is told (a paused one is sent nothing, T-9.6); a kind
only a man is told never reaches anyone else (D-554, P-460); a push waits in
`push_outbox` only when the kind's setting is on and there is a subscription;
a like to a man never names who (D-542); and a rollback tells nobody."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, UserStatus
from app.core.security import normalize_phone
from app.modules.notifications.models import NotificationPrefs
from app.modules.notifications.rules import Kind
from app.modules.notifications.service import notify
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings
from tests.modules.notifications.support import in_app, outbox, subscribed

SETTINGS = make_test_settings()
PAYLOAD = {"user_id": "00000000-0000-0000-0000-000000000001"}


async def _status(db: AsyncSession, user: User, status: UserStatus) -> None:
    await db.execute(update(User).where(User.id == user.id).values(status=status))


async def _pref(db: AsyncSession, user: User, **values: bool) -> None:
    await db.execute(
        update(NotificationPrefs)
        .where(NotificationPrefs.user_id == user.id)
        .values(**values)
    )


def _wakes(db: AsyncSession) -> list[events.Event]:
    """The wakes queued in the test's open transaction, not yet published."""
    pending = db.sync_session.info.get("events.pending", [])
    return [each for _, each in pending if each.type == events.PUSH_WAKE]


async def test_an_active_account_with_a_subscription_gets_both(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user(Gender.FEMALE)
    await subscribed(db, user.id)

    assert await notify(db, user.id, Kind.MATCH, PAYLOAD)

    assert await in_app(db, user.id) == [("match", PAYLOAD)]
    assert await outbox(db, user.id) == [("match", PAYLOAD)]
    [wake] = _wakes(db)
    assert (wake.channel, wake.envelope()) == ("wake:send_push", str(user.id))


async def test_without_a_subscription_only_the_list_is_written(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user(Gender.FEMALE)

    assert await notify(db, user.id, Kind.MATCH, PAYLOAD)

    assert await in_app(db, user.id) == [("match", PAYLOAD)]
    assert await outbox(db, user.id) == []
    assert _wakes(db) == []


@pytest.mark.parametrize(
    "status",
    [UserStatus.PAUSED, UserStatus.FROZEN, UserStatus.BANNED, UserStatus.DELETED],
)
async def test_an_account_that_is_not_active_is_told_nothing(
    db: AsyncSession, make_user: MakeUser, status: UserStatus
) -> None:
    """T-9.6: a paused account is sent nothing, no push and no row; nor is a
    frozen, banned or deleted one (`rules.TOLD`, an allowlist)."""
    user, _ = await make_user(Gender.FEMALE)
    await subscribed(db, user.id)
    await _status(db, user, status)

    assert not await notify(db, user.id, Kind.MATCH, PAYLOAD)

    assert await in_app(db, user.id) == []
    assert await outbox(db, user.id) == []
    assert _wakes(db) == []


async def test_nobody_is_told_about_an_id_with_no_account(
    db: AsyncSession, make_user: MakeUser
) -> None:
    await make_user()  # the test's transaction, open
    assert not await notify(db, uuid.uuid4(), Kind.MATCH, PAYLOAD)


@pytest.mark.parametrize(
    ("kind", "pref"),
    [
        (Kind.MATCH, "match"),
        (Kind.THREAD, "message"),
        (Kind.GIFT, "gift"),
        (Kind.ALBUM_REQUEST, "album"),
        (Kind.ALBUM_DECIDED, "album"),
        (Kind.KNOT_REQUESTED, "knot"),
        (Kind.KNOT_ACCEPTED, "knot"),
    ],
)
async def test_a_setting_turned_off_keeps_the_push_and_not_the_row(
    db: AsyncSession, make_user: MakeUser, kind: Kind, pref: str
) -> None:
    """P-550, P-631: gifts and the album have settings of their own. Off, the
    list still shows it; no push waits."""
    user, _ = await make_user(Gender.FEMALE)
    await subscribed(db, user.id)
    await _pref(db, user, **{pref: False})

    assert await notify(db, user.id, kind, PAYLOAD)

    assert await in_app(db, user.id) == [(str(kind), PAYLOAD)]
    assert await outbox(db, user.id) == []


@pytest.mark.parametrize(
    ("kind", "pref"), [(Kind.MESSAGE, "message"), (Kind.LIKE, "like")]
)
async def test_messages_and_likes_are_pushes_only(
    db: AsyncSession, make_user: MakeUser, kind: Kind, pref: str
) -> None:
    """D-852: the chats list and Liked you are their places in the app."""
    user, _ = await make_user(Gender.FEMALE)
    await subscribed(db, user.id)

    assert await notify(db, user.id, kind, PAYLOAD)
    assert await in_app(db, user.id) == []
    assert await outbox(db, user.id) == [(str(kind), PAYLOAD)]

    await _pref(db, user, **{pref: False})
    assert await notify(db, user.id, kind, PAYLOAD)
    assert len(await outbox(db, user.id)) == 1


@pytest.mark.parametrize("kind", [Kind.THREAD_EXPIRING, Kind.LOW_BALANCE])
@pytest.mark.parametrize("gender", [Gender.FEMALE, None])
async def test_an_hour_and_a_balance_never_reach_anyone_but_a_man(
    db: AsyncSession, make_user: MakeUser, kind: Kind, gender: Gender | None
) -> None:
    """D-554, P-460: nothing tells her an hour is running out; an allowlist, so
    someone with no gender is told neither."""
    if gender is None:
        # Signed up, gender not yet chosen: `users.gender` is set once only.
        account = await users_service.create_account(
            db, normalize_phone(f"+9196{uuid.uuid4().int % 10**8:08d}"), SETTINGS
        )
        user = account.user
        user.status = UserStatus.ACTIVE
        await db.flush()
    else:
        user, _ = await make_user(gender)
    await subscribed(db, user.id)

    assert not await notify(db, user.id, kind, {"thread_id": str(uuid.uuid4())})

    assert await in_app(db, user.id) == []
    assert await outbox(db, user.id) == []


async def test_a_man_is_told_his_hour_is_running_out(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    await subscribed(db, man.id)
    payload = {"thread_id": str(uuid.uuid4())}

    assert await notify(db, man.id, Kind.THREAD_EXPIRING, payload)

    assert await in_app(db, man.id) == [("thread_expiring", payload)]
    assert await outbox(db, man.id) == [("thread_expiring", payload)]


async def test_a_like_to_a_man_never_says_who(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-542: he pays to see who liked him; the push can't tell him free."""
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    for each in (man, woman):
        await subscribed(db, each.id)
    liker = {"user_id": str(uuid.uuid4()), "super": True}

    await notify(db, man.id, Kind.LIKE, liker)
    await notify(db, woman.id, Kind.LIKE, liker)

    assert await outbox(db, man.id) == [("like", {"super": True})]
    assert await outbox(db, woman.id) == [("like", liker)]


async def test_a_rolled_back_savepoint_tells_nobody(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user(Gender.FEMALE)
    await subscribed(db, user.id)

    savepoint = await db.begin_nested()
    await notify(db, user.id, Kind.MATCH, PAYLOAD)
    await savepoint.rollback()

    assert await in_app(db, user.id) == []
    assert await outbox(db, user.id) == []
    assert _wakes(db) == []


async def test_it_runs_only_inside_a_transaction(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user(Gender.FEMALE)
    await db.commit()
    with pytest.raises(RuntimeError, match="transaction"):
        await notify(db, user.id, Kind.MATCH, PAYLOAD)


class _Recorded:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> int:
        self.sent.append((channel, message))
        return 1


async def test_one_wake_is_published_however_many_were_queued() -> None:
    """D-850: the worker drains every waiting push when it hears one wake, so
    a request with three pushes costs Upstash one PUBLISH for them."""
    first, second = uuid.uuid4(), uuid.uuid4()
    queued = [
        events.Event(first, events.PUSH_WAKE, {}),
        events.Event(first, "match.created", {"match_id": "m"}),
        events.Event(second, events.PUSH_WAKE, {}),
        events.Event(second, events.PUSH_WAKE, {}),
    ]
    redis = _Recorded()

    await events.publish(queued, redis)  # type: ignore[arg-type]

    assert [channel for channel, _ in redis.sent] == [
        "wake:send_push",
        f"user:{first}",
    ]
    assert redis.sent[0][1] == str(first)
