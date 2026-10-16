"""`GET /v1/admin/users` and `GET /v1/admin/users/{id}` (T-9.5).

- **A number is found only whole** (D-061): its hash, matched exactly, every
  account it ever had, an erased one included (D-500); never a part of one.
  The audit row says how staff searched, never the number.
- **The whole number is an admin's alone** (D-927), each view audited; a
  moderator sees it masked; an erased account has none.
- **Never a selfie or the face photo** (D-925), and never the system user (D-905).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import PhotoKind, ReportReason, ReviewStatus, Role, UserStatus
from app.core.security import decrypt_phone
from app.modules.account import service as account_service
from app.modules.admin.service import SYSTEM_USER_ID
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile
from app.modules.safety.models import Report
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.admin.support import ADMIN, audits, auth, error, staff

pytestmark = pytest.mark.usefixtures("test_redis")

USERS = f"{ADMIN}/users"


async def _phone(make_user: MakeUser) -> tuple[uuid.UUID, str]:
    man, _ = await make_user()
    assert man.phone_enc is not None
    return man.id, decrypt_phone(man.phone_enc, make_test_settings())


async def _search(client: AsyncClient, token: str, q: str) -> list[str]:
    response = await client.get(USERS, params={"q": q}, headers=auth(token))
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


async def test_a_whole_number_finds_its_account_however_it_is_typed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    man_id, phone = await _phone(make_user)
    local = phone.removeprefix("+91")

    for typed in (phone, local, f"0{local}", f"{local[:5]} {local[5:]}"):
        assert await _search(client, token, typed) == [str(man_id)], typed
    entries = await audits(db, moderator_id, "users.search")
    assert {str(entry.meta) for entry in entries} == {str({"by": "phone"})}
    assert all(local[-4:] not in str(entry.meta) for entry in entries)


async def test_part_of_a_number_finds_nobody(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """'Whose number ends in 4321?' has no answer, by design (D-061)."""
    _, token = await staff(make_user, Role.MODERATOR)
    _, phone = await _phone(make_user)

    assert await _search(client, token, phone[-4:]) == []
    # One digit short: it looks like a number, and isn't a whole one.
    response = await client.get(USERS, params={"q": phone[:-1]}, headers=auth(token))
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_an_erased_account_is_still_found_by_its_number(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """T-9.6, D-500: the erased row keeps its hash, so support sees it as erased."""
    _, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    assert man.phone_enc is not None
    man_id, phone = man.id, decrypt_phone(man.phone_enc, make_test_settings())
    man.status = UserStatus.DELETED
    man.deleted_requested_at = clock.now() - timedelta(days=30)
    await db.flush()
    await account_service.anonymise(db, man)
    await db.flush()

    response = await client.get(USERS, params={"q": phone}, headers=auth(token))

    [item] = response.json()["items"]
    assert (item["id"], item["erased"], item["status"]) == (
        str(man_id),
        True,
        "deleted",
    )


async def test_a_username_or_first_name_finds_by_its_start_wildcards_as_characters(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    other, _ = await make_user()
    profile = await db.get(Profile, man.id)
    other_profile = await db.get(Profile, other.id)
    assert profile is not None and other_profile is not None
    profile.username, profile.first_name = "ravi_k", "Ravinder"
    other_profile.username, other_profile.first_name = "ravixk", "Arjun"
    await db.flush()
    man_id, other_id = man.id, other.id

    assert await _search(client, token, "@ravi_") == [str(man_id)]
    assert await _search(client, token, "Ravin") == [str(man_id)]
    assert set(await _search(client, token, "ravi")) == {str(man_id), str(other_id)}
    assert await _search(client, token, str(other_id)) == [str(other_id)]


async def test_the_system_user_is_never_listed_nor_read(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)

    assert await _search(client, token, str(SYSTEM_USER_ID)) == []
    response = await client.get(f"{USERS}/{SYSTEM_USER_ID}", headers=auth(token))
    assert response.status_code == 404


async def test_the_newest_accounts_a_page_at_a_time(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)
    for _ in range(2):
        await make_user()

    first = await client.get(USERS, params={"limit": 1}, headers=auth(token))
    second = await client.get(
        USERS,
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
        headers=auth(token),
    )

    assert len(first.json()["items"]) == 1 and len(second.json()["items"]) == 1
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]


@pytest.mark.parametrize("q", ["a", "x" * 51, "@"])
async def test_a_search_out_of_shape_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, q: str
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)

    response = await client.get(USERS, params={"q": q}, headers=auth(token))

    assert response.status_code == 400
    assert await audits(db, moderator_id) == []


# --- The detail ------------------------------------------------------------------------


async def test_an_admin_sees_the_whole_number_and_the_view_is_audited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    man_id, phone = await _phone(make_user)

    response = await client.get(f"{USERS}/{man_id}", headers=auth(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["phone"], body["phone_masked"]) == (phone, False)
    [entry] = await audits(db, admin_id, "user.read")
    assert (entry.target_id, entry.meta) == (man_id, {"phone_shown": True})


async def test_a_moderator_sees_it_masked(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    man_id, phone = await _phone(make_user)

    body = (await client.get(f"{USERS}/{man_id}", headers=auth(token))).json()

    assert body["phone"] == phone[:3] + "*" * (len(phone) - 7) + phone[-4:]
    assert body["phone_masked"] is True
    [entry] = await audits(db, moderator_id, "user.read")
    assert entry.meta == {"phone_shown": False}


async def test_the_detail_holds_photos_reports_ledger_and_threads_never_a_selfie(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user(credits=7)
    woman, _ = await make_user("female")
    man_id, woman_id = man.id, woman.id
    for kind in PhotoKind:
        photo_id = uuid.uuid4()
        db.add(
            Photo(
                id=photo_id,
                user_id=man_id,
                kind=kind,
                position=0 if kind is PhotoKind.PUBLIC else None,
                raw_key=f"raw/{man_id}/{photo_id}",
                status=ReviewStatus.PENDING,
            )
        )
    db.add(
        Report(
            reporter_id=woman_id,
            reported_id=man_id,
            reason=ReportReason.SCAM,
            details="Asked for money.",
        )
    )
    thread = await make_thread(man, woman, messages=2)
    thread_id = thread.id
    await db.flush()

    body = (await client.get(f"{USERS}/{man_id}", headers=auth(token))).json()

    assert sorted(p["kind"] for p in body["photos"]) == ["private", "public"]
    assert [r["reporter"]["id"] for r in body["reports_about"]] == [str(woman_id)]
    assert body["reports_by"] == []
    [grant] = body["ledger"]
    assert (grant["reason"], grant["delta"], grant["ref_type"]) == (
        "admin_grant",
        7,
        "audit_log",
    )
    assert body["balance"] == 7
    [listed] = body["threads"]
    assert (listed["id"], listed["other"]["id"], listed["message_count"]) == (
        str(thread_id),
        str(woman_id),
        2,
    )
    assert body["ban"] is None and body["fraud"] is None


async def test_an_erased_account_has_no_number_to_show(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id
    man.status = UserStatus.DELETED
    man.deleted_requested_at = clock.now() - timedelta(days=30)
    await db.flush()
    await account_service.anonymise(db, man)
    await db.flush()

    body = (await client.get(f"{USERS}/{man_id}", headers=auth(token))).json()

    assert (body["phone"], body["phone_masked"], body["user"]["erased"]) == (
        None,
        False,
        True,
    )
    [entry] = await audits(db, admin_id, "user.read")
    assert entry.meta == {"phone_shown": False}


async def test_an_unknown_account_is_not_found_and_unwritten(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)

    response = await client.get(f"{USERS}/{uuid.uuid4()}", headers=auth(token))

    assert response.status_code == 404
    assert await audits(db, admin_id) == []


async def test_the_admins_own_account_reads_like_any_other(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)

    response = await client.get(f"{USERS}/{admin_id}", headers=auth(token))

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    assert (await db.get(User, admin_id)) is not None
