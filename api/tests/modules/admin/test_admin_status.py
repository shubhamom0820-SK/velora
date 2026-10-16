"""`POST /v1/admin/users/{id}/status` (T-9.5, D-922): a moderator freezes; an
admin bans, unbans and unfreezes. A freeze or a ban signs the person out and
closes their sockets in its transaction (D-557). A ban keeps the number in
`banned_identities`; an unban lifts that row in place, never deletes it
(golden rule 12), and the database refuses lifting anything but a ban.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.enums import BanKind, FraudBand, Role, UserStatus
from app.modules.account import service as account_service
from app.modules.admin.service import SYSTEM_USER_ID
from app.modules.auth import repository as auth_repository
from app.modules.auth.models import BannedIdentity
from app.modules.safety import repository as safety_repository
from app.modules.safety.models import FraudScore
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.admin.support import ADMIN, REASON, audits, auth, error, fresh, staff

pytestmark = pytest.mark.usefixtures("test_redis")


def _path(user_id: uuid.UUID) -> str:
    return f"{ADMIN}/users/{user_id}/status"


async def _set(
    client: AsyncClient,
    token: str,
    user_id: uuid.UUID,
    status: str,
    reason: str = REASON,
) -> Response:
    return await client.post(
        _path(user_id), json={"status": status, "reason": reason}, headers=auth(token)
    )


async def _bans(db: AsyncSession, phone_hash: str) -> list[BannedIdentity]:
    return list(
        await db.scalars(
            select(BannedIdentity)
            .where(BannedIdentity.value == phone_hash)
            .order_by(BannedIdentity.lifted_at.nulls_last(), BannedIdentity.id)
            .execution_options(populate_existing=True)
        )
    )


async def _erased(db: AsyncSession, user: User) -> None:
    user.status = UserStatus.DELETED
    user.deleted_requested_at = clock.now() - timedelta(days=30)
    await db.flush()
    await account_service.anonymise(db, user)
    await db.flush()


# --- Freeze ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.MODERATOR, Role.ADMIN])
async def test_staff_freeze_signs_out_closes_sockets_and_audits(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
    role: Role,
) -> None:
    moderator_id, token = await staff(make_user, role)
    man, his_token = await make_user()
    man_id = man.id

    response = await _set(client, token, man_id, "frozen")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, man_id)).status is UserStatus.FROZEN
    assert (man_id, events.CLOSE_SOCKETS) in [(e.user_id, e.type) for e in published]
    after = await client.get("/v1/me", headers=auth(his_token))
    assert error(after)["code"] == "ACCOUNT_FROZEN"
    [entry] = await audits(db, moderator_id, "user.freeze")
    assert (entry.target_type, entry.target_id) == ("user", man_id)
    assert entry.meta == {"reason": REASON, "from": "active", "report_id": None}


@pytest.mark.parametrize(
    ("status", "why"),
    [
        (UserStatus.FROZEN, "already_frozen"),
        (UserStatus.BANNED, "banned"),
        (UserStatus.DELETED, "deleted"),
    ],
)
async def test_only_who_can_sign_in_is_frozen_and_nothing_else_is_written(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    status: UserStatus,
    why: str,
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    man_id = man.id
    man.status = status
    await db.flush()

    response = await _set(client, token, man_id, "frozen")

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    assert error(response)["details"]["why"] == why
    assert (await fresh(db, User, man_id)).status is status
    assert await audits(db, moderator_id) == []


@pytest.mark.parametrize(
    ("status", "start"),
    [
        ("banned", UserStatus.ACTIVE),
        ("active", UserStatus.BANNED),
        ("active", UserStatus.FROZEN),
    ],
    ids=["ban", "unban", "unfreeze"],
)
async def test_a_moderator_never_bans_unbans_or_unfreezes(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    status: str,
    start: UserStatus,
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    man_id, man_hash = man.id, man.phone_hash
    man.status = start
    await db.flush()

    response = await _set(client, token, man_id, status)

    assert response.status_code == 403
    assert error(response)["code"] == "FORBIDDEN"
    assert (await fresh(db, User, man_id)).status is start
    assert await _bans(db, man_hash) == []
    assert await audits(db, moderator_id) == []


# --- Ban --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start", [UserStatus.ACTIVE, UserStatus.PAUSED, UserStatus.FROZEN]
)
async def test_an_admins_ban_bars_the_number_signs_out_and_audits(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
    start: UserStatus,
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id, man_hash = man.id, man.phone_hash
    man.status = start
    await db.flush()

    response = await _set(client, token, man_id, "banned")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, man_id)).status is UserStatus.BANNED
    [ban] = await _bans(db, man_hash)
    assert (ban.kind, ban.reason, ban.lifted_at) == (BanKind.PHONE_HASH, "ban", None)
    assert await auth_repository.is_banned(db, man_hash)
    assert (man_id, events.CLOSE_SOCKETS) in [(e.user_id, e.type) for e in published]
    [entry] = await audits(db, admin_id, "user.ban")
    assert entry.meta == {
        "reason": REASON,
        "from": start.value,
        "erased": False,
        "report_id": None,
    }


async def test_a_ban_during_a_deletions_29_days_stops_the_erasure_and_keeps_the_request(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """P-401, D-929: the erasure takes only `deleted` accounts, so a banned one
    keeps its data; `deleted_requested_at` stays as the record of the ask."""
    _, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id
    asked = clock.now() - timedelta(days=3)
    man.status, man.deleted_requested_at = UserStatus.DELETED, asked
    await db.flush()

    response = await _set(client, token, man_id, "banned")

    assert response.status_code == 204, response.text
    row = await fresh(db, User, man_id)
    assert (row.status, row.deleted_requested_at) == (UserStatus.BANNED, asked)


async def test_an_erased_account_is_banned_by_its_number_alone(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Its row can't leave `deleted` (`ck_users_anonymised_is_deleted`)."""
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id, man_hash = man.id, man.phone_hash
    await _erased(db, man)

    response = await _set(client, token, man_id, "banned")
    again = await _set(client, token, man_id, "banned")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, man_id)).status is UserStatus.DELETED
    [ban] = await _bans(db, man_hash)
    assert ban.reason == "ban"
    assert error(again)["details"]["why"] == "already_banned"
    [entry] = await audits(db, admin_id, "user.ban")
    assert entry.meta is not None and entry.meta["erased"] is True


async def test_banning_twice_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id
    await _set(client, token, man_id, "banned")

    again = await _set(client, token, man_id, "banned")

    assert error(again)["code"] == "NOT_ALLOWED"
    assert error(again)["details"]["why"] == "already_banned"
    assert len(await audits(db, admin_id, "user.ban")) == 1


# --- Unban ------------------------------------------------------------------------------


async def test_an_unban_lifts_the_row_in_place_and_returns_the_account(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id, man_hash = man.id, man.phone_hash
    await _set(client, token, man_id, "banned")

    response = await _set(
        client, token, man_id, "active", "Banned by mistake, see report."
    )

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, man_id)).status is UserStatus.ACTIVE
    [ban] = await _bans(db, man_hash)
    assert (ban.reason, ban.lifted_by, ban.lift_reason) == (
        "ban",
        admin_id,
        "Banned by mistake, see report.",
    )
    assert ban.lifted_at is not None
    assert not await auth_repository.is_banned(db, man_hash)
    [entry] = await audits(db, admin_id, "user.unban")
    assert entry.meta == {
        "reason": "Banned by mistake, see report.",
        "to": "active",
        "lifted": 1,
        "erased": False,
    }


async def test_an_unban_of_someone_who_asked_to_go_returns_them_to_deleted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The founder's answer (D-922): the erasure then runs as /privacy said."""
    _, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id
    man.status, man.deleted_requested_at = UserStatus.DELETED, clock.now()
    await db.flush()
    await _set(client, token, man_id, "banned")

    response = await _set(client, token, man_id, "active")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, man_id)).status is UserStatus.DELETED


async def test_an_erased_accounts_number_is_unbanned_alone(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user)
    man, _ = await make_user()
    man_id, man_hash = man.id, man.phone_hash
    await _erased(db, man)
    await _set(client, token, man_id, "banned")

    response = await _set(client, token, man_id, "active")
    again = await _set(client, token, man_id, "active")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, man_id)).status is UserStatus.DELETED
    assert not await auth_repository.is_banned(db, man_hash)
    assert error(again)["details"]["why"] == "not_banned"


async def test_a_number_banned_again_after_a_lift_gets_a_row_of_its_own(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user)
    man, _ = await make_user()
    man_id, man_hash = man.id, man.phone_hash
    await _set(client, token, man_id, "banned")
    await _set(client, token, man_id, "active")

    response = await _set(client, token, man_id, "banned")

    assert response.status_code == 204, response.text
    lifted, standing = await _bans(db, man_hash)
    assert lifted.lifted_at is not None and standing.lifted_at is None
    assert await auth_repository.is_banned(db, man_hash)


async def test_unbanning_someone_not_banned_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id

    response = await _set(client, token, man_id, "active")

    assert error(response)["code"] == "NOT_ALLOWED"
    assert error(response)["details"]["why"] == "not_banned"
    assert await audits(db, admin_id) == []


# --- What the database allows (migration 7c8a628fd3d7) --------------------------------


async def _refused(db: AsyncSession, sql: str, params: dict[str, object]) -> str:
    with pytest.raises(DBAPIError) as refused:
        async with db.begin_nested():
            await db.execute(text(sql), params)
    return str(refused.value)


async def test_an_underage_ban_can_never_be_lifted_nor_any_ban_deleted(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin_id, _ = await staff(make_user)
    underage = BannedIdentity(
        kind=BanKind.PHONE_HASH, value="hash-u", reason="underage"
    )
    ban = BannedIdentity(kind=BanKind.PHONE_HASH, value="hash-b", reason="ban")
    db.add_all([underage, ban])
    await db.flush()
    lift = (
        "update banned_identities set lifted_at = now(), lifted_by = :by, "
        "lift_reason = 'lifted by hand' where id = :id"
    )

    assert "only a ban is ever lifted, never underage" in await _refused(
        db, lift, {"by": admin_id, "id": underage.id}
    )
    assert "a ban is lifted, never deleted" in await _refused(
        db, "delete from banned_identities where id = :id", {"id": ban.id}
    )
    assert "a ban changes only by being lifted" in await _refused(
        db,
        "update banned_identities set value = 'other' where id = :id",
        {"id": ban.id},
    )
    await db.execute(text(lift), {"by": admin_id, "id": ban.id})
    assert "a lifted ban never changes again" in await _refused(
        db,
        "update banned_identities set lift_reason = 'rewritten' where id = :id",
        {"id": ban.id},
    )
    assert "ck_banned_identities_lift_complete" in await _refused(
        db,
        "insert into banned_identities (kind, value, reason, lifted_at) "
        "values ('phone_hash', 'hash-x', 'ban', now())",
        {},
    )


# --- Unfreeze ---------------------------------------------------------------------------


async def test_an_admins_unfreeze_is_the_tools_own_path_and_starts_the_score_again(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-906: active, the score 0 and normal, and only what comes after counts."""
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id
    man.status = UserStatus.FROZEN
    await safety_repository.save_score(
        db,
        man_id,
        score=90,
        band=FraudBand.FREEZE,
        signals={"report_received": 90},
        counted_from=None,
    )
    await db.flush()

    response = await _set(client, token, man_id, "active")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, man_id)).status is UserStatus.ACTIVE
    score = await db.scalar(
        select(FraudScore)
        .where(FraudScore.user_id == man_id)
        .execution_options(populate_existing=True)
    )
    assert score is not None
    assert (score.score, score.band) == (0, FraudBand.NORMAL)
    assert score.counted_from is not None
    [entry] = await audits(db, admin_id, "fraud.unfreeze")
    assert entry.meta == {"reason": REASON, "score_before": 90, "band_before": "freeze"}


# --- Who and what ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "who", ["nobody", "the system user"], ids=["unknown", "system"]
)
async def test_an_account_nobody_holds_or_the_system_user_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, who: str
) -> None:
    admin_id, token = await staff(make_user)
    target = uuid.uuid4() if who == "nobody" else SYSTEM_USER_ID

    response = await _set(client, token, target, "frozen")

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"
    assert await audits(db, admin_id) == []


@pytest.mark.parametrize(
    "body",
    [
        {"status": "frozen", "reason": "too short"},
        {"status": "frozen"},
        {"status": "paused", "reason": REASON},
        {"status": "frozen", "reason": REASON, "extra": 1},
    ],
    ids=["short reason", "no reason", "a status staff never set", "an extra field"],
)
async def test_a_body_out_of_shape_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, body: dict[str, object]
) -> None:
    _, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id

    response = await client.post(_path(man_id), json=body, headers=auth(token))

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
