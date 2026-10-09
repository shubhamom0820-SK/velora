"""Welcome Velas (T-8.11, D-470, D-530): finishing sign-up gives a man
`app_config.welcome_velas` of them, through the wallet, once per phone number,
ever. A woman, an amount of 0, a missing row and a number already given its
welcome each skip the grant, and none of them fails a sign-up.

Every test here runs in the `db` fixture's rolled-back transaction: a
committed `welcome` row could never be deleted, and would stop the reason's
downgrade for every later test (tests/committed.py). So the overlap of two
completions is forced inside it, T-8.1's way: the second runs whole while the
first is inside its grant.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import IST
from app.core.enums import Gender, OnboardingStep, Role
from app.core.providers.storage import FakeStorage
from app.core.security import E164, decrypt_phone, make_access_token
from app.modules.account import service as account_service
from app.modules.admin import service as admin_service
from app.modules.onboarding import repository as onboarding_repository
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.infra import ActiveSession
from tests.modules.onboarding.test_complete import _at_selfie, _complete, _ready
from tests.modules.photos.test_moderate import Sessions

pytestmark = pytest.mark.usefixtures("test_redis")

SETTINGS = make_test_settings()
NOW = datetime(2026, 10, 8, 6, 30, tzinfo=IST)
RESTRICT_VIOLATION = "23001"


def _phone(user: User) -> E164:
    """The number, as sign-in would type it again: never an erased row's."""
    assert user.phone_enc is not None
    return decrypt_phone(user.phone_enc, SETTINGS)


async def _welcome_rows(db: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = await db.execute(
        text(
            "select reason::text, delta, balance_after, ref_type, ref_id, "
            "idempotency_key from ledger_entries where user_id = :u order by id"
        ),
        {"u": user_id},
    )
    return [dict(row._mapping) for row in rows]


async def _grants(db: AsyncSession, phone_hash: str) -> list[uuid.UUID]:
    rows = await db.scalars(
        text("select user_id from welcome_grants where phone_hash = :h"),
        {"h": phone_hash},
    )
    return list(rows)


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    balance = await db.scalar(
        text("select balance from wallets where user_id = :u"), {"u": user_id}
    )
    assert balance is not None
    return int(balance)


async def _set_welcome(db: AsyncSession, value: str | None) -> None:
    """`app_config.welcome_velas` as JSON text, or no row at all."""
    if value is None:
        await db.execute(text("delete from app_config where key = 'welcome_velas'"))
    else:
        await db.execute(
            text(
                "update app_config set value = cast(:v as jsonb) where key = 'welcome_velas'"
            ),
            {"v": value},
        )


# --- Who gets them ---------------------------------------------------------------


@pytest.mark.critical  # D-470: money, through the wallet only (rule 5)
async def test_a_man_finishing_gets_five_velas_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token, man_id = await _at_selfie(db, make_user, Gender.MALE)
    phone_hash = man.phone_hash

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    assert (response.json()["onboarding_step"], response.json()["balance"]) == (
        "done",
        5,
    )
    assert await _balance(db, man_id) == 5
    assert await _welcome_rows(db, man_id) == [
        {
            "reason": "welcome",
            "delta": 5,
            "balance_after": 5,
            "ref_type": "user",
            "ref_id": man_id,
            "idempotency_key": f"{man_id}:welcome:{man_id}",
        }
    ]
    assert await _grants(db, phone_hash) == [man_id]


@pytest.mark.critical  # D-076: never a woman, and her sign-up still completes
async def test_a_woman_finishing_gets_nothing_and_finishes(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    woman, token, woman_id = await _at_selfie(
        db, make_user, Gender.FEMALE, verified=True
    )
    phone_hash = woman.phone_hash

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    assert (response.json()["onboarding_step"], response.json()["balance"]) == (
        "done",
        0,
    )
    assert await _welcome_rows(db, woman_id) == []
    assert await _grants(db, phone_hash) == []


async def test_done_twice_is_one_grant(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, man_id = await _at_selfie(db, make_user, Gender.MALE)

    first = await _complete(client, token)
    second = await _complete(client, token)

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["balance"] == 5
    assert [row["reason"] for row in await _welcome_rows(db, man_id)] == ["welcome"]


@pytest.mark.critical  # D-470: two completions at once are one grant
async def test_two_completions_overlapping_are_one_grant(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The overlap forced, not hoped for: the first completion has moved the
    step in memory, not yet written it, and is reading the amount when the
    second runs from start to finish. The second finds the step still at
    `selfie`, so both reach the claim: the second claims the number and is
    credited; the first finds it claimed, and credits nothing."""
    man, token, man_id = await _at_selfie(db, make_user, Gender.MALE)
    phone_hash = man.phone_hash
    config_int = admin_service.config_int
    claim = onboarding_repository.claim_welcome
    inner: list[Response] = []
    claims: list[bool] = []
    overtaking = False

    async def overtaken(session: AsyncSession, key: str, **kwargs: Any) -> int:
        nonlocal overtaking
        if key == "welcome_velas" and not overtaking:
            overtaking = True  # the second runs once, inside the first
            inner.append(await _beside(session, _complete(client, token)))
        return await config_int(session, key, **kwargs)

    async def recorded(session: AsyncSession, phone: str, user_id: uuid.UUID) -> bool:
        claimed = await claim(session, phone, user_id)
        claims.append(claimed)
        return claimed

    monkeypatch.setattr(admin_service, "config_int", overtaken)
    monkeypatch.setattr(onboarding_repository, "claim_welcome", recorded)

    outer = await _complete(client, token)

    [overtaker] = inner
    assert overtaker.status_code == outer.status_code == 200
    assert claims == [True, False]  # both reached the claim: the overlap
    assert outer.json()["balance"] == overtaker.json()["balance"] == 5
    assert [row["reason"] for row in await _welcome_rows(db, man_id)] == ["welcome"]
    assert await _grants(db, phone_hash) == [man_id]


async def _beside(session: AsyncSession, request: Awaitable[Response]) -> Response:
    """`request` on a session of its own, as a second request has, on the test's
    one connection: the app's stand-in hands every request the `db` session,
    and ending its open transaction would end the first request's too."""
    second = AsyncSession(
        bind=await session.connection(),
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    held, ActiveSession.session = ActiveSession.session, second
    try:
        return await request
    finally:
        ActiveSession.session = held
        await second.close()


# --- How many: app_config ----------------------------------------------------------


async def test_welcome_velas_at_zero_gives_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token, man_id = await _at_selfie(db, make_user, Gender.MALE)
    phone_hash = man.phone_hash
    await _set_welcome(db, "0")

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == "done"
    assert await _welcome_rows(db, man_id) == []
    # The number received nothing, so it hasn't had its welcome.
    assert await _grants(db, phone_hash) == []


async def test_welcome_velas_tuned_gives_that_many(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, man_id = await _at_selfie(db, make_user, Gender.MALE)
    await _set_welcome(db, "8")

    response = await _complete(client, token)

    assert response.json()["balance"] == 8
    assert [row["delta"] for row in await _welcome_rows(db, man_id)] == [8]


@pytest.mark.parametrize(
    ("value", "event"),
    [
        (None, "onboarding.welcome_config_missing"),
        ("-5", "onboarding.welcome_config_negative"),
        ('"five"', "onboarding.welcome_config_missing"),
    ],
    ids=["no row", "negative", "not a number"],
)
async def test_a_missing_or_broken_setting_skips_with_a_warning_and_never_fails_sign_up(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
    value: str | None,
    event: str,
) -> None:
    """D-530: a lost row grants nobody, and says so at warning, so someone can
    notice; `tests/test_reference_data.py` holds the migrated database to it."""
    man, token, man_id = await _at_selfie(db, make_user, Gender.MALE)
    phone_hash = man.phone_hash
    await _set_welcome(db, value)

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == "done"
    assert await _welcome_rows(db, man_id) == []
    assert await _grants(db, phone_hash) == []
    [line] = [e for e in captured_logs.events if e["event"] == event]
    assert line["log_level"] == "warning"
    assert line["user_id"] == str(man_id)
    assert line["key"] == "welcome_velas"


# --- Once per number, ever (P-371) -----------------------------------------------


@pytest.mark.critical  # P-371: deleting and signing up again is no second welcome
async def test_grant_delete_wait_out_the_erasure_sign_up_again_is_no_second_grant(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    """Through T-9.6's real erasure: the first account is deleted, erased 30
    days on by `erase_due_accounts`, and the number signs up again as sign-in
    does, a new account. It finishes, and gets nothing."""
    clock.freeze(NOW - timedelta(days=30))
    first, token, first_id = await _at_selfie(db, make_user, Gender.MALE)
    phone = _phone(first)
    phone_hash = first.phone_hash
    assert (await _complete(client, token)).json()["balance"] == 5
    deleted = await client.delete(
        "/v1/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert deleted.status_code == 202, deleted.text

    clock.freeze(NOW)
    erased = await account_service.erase_due_accounts(
        Sessions(db),
        storage=FakeStorage(),
        settings=SETTINGS,
    )
    assert erased == 1
    assert await db.scalar(
        text("select anonymised_at is not null from users where id = :u"),
        {"u": first_id},
    )

    again, created = await users_service.find_or_create_account(db, phone, SETTINGS)
    assert created and again.id != first_id
    again_id = again.id
    await _signed_up_as_a_man(db, again)
    response = await _complete(client, _token(again))

    assert response.status_code == 200, response.text
    assert (response.json()["onboarding_step"], response.json()["balance"]) == (
        "done",
        0,
    )
    assert await _welcome_rows(db, again_id) == []
    assert await _grants(db, phone_hash) == [first_id]
    [line] = [
        e
        for e in captured_logs.events
        if e["event"] == "onboarding.welcome_already_given"
    ]
    assert line["user_id"] == str(again_id)
    # The first account's welcome is kept with its ledger (rule 12, D-503).
    assert [row["reason"] for row in await _welcome_rows(db, first_id)] == ["welcome"]


async def _signed_up_as_a_man(db: AsyncSession, user: User) -> None:
    """A new account through the screens to `selfie`, as `make_user` makes one."""
    user.gender = Gender.MALE
    user.dob = (NOW - timedelta(days=25 * 366)).date()
    user.role = Role.USER
    await db.flush()
    await _ready(db, user, step=OnboardingStep.SELFIE)


def _token(user: User) -> str:
    return make_access_token(user.id, user.role, SETTINGS, auth_time=NOW)


async def test_a_number_already_claimed_gets_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The claim alone, whoever made it: the number's hash in the table is
    enough, whatever account it names."""
    other, _ = await make_user(Gender.MALE)
    man, token, man_id = await _at_selfie(db, make_user, Gender.MALE)
    await db.execute(
        text("insert into welcome_grants (phone_hash, user_id) values (:h, :u)"),
        {"h": man.phone_hash, "u": other.id},
    )

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 0
    assert await _welcome_rows(db, man_id) == []


async def test_nothing_logged_names_the_number_or_its_hash(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
) -> None:
    """Rule 15: the grant's lines name the user, never the number."""
    man, token, _ = await _at_selfie(db, make_user, Gender.MALE)
    phone = _phone(man)
    phone_hash = man.phone_hash

    await _complete(client, token)
    await _complete(client, token)

    assert "wallet.applied" in captured_logs.text
    assert phone_hash not in captured_logs.text
    assert phone not in captured_logs.text
    assert phone.removeprefix("+91") not in captured_logs.text
    captured_logs.assert_listening()


# --- The table keeps every number ---------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "update welcome_grants set phone_hash = phone_hash",
        "delete from welcome_grants",
        "truncate welcome_grants",
    ],
    ids=["update", "delete", "truncate"],
)
async def test_a_welcome_once_recorded_is_never_changed_or_removed(
    db: AsyncSession, make_user: MakeUser, statement: str
) -> None:
    man, _ = await make_user(Gender.MALE)
    await db.execute(
        text("insert into welcome_grants (phone_hash, user_id) values (:h, :u)"),
        {"h": man.phone_hash, "u": man.id},
    )

    with pytest.raises(DBAPIError) as refused:
        async with db.begin_nested():
            await db.execute(text(statement))

    orig = refused.value.orig
    assert getattr(orig, "sqlstate", None) == RESTRICT_VIOLATION, str(orig)
    assert "on welcome_grants is not allowed" in str(orig)
