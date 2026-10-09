"""Scoring and its actions (T-9.2, D-031, D-900 to D-905): the score and band
written from the last 7 days' signals; `shadow` out of a normal person's feed
and back as it decays; `freeze` frozen, signed out everywhere, sockets closed,
audited as the system user and warned of; only an account that can sign in is
frozen, and nothing automatic ever lifts it; three reporting numbers that
share a Thread with someone freeze them in the third report's transaction."""

from __future__ import annotations

import uuid
from datetime import timedelta
from types import ModuleType

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core import events
from app.core.enums import FraudBand, Gender, UserStatus
from app.core.security import make_access_token
from app.modules.admin.models import AuditLogEntry
from app.modules.admin.service import SYSTEM_USER_ID
from app.modules.auth import repository as auth_repository
from app.modules.auth.models import Session
from app.modules.safety import scoring
from app.modules.safety.models import FraudEvent, FraudScore, Report
from app.modules.users.models import User
from tests.conftest import CapturedLogs, MakeThread, MakeUser, make_test_settings
from tests.modules.discovery.support import bearer, error, ids, north, person
from tests.modules.safety.support import report

pytestmark = pytest.mark.usefixtures("test_redis")


def _event(
    user_id: uuid.UUID, signal: str, weight: int, *, ago: timedelta = timedelta(0)
) -> FraudEvent:
    return FraudEvent(
        user_id=user_id,
        signal=signal,
        weight=weight,
        created_at=core_clock.now() - ago,
    )


async def _signalled(
    db: AsyncSession, user_id: uuid.UUID, *pairs: tuple[str, int]
) -> None:
    for signal, weight in pairs:
        db.add(_event(user_id, signal, weight))
    await db.flush()


# Signals worth 95: three kinds, each at its cap.
SPAMMER = (
    *[("message_rejected", 15)] * 3,
    ("identical_first_message", 25),
    ("many_new_threads", 25),
)


async def _recompute(db: AsyncSession, user_id: uuid.UUID) -> scoring.Outcome | None:
    if db.in_transaction():
        await db.commit()
    async with db.begin():
        return await scoring.recompute(db, user_id)


async def _score(db: AsyncSession, user_id: uuid.UUID) -> FraudScore | None:
    return await db.get(FraudScore, user_id, populate_existing=True)


async def _user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id, populate_existing=True)
    assert user is not None
    return user


async def _audit(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[uuid.UUID, str, dict[str, object]]]:
    rows = await db.execute(
        select(AuditLogEntry.actor_id, AuditLogEntry.action, AuditLogEntry.meta)
        .where(AuditLogEntry.target_type == "user", AuditLogEntry.target_id == user_id)
        .order_by(AuditLogEntry.created_at, AuditLogEntry.action)
    )
    return [(row[0], row[1], row[2]) for row in rows]


async def _signed_in(db: AsyncSession, user_id: uuid.UUID, families: int = 2) -> None:
    now = core_clock.now()
    for _ in range(families):
        await auth_repository.insert_session(
            db,
            user_id=user_id,
            family_id=uuid.uuid4(),
            token_hash=uuid.uuid4().hex,
            expires_at=now + timedelta(days=30),
            auth_time=now,
        )


async def _live_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    rows = await db.scalars(
        select(Session.id)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .execution_options(populate_existing=True)
    )
    return len(rows.all())


# --- The score ---------------------------------------------------------------------------


async def test_the_score_band_and_shares_are_written(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    await _signalled(db, man.id, ("message_rejected", 15), ("contact_masked", 2))

    outcome = await _recompute(db, man.id)

    assert outcome == scoring.Outcome(score=17, band=FraudBand.NORMAL, frozen=False)
    row = await _score(db, man.id)
    assert row is not None
    assert (row.score, row.band, row.signals, row.counted_from) == (
        17,
        FraudBand.NORMAL,
        {"contact_masked": 2, "message_rejected": 15},
        None,
    )


async def test_older_signals_count_less_and_a_week_old_ones_not_at_all(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    db.add(_event(man.id, "chargeback_shortfall", 30, ago=timedelta(days=3, hours=12)))
    db.add(_event(man.id, "location_jump", 15, ago=timedelta(days=7, minutes=1)))
    await db.flush()

    outcome = await _recompute(db, man.id)

    assert outcome is not None
    assert outcome.score == 15


async def test_a_shadowed_person_leaves_a_normal_feed_and_comes_back_as_it_decays(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    viewer, _ = await person(db, make_user, Gender.MALE)
    viewer_id = viewer.id
    her, _ = await person(db, make_user, at=north(1))
    her_id = her.id
    await _signalled(
        db,
        her_id,
        *[("message_rejected", 15)] * 3,
        ("identical_first_message", 25),
    )

    assert (await _recompute(db, her_id)).band is FraudBand.SHADOW  # type: ignore[union-attr]
    token = make_access_token(
        viewer_id,
        (await _user(db, viewer_id)).role,
        make_test_settings(),
        auth_time=core_clock.now(),
    )
    assert await ids(client, token) == []

    # 70 at four days of seven: 30, monitor, which everyone sees.
    clock.freeze(core_clock.now() + timedelta(days=4))
    assert (await _recompute(db, her_id)).band is FraudBand.MONITOR  # type: ignore[union-attr]
    token = make_access_token(
        viewer_id,
        (await _user(db, viewer_id)).role,
        make_test_settings(),
        auth_time=core_clock.now(),
    )
    assert await ids(client, token) == [str(her_id)]
    assert [action for _, action, _ in await _audit(db, her_id)] == [
        "fraud.band",
        "fraud.band",
    ]


# --- The freeze --------------------------------------------------------------------------


async def test_a_score_above_80_freezes_signs_out_closes_sockets_and_audits(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
) -> None:
    woman, token = await make_user(Gender.FEMALE)
    her_id = woman.id
    await _signed_in(db, her_id)
    await _signalled(db, her_id, *SPAMMER)

    outcome = await _recompute(db, her_id)
    committed = events.take_committed(db)

    assert outcome == scoring.Outcome(score=95, band=FraudBand.FREEZE, frozen=True)
    assert (await _user(db, her_id)).status is UserStatus.FROZEN
    assert await _live_sessions(db, her_id) == 0
    assert [(e.user_id, e.type) for e in committed] == [(her_id, events.CLOSE_SOCKETS)]
    assert await _audit(db, her_id) == [
        (SYSTEM_USER_ID, "fraud.band", {"from": "normal", "to": "freeze", "score": 95}),
        (SYSTEM_USER_ID, "fraud.freeze", {"rule": "score", "score": 95}),
    ]
    [warned] = [e for e in captured_logs.events if e.get("event") == "fraud.frozen"]
    assert (warned["user_id"], warned["rule"], warned["score"]) == (
        str(her_id),
        "score",
        95,
    )
    response = await client.get("/v1/me", headers=bearer(token))
    assert response.status_code == 403
    assert error(response)["code"] == "ACCOUNT_FROZEN"


async def test_a_paused_account_is_frozen_too(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    man.status = UserStatus.PAUSED
    await _signalled(db, man.id, *SPAMMER)

    outcome = await _recompute(db, man.id)

    assert outcome is not None and outcome.frozen
    assert (await _user(db, man.id)).status is UserStatus.FROZEN


@pytest.mark.parametrize("status", [UserStatus.DELETED, UserStatus.BANNED])
async def test_a_deleted_or_banned_account_is_left_as_it_is(
    db: AsyncSession, make_user: MakeUser, status: UserStatus
) -> None:
    """D-902: a deleted one is left to its erasure, which a freeze would stop."""
    man, _ = await make_user()
    man.status = status
    await _signalled(db, man.id, *SPAMMER)

    outcome = await _recompute(db, man.id)

    assert outcome == scoring.Outcome(score=95, band=FraudBand.FREEZE, frozen=False)
    assert (await _user(db, man.id)).status is status
    assert [action for _, action, _ in await _audit(db, man.id)] == ["fraud.band"]


async def test_an_account_restored_while_in_the_freeze_band_is_frozen_then(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Deleted when the band reached freeze, so left alone (D-902); signing in
    again restores it (D-500), and the next score freezes it."""
    man, _ = await make_user()
    man.status = UserStatus.DELETED
    await _signalled(db, man.id, *SPAMMER)
    assert not (await _recompute(db, man.id)).frozen  # type: ignore[union-attr]
    (await _user(db, man.id)).status = UserStatus.ACTIVE

    outcome = await _recompute(db, man.id)

    assert outcome is not None and outcome.frozen
    assert (await _user(db, man.id)).status is UserStatus.FROZEN


async def test_nothing_automatic_lifts_a_freeze(
    db: AsyncSession, make_user: MakeUser, clock: ModuleType
) -> None:
    man, _ = await make_user()
    await _signalled(db, man.id, *SPAMMER)
    assert (await _recompute(db, man.id)).frozen  # type: ignore[union-attr]

    clock.freeze(core_clock.now() + timedelta(days=8))
    outcome = await _recompute(db, man.id)

    assert outcome == scoring.Outcome(score=0, band=FraudBand.NORMAL, frozen=False)
    assert (await _user(db, man.id)).status is UserStatus.FROZEN


async def test_a_freeze_is_written_once_however_often_it_is_scored(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    await _signalled(db, man.id, *SPAMMER)
    await _recompute(db, man.id)

    again = await _recompute(db, man.id)

    assert again is not None and not again.frozen
    assert [action for _, action, _ in await _audit(db, man.id)] == [
        "fraud.band",
        "fraud.freeze",
    ]


async def test_possible_minor_scores_never_act_on_anyone_alone(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-093: a model's probability weighs in; it never shadows or freezes."""
    woman, _ = await make_user(Gender.FEMALE)
    await _signalled(db, woman.id, *[("possible_minor_photo_score", 10)] * 20)

    outcome = await _recompute(db, woman.id)

    assert outcome == scoring.Outcome(score=20, band=FraudBand.NORMAL, frozen=False)
    assert (await _user(db, woman.id)).status is UserStatus.ACTIVE


async def test_the_system_user_is_never_scored(db: AsyncSession) -> None:
    assert await _recompute(db, SYSTEM_USER_ID) is None


# --- Three reports in 24 hours (D-031, D-901) ----------------------------------------------


async def _reporter(
    make_user: MakeUser, make_thread: MakeThread, him: User, *, thread: bool = True
) -> tuple[User, str]:
    woman, token = await make_user(Gender.FEMALE)
    if thread:
        await make_thread(him, woman)
    return woman, token


async def _reporters(
    make_user: MakeUser,
    make_thread: MakeThread,
    him: User,
    n: int,
    *,
    threads: bool = True,
) -> list[str]:
    return [
        (await _reporter(make_user, make_thread, him, thread=threads))[1]
        for _ in range(n)
    ]


async def test_three_reporters_sharing_a_thread_freeze_in_the_third_report(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    him, his_token = await make_user()
    him_id = him.id
    first, second, third = await _reporters(make_user, make_thread, him, 3)

    for token in (first, second):
        assert (await report(client, token, him_id)).status_code == 201
    assert (await _user(db, him_id)).status is UserStatus.ACTIVE

    assert (await report(client, third, him_id)).status_code == 201

    assert (await _user(db, him_id)).status is UserStatus.FROZEN
    assert (him_id, events.CLOSE_SOCKETS) in [(e.user_id, e.type) for e in published]
    assert (await _audit(db, him_id))[-1] == (
        SYSTEM_USER_ID,
        "fraud.freeze",
        {"rule": "reports", "score": 60},
    )
    response = await client.get("/v1/me", headers=bearer(his_token))
    assert error(response)["code"] == "ACCOUNT_FROZEN"


async def test_one_reporter_three_times_is_one(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    him, _ = await make_user()
    him_id = him.id
    [token] = await _reporters(make_user, make_thread, him, 1)

    for _ in range(3):
        assert (await report(client, token, him_id)).status_code == 201

    assert (await _user(db, him_id)).status is UserStatus.ACTIVE
    assert (await _score(db, him_id)).score == 20  # type: ignore[union-attr]


async def test_reporters_who_never_shared_a_thread_shadow_and_never_freeze(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """D-901: strangers can't freeze someone by reporting them; their reports
    still score, and three take a fake profile out of everyone's deck."""
    her, _ = await make_user(Gender.FEMALE)
    her_id = her.id
    tokens = await _reporters(make_user, make_thread, her, 3, threads=False)

    for token in tokens:
        assert (await report(client, token, her_id)).status_code == 201

    assert (await _user(db, her_id)).status is UserStatus.ACTIVE
    row = await _score(db, her_id)
    assert row is not None
    assert (row.score, row.band) == (60, FraudBand.SHADOW)


async def test_reports_spread_over_more_than_a_day_dont_freeze(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    him, _ = await make_user()
    him_id = him.id
    early = await _reporters(make_user, make_thread, him, 2)
    for token in early:
        assert (await report(client, token, him_id)).status_code == 201
    await db.execute(
        update(Report)
        .where(Report.reported_id == him_id)
        .values(created_at=core_clock.now() - timedelta(hours=25))
    )
    [late] = await _reporters(make_user, make_thread, him, 1)

    assert (await report(client, late, him_id)).status_code == 201

    assert (await _user(db, him_id)).status is UserStatus.ACTIVE


async def test_one_numbers_two_accounts_report_as_one(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """By number (D-901): a reporter erased and signed up again on the same
    number is the same reporter. The erasure is stood in for by its row's
    shape; the new account takes the number's hash, as sign-up would."""
    him, _ = await make_user()
    him_id = him.id
    (first, first_token), (_, second_token) = [
        await _reporter(make_user, make_thread, him) for _ in range(2)
    ]
    for token in (first_token, second_token):
        assert (await report(client, token, him_id)).status_code == 201
    number = first.phone_hash
    await db.execute(
        update(User)
        .where(User.id == first.id)
        .values(
            status=UserStatus.DELETED,
            anonymised_at=core_clock.now(),
            phone_enc=None,
            dob=None,
            pin_hash=None,
        )
    )
    again, again_token = await _reporter(make_user, make_thread, him)
    await db.execute(update(User).where(User.id == again.id).values(phone_hash=number))

    assert (await report(client, again_token, him_id)).status_code == 201

    assert (await _user(db, him_id)).status is UserStatus.ACTIVE
