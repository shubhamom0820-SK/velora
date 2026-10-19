"""The possible-minor list and its decisions (P-72, D-991, D-1050).

`GET /v1/admin/minor-flags` lists, for staff, who has two flags in 30 days
after any decision on them. `POST /v1/admin/users/{id}/minor-decision` leaves
them (an admin's), freezes them (staff's, D-922) or bans them as underage (an
admin's, permanent): each with a reason in `audit_log`, none automatic. An
underage ban keeps the account, banned and signed out, and no unban lifts it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.enums import BanKind, Gender, Role, UserStatus
from app.modules.account import service as account_service
from app.modules.auth import repository as auth_repository
from app.modules.auth.models import BannedIdentity
from app.modules.safety import fraud
from app.modules.safety import service as safety_service
from app.modules.safety.models import FraudEvent
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.admin.support import ADMIN, REASON, audits, auth, error, fresh, staff

pytestmark = pytest.mark.usefixtures("test_redis")


def _ago(days: float) -> datetime:
    return clock.now() - timedelta(days=days)


async def _flagged(
    db: AsyncSession, make_user: MakeUser, *days_ago: float
) -> tuple[uuid.UUID, str, str]:
    """A woman with a flag `days_ago` each: her id, token and number's hash."""
    woman, token = await make_user(Gender.FEMALE)
    for days in days_ago:
        db.add(
            FraudEvent(
                user_id=woman.id,
                signal=fraud.POSSIBLE_MINOR_SCORE,
                weight=safety_service.POSSIBLE_MINOR_WEIGHT,
                meta={"what": safety_service.POSSIBLE_MINOR_NOTE, "score": 0.5},
                created_at=_ago(days),
            )
        )
    await db.flush()
    return woman.id, token, woman.phone_hash


async def _decide(
    client: AsyncClient,
    token: str,
    user_id: uuid.UUID,
    decision: str,
    reason: str = REASON,
) -> Response:
    return await client.post(
        f"{ADMIN}/users/{user_id}/minor-decision",
        json={"decision": decision, "reason": reason},
        headers=auth(token),
    )


async def _listed(client: AsyncClient, token: str) -> list[uuid.UUID]:
    response = await client.get(f"{ADMIN}/minor-flags", headers=auth(token))
    assert response.status_code == 200, response.text
    return [uuid.UUID(item["user"]["id"]) for item in response.json()["items"]]


async def _bans(db: AsyncSession, phone_hash: str) -> list[BannedIdentity]:
    return list(
        await db.scalars(
            select(BannedIdentity)
            .where(BannedIdentity.value == phone_hash)
            .execution_options(populate_existing=True)
        )
    )


# --- The list ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.MODERATOR, Role.ADMIN])
async def test_staff_see_who_has_two_flags_in_30_days_and_nobody_else(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, role: Role
) -> None:
    staff_id, token = await staff(make_user, role)
    two, _, _ = await _flagged(db, make_user, 20, 2)
    one, _, _ = await _flagged(db, make_user, 2)
    apart, _, _ = await _flagged(db, make_user, 40, 2)

    response = await client.get(f"{ADMIN}/minor-flags", headers=auth(token))

    assert response.status_code == 200, response.text
    items = {uuid.UUID(item["user"]["id"]): item for item in response.json()["items"]}
    assert two in items
    assert one not in items
    assert apart not in items
    item = items[two]
    assert (item["flags"], item["scores"]) == (2, [0.5, 0.5])
    assert len(item["times"]) == 2
    assert item["first_at"] < item["last_at"]
    [entry] = await audits(db, staff_id, "minor_flags.list")
    assert entry.target_id is None


async def test_the_newest_flag_comes_first(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user)
    older, _, _ = await _flagged(db, make_user, 10, 9)
    newer, _, _ = await _flagged(db, make_user, 10, 1)

    listed = await _listed(client, token)

    assert listed.index(newer) < listed.index(older)


async def test_the_detail_carries_the_flags_while_they_wait(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user)
    two, _, _ = await _flagged(db, make_user, 3, 2)
    one, _, _ = await _flagged(db, make_user, 2)

    waiting = await client.get(f"{ADMIN}/users/{two}", headers=auth(token))
    alone = await client.get(f"{ADMIN}/users/{one}", headers=auth(token))

    assert waiting.json()["minor_flags"]["flags"] == 2
    assert alone.json()["minor_flags"] is None


# --- Deciding ---------------------------------------------------------------------------


async def test_an_admin_leaves_an_adult_and_she_leaves_the_list(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    woman, _, _ = await _flagged(db, make_user, 3, 2)

    response = await _decide(client, token, woman, "adult")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, woman)).status is UserStatus.ACTIVE
    [entry] = await audits(db, admin_id, fraud.MINOR_REVIEWED)
    assert (entry.target_type, entry.target_id) == ("user", woman)
    assert entry.meta == {"decision": "adult", "reason": REASON, "flags": 2}
    assert woman not in await _listed(client, token)


@pytest.mark.parametrize("decision", ["adult", "underage"])
async def test_a_moderator_never_leaves_nor_bans_as_underage(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, decision: str
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman, _, phone_hash = await _flagged(db, make_user, 3, 2)

    response = await _decide(client, token, woman, decision)

    assert response.status_code == 403, response.text
    assert error(response)["code"] == "FORBIDDEN"
    assert (await fresh(db, User, woman)).status is UserStatus.ACTIVE
    assert await _bans(db, phone_hash) == []
    assert await audits(db, moderator_id) == []


@pytest.mark.parametrize("role", [Role.MODERATOR, Role.ADMIN])
async def test_staff_freeze_signs_her_out_and_records_both(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
    role: Role,
) -> None:
    staff_id, token = await staff(make_user, role)
    woman, her_token, _ = await _flagged(db, make_user, 3, 2)

    response = await _decide(client, token, woman, "freeze")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, woman)).status is UserStatus.FROZEN
    assert (woman, events.CLOSE_SOCKETS) in [(e.user_id, e.type) for e in published]
    after = await client.get("/v1/me", headers=auth(her_token))
    assert error(after)["code"] == "ACCOUNT_FROZEN"
    [freeze] = await audits(db, staff_id, "user.freeze")
    assert freeze.meta == {"reason": REASON, "from": "active", "report_id": None}
    [decided] = await audits(db, staff_id, fraud.MINOR_REVIEWED)
    assert decided.meta == {"decision": "freeze", "reason": REASON, "flags": 2}


async def test_an_underage_ban_keeps_the_account_banned_and_signed_out(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    admin_id, token = await staff(make_user)
    woman, her_token, phone_hash = await _flagged(db, make_user, 3, 2)

    response = await _decide(client, token, woman, "underage")

    assert response.status_code == 204, response.text
    kept = await fresh(db, User, woman)
    assert (kept.status, kept.anonymised_at) == (UserStatus.BANNED, None)
    [ban] = await _bans(db, phone_hash)
    assert (ban.kind, ban.reason, ban.lifted_at) == (
        BanKind.PHONE_HASH,
        "underage",
        None,
    )
    assert await auth_repository.is_banned(db, phone_hash)
    assert (woman, events.CLOSE_SOCKETS) in [(e.user_id, e.type) for e in published]
    after = await client.get("/v1/me", headers=auth(her_token))
    assert error(after)["code"] == "ACCOUNT_BANNED"
    [entry] = await audits(db, admin_id, "user.ban_underage")
    assert entry.meta == {
        "reason": REASON,
        "from": "active",
        "erased": False,
        "kept_reason": None,
    }
    [decided] = await audits(db, admin_id, fraud.MINOR_REVIEWED)
    assert decided.meta == {"decision": "underage", "reason": REASON, "flags": 2}
    detail = await client.get(f"{ADMIN}/users/{woman}", headers=auth(token))
    assert detail.json()["ban"]["permanent"] is True


async def test_an_underage_ban_is_never_lifted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The fix P-72 needed: an unban here would have set her back to
    `active`, and into everyone's deck, with the number still barred."""
    admin_id, token = await staff(make_user)
    woman, _, phone_hash = await _flagged(db, make_user, 3, 2)
    assert (await _decide(client, token, woman, "underage")).status_code == 204

    response = await client.post(
        f"{ADMIN}/users/{woman}/status",
        json={"status": "active", "reason": REASON},
        headers=auth(token),
    )

    assert response.status_code == 422, response.text
    assert error(response)["details"]["why"] == "underage"
    assert (await fresh(db, User, woman)).status is UserStatus.BANNED
    [ban] = await _bans(db, phone_hash)
    assert (ban.reason, ban.lifted_at) == ("underage", None)
    assert await audits(db, admin_id, "user.unban") == []


async def test_over_a_plain_ban_the_row_keeps_its_reason_and_still_never_lifts(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-991: `ban_phone_hash` adds nothing over a standing row, so the
    account's record is what holds the ban permanent."""
    admin_id, token = await staff(make_user)
    woman, _, phone_hash = await _flagged(db, make_user, 3, 2)
    banned = await client.post(
        f"{ADMIN}/users/{woman}/status",
        json={"status": "banned", "reason": REASON},
        headers=auth(token),
    )
    assert banned.status_code == 204, banned.text

    response = await _decide(client, token, woman, "underage")

    assert response.status_code == 204, response.text
    [ban] = await _bans(db, phone_hash)
    assert (ban.reason, ban.lifted_at) == ("ban", None)
    [entry] = await audits(db, admin_id, "user.ban_underage")
    assert entry.meta is not None
    assert (entry.meta["from"], entry.meta["kept_reason"]) == ("banned", "ban")
    unban = await client.post(
        f"{ADMIN}/users/{woman}/status",
        json={"status": "active", "reason": REASON},
        headers=auth(token),
    )
    assert error(unban)["details"]["why"] == "underage"
    [still] = await _bans(db, phone_hash)
    assert still.lifted_at is None
    assert (await fresh(db, User, woman)).status is UserStatus.BANNED
    detail = await client.get(f"{ADMIN}/users/{woman}", headers=auth(token))
    assert detail.json()["ban"] == {
        "reason": "ban",
        "created_at": detail.json()["ban"]["created_at"],
        "permanent": True,
    }


async def test_an_erased_account_is_banned_as_underage_by_its_number_alone(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Her flags outlive the erasure (D-051), so she can still be listed; her
    row can't leave `deleted` (`ck_users_anonymised_is_deleted`)."""
    admin_id, token = await staff(make_user)
    woman, _, phone_hash = await _flagged(db, make_user, 3, 2)
    row = await fresh(db, User, woman)
    row.status = UserStatus.DELETED
    row.deleted_requested_at = clock.now() - timedelta(days=30)
    await db.flush()
    await account_service.anonymise(db, row)
    await db.flush()

    response = await _decide(client, token, woman, "underage")

    assert response.status_code == 204, response.text
    assert (await fresh(db, User, woman)).status is UserStatus.DELETED
    [ban] = await _bans(db, phone_hash)
    assert ban.reason == "underage"
    [entry] = await audits(db, admin_id, "user.ban_underage")
    assert entry.meta is not None and entry.meta["erased"] is True


async def test_a_plain_ban_is_not_permanent(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user)
    woman, _, _ = await _flagged(db, make_user)
    await client.post(
        f"{ADMIN}/users/{woman}/status",
        json={"status": "banned", "reason": REASON},
        headers=auth(token),
    )

    detail = await client.get(f"{ADMIN}/users/{woman}", headers=auth(token))

    assert detail.json()["ban"]["permanent"] is False


async def test_someone_not_waiting_is_refused_and_nothing_is_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    one, _, phone_hash = await _flagged(db, make_user, 2)
    decided, _, _ = await _flagged(db, make_user, 3, 2)
    assert (await _decide(client, token, decided, "adult")).status_code == 204

    for user_id in (one, decided):
        response = await _decide(client, token, user_id, "underage")
        assert response.status_code == 422, response.text
        assert error(response)["details"]["why"] == "not_waiting"
    assert (await fresh(db, User, one)).status is UserStatus.ACTIVE
    assert await _bans(db, phone_hash) == []
    assert len(await audits(db, admin_id, fraud.MINOR_REVIEWED)) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "underage"},
        {"decision": "underage", "reason": "short"},
        {"decision": "ban", "reason": REASON},
        {"decision": "underage", "reason": REASON, "extra": 1},
    ],
    ids=["no-reason", "short-reason", "unknown-decision", "extra-field"],
)
async def test_a_body_out_of_shape_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, body: dict[str, object]
) -> None:
    admin_id, token = await staff(make_user)
    woman, _, phone_hash = await _flagged(db, make_user, 3, 2)

    response = await client.post(
        f"{ADMIN}/users/{woman}/minor-decision", json=body, headers=auth(token)
    )

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert await _bans(db, phone_hash) == []
    assert await audits(db, admin_id) == []
