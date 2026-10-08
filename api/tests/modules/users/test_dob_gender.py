"""`POST /v1/me/dob` and `POST /v1/me/gender` (T-3.6): the 18+ gate in IST,
D-072's deletion of an under-18 account keeping only the number's hash, both
fields set once (D-068, T-1.9's trigger behind the service), and D-068's step
rule as these two steps follow it."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.core import clock as clock_module
from app.core.enums import BanKind, Gender, OnboardingStep, PhotoKind, ReviewStatus
from app.core.errors import AppError
from app.core.providers import FakeProviders
from app.core.queue import DELETE_FILES, FakeQueue
from app.core.security import E164, hash_phone, make_access_token
from app.modules.auth import service as auth_service
from app.modules.auth.models import BannedIdentity, Session
from app.modules.notifications.models import NotificationPrefs
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.users import repository as users_repository
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.verification.models import Verification
from app.modules.wallet.models import Wallet
from app.workers.tasks import delete_files as delete_files_job
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.workers.test_delete_files import SharedSession

pytestmark = pytest.mark.usefixtures("test_redis")

SETTINGS = make_test_settings()
PHONE = E164("+919812345601")
# 06:30 UTC is 12:00 in IST: the same date in both, away from either midnight.
NOON_IST = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)
TODAY = date(2026, 10, 3)

NewAccount = Callable[..., Awaitable[tuple[User, str]]]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _count(db: AsyncSession, model: type[Any], **where: Any) -> int:
    query = select(func.count()).select_from(model)
    for column, value in where.items():
        query = query.where(getattr(model, column) == value)
    return int(await db.scalar(query) or 0)


@pytest.fixture
def new_account(db: AsyncSession) -> NewAccount:
    """An account as sign-in leaves it, at the dob step unless told otherwise,
    and an access token for it."""

    async def factory(
        phone: E164 = PHONE, step: OnboardingStep = OnboardingStep.DOB
    ) -> tuple[User, str]:
        account = await users_service.create_account(db, phone, SETTINGS)
        user = account.user
        user.onboarding_step = step
        await db.flush()
        token = make_access_token(
            user.id, user.role, SETTINGS, auth_time=clock_module.now()
        )
        return user, token

    return factory


async def _post_dob(client: AsyncClient, token: str, dob: object) -> Response:
    return await client.post("/v1/me/dob", json={"dob": dob}, headers=_bearer(token))


async def _post_gender(client: AsyncClient, token: str, gender: str) -> Response:
    return await client.post(
        "/v1/me/gender", json={"gender": gender}, headers=_bearer(token)
    )


class Device:
    """A browser after a real sign-in by OTP: its access token and the two
    cookies, sent back as it would send them."""

    def __init__(self, signed_in: Response) -> None:
        self.token = ""
        self.refresh = ""
        self.csrf = ""
        self.take(signed_in)

    def take(self, response: Response) -> None:
        self.token = response.json()["access_token"]
        for header in response.headers.get_list("set-cookie"):
            name, _, value = header.split(";")[0].partition("=")
            if name == "refresh_local":
                self.refresh = value
            elif name == "csrf_local":
                self.csrf = value

    async def refreshed(self, client: AsyncClient) -> Response:
        return await client.post(
            "/v1/auth/refresh",
            headers={
                "Cookie": f"refresh_local={self.refresh}; csrf_local={self.csrf}",
                "X-CSRF": self.csrf,
            },
        )


async def _signed_in(
    client: AsyncClient, fake_providers: FakeProviders, phone: E164 = PHONE
) -> Device:
    typed = phone.removeprefix("+91")
    sent = await client.post("/v1/auth/otp/send", json={"phone": typed})
    assert sent.status_code == 200
    verified = await client.post(
        "/v1/auth/otp/verify",
        json={"phone": typed, "otp": fake_providers.sms.sent[-1].code},
    )
    assert verified.status_code == 200
    return Device(verified)


# --- The date of birth ------------------------------------------------------------


async def test_a_dob_at_its_step_is_set_and_moves_on_to_gender(
    db: AsyncSession, client: AsyncClient, new_account: NewAccount, clock: ModuleType
) -> None:
    clock.freeze(NOON_IST)
    user, token = await new_account()

    response = await _post_dob(client, token, "1998-06-01")

    assert response.status_code == 200
    me = response.json()
    assert me["onboarding_step"] == "gender"
    assert me["age"] == 28
    assert "dob" not in response.text
    await db.refresh(user)
    assert user.dob == date(1998, 6, 1)
    assert user.onboarding_step is OnboardingStep.GENDER


@pytest.mark.critical
async def test_exactly_eighteen_today_is_accepted(
    db: AsyncSession, client: AsyncClient, new_account: NewAccount, clock: ModuleType
) -> None:
    clock.freeze(NOON_IST)
    user, token = await new_account()

    response = await _post_dob(client, token, "2008-10-03")

    assert response.status_code == 200
    assert response.json()["age"] == 18
    assert await _count(db, User, id=user.id) == 1
    assert await _count(db, BannedIdentity) == 0


@pytest.mark.critical
async def test_under_eighteen_deletes_the_account_and_keeps_only_the_hash(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """🔒 7 (D-072): 17 years and 364 days. Signed in for real, so a session
    and both cookies exist; afterwards nothing is left but the hash."""
    clock.freeze(NOON_IST)
    device = await _signed_in(client, fake_providers)
    user = await db.scalar(select(User).where(User.phone_hash == _phone_hash()))
    assert user is not None
    user_id = user.id
    attached: tuple[type[Any], ...] = (Session, Profile, Wallet, NotificationPrefs)
    for model in attached:
        assert await _count(db, model, user_id=user_id) == 1, model.__tablename__

    response = await _post_dob(client, device.token, "2008-10-04")

    assert response.status_code == 422
    assert _error(response)["code"] == "UNDERAGE"
    assert await _count(db, User, id=user_id) == 0
    everything: tuple[type[Any], ...] = (*attached, ProfileIntent, ProfileInterest)
    for model in everything:
        assert await _count(db, model, user_id=user_id) == 0, model.__tablename__
    assert await _count(db, User, phone_hash=_phone_hash()) == 0
    bans = (await db.scalars(select(BannedIdentity))).all()
    assert [(b.kind, b.value, b.reason) for b in bans] == [
        (BanKind.PHONE_HASH, _phone_hash(), "underage")
    ]


async def test_after_underage_the_token_refresh_and_number_all_fail(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON_IST)
    device = await _signed_in(client, fake_providers)
    # Both work beforehand, so what fails afterwards fails for the deletion.
    assert (
        await client.get("/v1/me", headers=_bearer(device.token))
    ).status_code == 200
    rotated = await device.refreshed(client)
    assert rotated.status_code == 200
    device.take(rotated)

    assert (await _post_dob(client, device.token, "2010-01-01")).status_code == 422

    me = await client.get("/v1/me", headers=_bearer(device.token))
    refreshed = await device.refreshed(client)
    assert me.status_code == 401 and _error(me)["code"] == "AUTH_REQUIRED"
    assert refreshed.status_code == 401
    assert _error(refreshed)["code"] == "AUTH_REQUIRED"
    # The number, proven by any path, can't sign up again (D-009).
    with pytest.raises(AppError) as refused:
        await auth_service.sign_in(db, SETTINGS, PHONE)
    assert refused.value.code == "ACCOUNT_BANNED"
    assert await _count(db, User, phone_hash=_phone_hash()) == 0


async def test_age_is_counted_in_ist_not_utc(
    client: AsyncClient, new_account: NewAccount, clock: ModuleType
) -> None:
    """Born 4 October 2008. At 19:00 UTC on the 3rd it is already the 4th in
    India: eighteen. Half an hour before midnight IST, seventeen."""
    clock.freeze(datetime(2026, 10, 3, 19, 0, tzinfo=UTC))
    _, eighteen = await new_account(phone=E164("+919812345602"))
    accepted = await _post_dob(client, eighteen, "2008-10-04")

    clock.freeze(datetime(2026, 10, 3, 18, 0, tzinfo=UTC))
    _, seventeen = await new_account(phone=E164("+919812345603"))
    refused = await _post_dob(client, seventeen, "2008-10-04")

    assert accepted.status_code == 200, accepted.text
    assert refused.status_code == 422
    assert _error(refused)["code"] == "UNDERAGE"


@pytest.mark.parametrize(
    ("dob", "problem"),
    [
        ("2026-10-04", "is in the future"),
        ("1925-10-02", "is more than 100 years ago"),
    ],
    ids=["tomorrow", "100 years and a day ago"],
)
async def test_a_dob_no_person_could_have_is_a_validation_error(
    db: AsyncSession,
    client: AsyncClient,
    new_account: NewAccount,
    clock: ModuleType,
    dob: str,
    problem: str,
) -> None:
    clock.freeze(NOON_IST)
    user, token = await new_account()

    response = await _post_dob(client, token, dob)

    assert response.status_code == 400
    assert _error(response) == {
        "code": "VALIDATION_ERROR",
        "message": "Some of the information sent was not valid.",
        "details": {"fields": [{"field": "dob", "problem": problem}]},
    }
    await db.refresh(user)
    assert user.dob is None and user.onboarding_step is OnboardingStep.DOB
    assert await _count(db, BannedIdentity) == 0


async def test_a_hundred_years_ago_to_the_day_is_accepted(
    client: AsyncClient, new_account: NewAccount, clock: ModuleType
) -> None:
    clock.freeze(NOON_IST)
    _, token = await new_account()

    response = await _post_dob(client, token, "1926-10-03")

    assert response.status_code == 200
    assert response.json()["age"] == 100


async def test_one_hundred_and_one_years_ago_is_refused(
    client: AsyncClient, new_account: NewAccount, clock: ModuleType
) -> None:
    clock.freeze(NOON_IST)
    _, token = await new_account()

    response = await _post_dob(client, token, "1925-10-03")

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "dob",
    [946684800, "946684800", "2000-01-01T00:00:00", "01/01/2000", "2000-02-30", None],
    ids=["a number", "digits", "a datetime", "another format", "no such day", "null"],
)
async def test_a_dob_not_written_as_a_date_is_refused_before_the_service(
    db: AsyncSession, client: AsyncClient, new_account: NewAccount, dob: object
) -> None:
    """A number would otherwise be read as a Unix timestamp, in UTC."""
    user, token = await new_account()

    response = await _post_dob(client, token, dob)

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"
    assert _error(response)["details"]["fields"][0]["field"] == "dob"
    await db.refresh(user)
    assert user.dob is None


@pytest.mark.parametrize("step", [OnboardingStep.GENDER, OnboardingStep.DONE])
async def test_a_dob_already_set_is_immutable(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token = await make_user(onboarded=step is OnboardingStep.DONE)
    user.onboarding_step = step
    await db.flush()
    before = user.dob
    assert before is not None

    for dob in ("1990-01-01", before.isoformat()):
        response = await _post_dob(client, token, dob)
        assert response.status_code == 422
        assert _error(response)["code"] == "IMMUTABLE_FIELD"
    await db.refresh(user)
    assert user.dob == before and user.onboarding_step is step


# --- Gender -------------------------------------------------------------------------


async def test_gender_at_its_step_is_set_and_moves_on_to_seeking(
    db: AsyncSession, client: AsyncClient, new_account: NewAccount
) -> None:
    user, token = await new_account(step=OnboardingStep.GENDER)

    response = await _post_gender(client, token, "female")

    assert response.status_code == 200
    assert response.json()["gender"] == "female"
    assert response.json()["onboarding_step"] == "seeking"
    await db.refresh(user)
    assert user.gender is Gender.FEMALE


async def test_gender_before_its_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, new_account: NewAccount
) -> None:
    user, token = await new_account()

    response = await _post_gender(client, token, "male")

    assert response.status_code == 403
    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"
    assert _error(response)["details"] == {"step": "dob"}
    await db.refresh(user)
    assert user.gender is None and user.onboarding_step is OnboardingStep.DOB


@pytest.mark.critical
@pytest.mark.parametrize("again", ["female", "male"], ids=["the other", "the same"])
async def test_a_second_gender_is_immutable(
    db: AsyncSession, client: AsyncClient, new_account: NewAccount, again: str
) -> None:
    """🔒 8: the service refuses a second set, whatever it says."""
    user, token = await new_account(step=OnboardingStep.GENDER)
    assert (await _post_gender(client, token, "male")).status_code == 200

    response = await _post_gender(client, token, again)

    assert response.status_code == 422
    assert _error(response)["code"] == "IMMUTABLE_FIELD"
    await db.refresh(user)
    assert user.gender is Gender.MALE
    assert user.onboarding_step is OnboardingStep.SEEKING


@pytest.mark.critical
@pytest.mark.parametrize("field", ["gender", "dob"])
async def test_the_trigger_refuses_a_change_the_service_lets_through(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    """🔒 8: with the service's own check gone, T-1.9's trigger still refuses
    the change, and its SQLSTATE becomes `IMMUTABLE_FIELD`, not a 500."""
    user, token = await make_user(onboarded=False)
    real = users_service.locked_user

    async def forgetful(session: AsyncSession, user_id: Any) -> User:
        locked = await real(session, user_id)
        # As if the service had read the field unset: the row still has it.
        set_committed_value(locked, field, None)
        return locked

    monkeypatch.setattr(users_service, "locked_user", forgetful)
    response = (
        await _post_gender(client, token, "female")
        if field == "gender"
        else await _post_dob(client, token, "1990-01-01")
    )

    assert response.status_code == 422, response.text
    assert _error(response)["code"] == "IMMUTABLE_FIELD"
    monkeypatch.undo()
    await db.refresh(user)
    assert user.gender is Gender.MALE
    assert user.dob is not None and user.dob.year != 1990


class _Orig(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("users.gender is immutable once set")
        self.sqlstate = sqlstate


def _integrity_error(sqlstate: str) -> IntegrityError:
    return IntegrityError("UPDATE users ...", {}, _Orig(sqlstate))


async def test_only_the_sqlstate_maps_to_immutable_never_the_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """23514 is `IMMUTABLE_FIELD` whatever the message says; the trigger's own
    words under any other SQLSTATE are not."""

    class Flushing:
        def __init__(self, error: IntegrityError) -> None:
            self.error = error

        async def flush(self) -> None:
            raise self.error

    with pytest.raises(AppError) as mapped:
        await users_service._flush_identity(Flushing(_integrity_error("23514")))  # type: ignore[arg-type]
    assert mapped.value.code == "IMMUTABLE_FIELD"

    unique = _integrity_error("23505")
    with pytest.raises(IntegrityError) as passed_on:
        await users_service._flush_identity(Flushing(unique))  # type: ignore[arg-type]
    assert passed_on.value is unique


# --- D-072's deletion: exactly these tables, and never more ---------------------------


async def _d072_problems(db: AsyncSession) -> list[str]:
    """Every way the tables keyed to `users`, read from the database, fail to
    match D-072's two lists exactly."""
    rows = await db.execute(
        text(
            """
            select c.conrelid::regclass::text, c.confdeltype::text
            from pg_constraint c
            where c.contype = 'f' and c.confrelid = 'users'::regclass
            """
        )
    )
    keys = {(str(table), str(rule)) for table, rule in rows}
    keyed = {table for table, _ in keys}
    deleted = _deleted_tables()
    kept = set(users_repository.UNDERAGE_KEEPS)
    problems = []
    if unclassified := sorted(keyed - deleted - kept):
        problems.append(
            f"D-072: {unclassified} hold a key to users. Add each to "
            "UNDERAGE_DELETES (an under-18 refusal deletes its rows) or "
            "UNDERAGE_KEEPS (with why a user at the dob step can't have one), in "
            "api/app/modules/users/repository.py."
        )
    if both := sorted(deleted & kept):
        problems.append(f"D-072: {both} are both deleted and kept")
    if stale := sorted((deleted | kept) - keyed):
        problems.append(f"D-072: {stale} are listed but hold no key to users")
    if loose := sorted(t for t, rule in keys if t in kept and rule not in {"r", "a"}):
        problems.append(
            f"D-072: kept {loose} must be RESTRICT, or the deletion takes their "
            "rows with the account (rule 12)"
        )
    return problems


async def test_every_table_keyed_to_users_is_one_d072_deletes_or_one_it_keeps(
    db: AsyncSession,
) -> None:
    """Every table with a key to `users` is in exactly one of D-072's two
    lists, so a table added later fails here, naming D-072, until someone
    decides whether an under-18 refusal deletes its rows. Kept tables' keys
    are RESTRICT: a CASCADE or SET NULL would quietly take moderation or money
    records with an account (rule 12)."""
    assert await _d072_problems(db) == []


def _deleted_tables() -> set[str]:
    return {a.model.__tablename__ for a in users_repository.UNDERAGE_DELETES}


async def _keys(db: AsyncSession, parent: str) -> set[tuple[str, str]]:
    """Every (table, column) holding a key to `parent`, read from the database."""
    rows = await db.execute(
        text(
            """
            select c.conrelid::regclass::text, a.attname
            from pg_constraint c
            join pg_attribute a
              on a.attrelid = c.conrelid and a.attnum = any(c.conkey)
            where c.contype = 'f' and c.confrelid = cast(:parent as regclass)
            """
        ),
        {"parent": parent},
    )
    return {(str(table), str(column)) for table, column in rows}


async def test_each_deleted_table_names_exactly_its_columns_keyed_to_users(
    db: AsyncSession,
) -> None:
    """A column naming the user that the deletion doesn't check would leave
    that row, and the row would stop the deletion (D-078)."""
    keyed = await _keys(db, "users")
    listed = {
        a.model.__tablename__: set(a.columns) for a in users_repository.UNDERAGE_DELETES
    }

    assert {table: {c for t, c in keyed if t == table} for table in listed} == listed


async def test_every_deleted_table_keyed_to_threads_deletes_by_thread(
    db: AsyncSession,
) -> None:
    """Another user's row on the user's thread (their clear of it) names the
    thread, not the user; without it the thread can't be deleted."""
    on_threads = {t for t, _ in await _keys(db, "threads")} & _deleted_tables()

    assert {
        a.model.__tablename__ for a in users_repository.UNDERAGE_DELETES if a.on_threads
    } == on_threads


async def test_the_deletion_runs_in_the_order_of_the_keys_between_its_tables(
    db: AsyncSession,
) -> None:
    """A table is deleted from before any table it holds a key to: verifications
    before photos, a thread's children before the thread."""
    order = [a.model.__tablename__ for a in users_repository.UNDERAGE_DELETES]
    rows = await db.execute(
        text(
            """
            select c.conrelid::regclass::text, c.confrelid::regclass::text
            from pg_constraint c where c.contype = 'f'
            """
        )
    )
    edges = {(str(child), str(parent)) for child, parent in rows}
    inside = [(c, p) for c, p in edges if c in order and p in order and c != p]

    assert inside, "the check must have keys between deleted tables to check"
    assert [(c, p) for c, p in inside if order.index(c) > order.index(p)] == []


async def test_kept_is_exactly_what_the_app_role_cant_delete(db: AsyncSession) -> None:
    """D-078: the deletion takes every table the app role may delete from and
    keeps only rule 12's, which it can't (T-1.22): read from its grants."""
    keyed = {t for t, _ in await _keys(db, "users")}
    rows = await db.execute(
        text(
            "select t, has_table_privilege('velora_app', t, 'DELETE') "
            "from unnest(cast(:tables as text[])) as t"
        ),
        {"tables": sorted(keyed)},
    )
    deletable = {str(t): bool(can) for t, can in rows}

    assert {t for t, can in deletable.items() if not can} == set(
        users_repository.UNDERAGE_KEEPS
    )
    assert {t for t, can in deletable.items() if can} == _deleted_tables()


async def test_a_new_table_keyed_to_users_fails_until_d072_names_it(
    db: AsyncSession,
) -> None:
    """The check against the wrong thing: a table it has never seen. Created
    inside the test's transaction, so it is rolled back with it."""
    await db.execute(
        text("create table d072_probe (user_id uuid not null references users (id))")
    )

    problems = await _d072_problems(db)

    assert len(problems) == 1
    assert problems[0].startswith("D-072: ['d072_probe'] hold a key to users.")


async def test_a_kept_table_that_cascades_fails(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await db.execute(
        text(
            "create table d072_probe (user_id uuid not null "
            "references users (id) on delete cascade)"
        )
    )
    await db.execute(text("revoke all on d072_probe from velora_app"))
    monkeypatch.setitem(users_repository.UNDERAGE_KEEPS, "d072_probe", "a probe")

    assert await _d072_problems(db) == [
        (
            "D-072: kept ['d072_probe'] must be RESTRICT, or the deletion takes their "
            "rows with the account (rule 12)"
        )
    ]


async def test_a_row_the_deletion_doesnt_clear_stops_it_whole(
    db: AsyncSession,
    client: AsyncClient,
    new_account: NewAccount,
    make_user: MakeUser,
    clock: ModuleType,
) -> None:
    """If an under-18 account somehow has a row rule 12 keeps (a report about
    it), nothing is deleted and no hash is kept: a 500, never a half-deleted
    account, and the bug is in whatever wrote the row (D-078)."""
    clock.freeze(NOON_IST)
    user, token = await new_account()
    user_id = user.id
    reporter, _ = await make_user()
    await db.execute(
        text(
            "insert into reports (reporter_id, reported_id, reason) "
            "values (:r, :u, 'other')"
        ),
        {"r": reporter.id, "u": user_id},
    )
    await db.flush()

    response = await _post_dob(client, token, "2010-01-01")

    assert response.status_code == 500
    assert _error(response)["code"] == "INTERNAL"
    assert await _count(db, User, id=user_id) == 1
    assert await _count(db, Profile, user_id=user_id) == 1
    assert await _count(db, Wallet, user_id=user_id) == 1
    assert await _count(db, BannedIdentity) == 0


# Rows only a kept row can stand behind: an unlock is of a message, a refund
# request of a payment. Either means the deletion fails whole, as above.
BEHIND_A_KEPT_ROW = {"message_unlocks", "refund_requests"}


async def _a_row_naming_them_everywhere(
    db: AsyncSession, minor: uuid.UUID, other: uuid.UUID
) -> uuid.UUID:
    """A row in every deleted table that can hold one, naming `minor` in each
    of its columns that can; and `other`'s clear of their shared thread, which
    names only the thread. Returns the thread."""
    low, high = sorted((minor, other))
    thread = await db.scalar(
        text(
            "insert into threads (user_low, user_high, origin, opened_by, expires_at) "
            "values (:low, :high, 'match', :m, now() + interval '1 day') returning id"
        ),
        {"low": low, "high": high, "m": minor},
    )
    photo = await db.scalar(
        text(
            "insert into photos (user_id, kind, raw_key) "
            "values (:m, 'private', 'raw/probe') returning id"
        ),
        {"m": minor},
    )
    both_ways = [
        (
            "insert into kudos (from_id, to_id, kind, thread_id) "
            "values (:a, :b, 'great_conversation', :t)"
        ),
        "insert into gift_sends (sender_id, recipient_id, gift_id) values (:a, :b, 'coffee')",
        "insert into liked_you_reveals (viewer_id, liker_id) values (:a, :b)",
        "insert into swipes (swiper_id, target_id, dir) values (:a, :b, 'like')",
        (
            "insert into profile_views (viewer_id, viewed_id, last_viewed_at) "
            "values (:a, :b, now())"
        ),
        "insert into blocks (blocker_id, blocked_id) values (:a, :b)",
        "insert into album_requests (requester_id, owner_id) values (:a, :b)",
        "insert into referrals (referee_id, referrer_id) values (:a, :b)",
    ]
    for statement in both_ways:
        for a, b in ((minor, other), (other, minor)):
            await db.execute(text(statement), {"a": a, "b": b, "t": thread})
    theirs = [
        "insert into thread_clears (user_id, thread_id, cleared_at) values (:m, :t, now())",
        "insert into thread_clears (user_id, thread_id, cleared_at) values (:o, :t, now())",
        "insert into matches (user_low, user_high, thread_id) values (:low, :high, :t)",
        "insert into notifications (user_id, kind) values (:m, 'probe')",
        (
            "insert into push_subscriptions (user_id, endpoint, p256dh, auth) "
            "values (:m, 'https://push.invalid/probe', 'p', 'a')"
        ),
        "insert into fraud_events (user_id, signal, weight) values (:m, 'probe', 1)",
        "insert into fraud_scores (user_id) values (:m)",
        "insert into profile_intents (user_id, intent_id) values (:m, 1)",
        "insert into profile_interests (user_id, interest_id) values (:m, 1)",
        (
            "insert into sessions (user_id, family_id, token_hash, expires_at, "
            "auth_time) values (:m, gen_random_uuid(), 'probe', now(), now())"
        ),
        (
            "insert into verifications (user_id, challenge, selfie_photo_id) "
            "values (:m, 'smile', :p)"
        ),
    ]
    values = {"m": minor, "o": other, "t": thread, "p": photo, "low": low, "high": high}
    for statement in theirs:
        await db.execute(text(statement), values)
    await db.flush()
    assert isinstance(thread, uuid.UUID)
    return thread


async def _naming(db: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    """How many rows name `user_id`, by table, in every column keyed to users."""
    counts: dict[str, int] = {}
    for table, column in sorted(await _keys(db, "users")):
        found = await db.scalar(
            text(f"select count(*) from {table} where {column} = :u"), {"u": user_id}
        )
        if found:
            counts[table] = counts.get(table, 0) + int(found)
    return counts


@pytest.mark.critical
async def test_under_eighteen_deletes_every_row_in_every_table_the_app_may(
    db: AsyncSession,
    client: AsyncClient,
    new_account: NewAccount,
    make_user: MakeUser,
    clock: ModuleType,
) -> None:
    """🔒 7, with D-078: a row naming the minor in every table the deletion
    takes, in every column that can name them, and another user's clear of
    their shared thread. Afterwards no row anywhere names them, the other
    user is untouched, and only the number's hash is kept."""
    clock.freeze(NOON_IST)
    minor, token = await new_account()
    minor_id, minor_hash = minor.id, minor.phone_hash
    other, _ = await make_user()
    other_id = other.id
    thread = await _a_row_naming_them_everywhere(db, minor_id, other_id)
    # Every table it could fill, so "none left" below means something.
    assert set(await _naming(db, minor_id)) == _deleted_tables() - BEHIND_A_KEPT_ROW

    response = await _post_dob(client, token, "2010-01-01")

    assert _error(response)["code"] == "UNDERAGE"
    assert await _naming(db, minor_id) == {}
    assert await _count(db, User, id=minor_id) == 0
    left = await db.scalar(
        text("select count(*) from thread_clears where thread_id = :t"), {"t": thread}
    )
    assert left == 0
    assert await _count(db, User, id=other_id) == 1
    assert await _count(db, Profile, user_id=other_id) == 1
    bans = (await db.scalars(select(BannedIdentity))).all()
    assert [(b.value, b.reason) for b in bans] == [(minor_hash, "underage")]


async def test_deleting_an_account_that_isnt_there_is_an_error(
    db: AsyncSession,
) -> None:
    """`UNDERAGE` says the account was deleted, so a deletion that found no
    user must fail, never pass as one that did."""
    with pytest.raises(LookupError):
        await users_repository.delete_account(db, uuid.uuid4())


async def test_a_number_already_banned_keeps_its_one_row(
    db: AsyncSession, client: AsyncClient, new_account: NewAccount, clock: ModuleType
) -> None:
    clock.freeze(NOON_IST)
    _, token = await new_account()
    db.add(BannedIdentity(kind=BanKind.PHONE_HASH, value=_phone_hash(), reason="ban"))
    await db.flush()

    response = await _post_dob(client, token, "2010-01-01")

    assert _error(response)["code"] == "UNDERAGE"
    bans = (await db.scalars(select(BannedIdentity))).all()
    assert [(b.value, b.reason) for b in bans] == [(_phone_hash(), "ban")]
    assert await _count(db, User, phone_hash=_phone_hash()) == 0


# --- Rule 15 --------------------------------------------------------------------------


async def test_no_number_hash_token_or_key_reaches_a_log_or_the_body(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    clock.freeze(NOON_IST)
    minor = await _signed_in(client, fake_providers)
    adult_phone = E164("+919812345604")
    adult = await _signed_in(client, fake_providers, adult_phone)

    refused = await _post_dob(client, minor.token, "2009-01-01")
    accepted = await _post_dob(client, adult.token, "1999-01-01")
    gender = await _post_gender(client, adult.token, "male")

    assert refused.status_code == 422 and accepted.status_code == 200
    assert gender.status_code == 200
    responses = [refused, accepted, gender]
    seen = "\n".join([*(r.text for r in responses), captured_logs.text])
    secrets = [
        *(p for phone in (PHONE, adult_phone) for p in _ways_to_write(phone)),
        _phone_hash(),
        _phone_hash(adult_phone),
        minor.token,
        minor.refresh,
        adult.token,
        adult.refresh,
        SETTINGS.CODE_PEPPER,
        SETTINGS.PHONE_PEPPER,
        SETTINGS.JWT_SECRET,
        *SETTINGS.PHONE_ENC_KEY,
    ]
    assert [s for s in secrets if s in seen] == []
    captured_logs.assert_listening()


def _ways_to_write(phone: E164) -> list[str]:
    national = phone.removeprefix("+91")
    return [phone, national, f"{national[:5]} {national[5:]}"]


def _phone_hash(phone: E164 = PHONE) -> str:
    return hash_phone(phone, SETTINGS)


# --- D-078's file half, in D-090's order (T-4.2) ----------------------------------------

CHECK_FILES_AFTER = timedelta(seconds=60)


async def _photos_with_files(
    db: AsyncSession, fake_providers: FakeProviders, minor: uuid.UUID
) -> list[list[str]]:
    """Two photos, one approved with a public copy, each file in storage. A
    user at the dob step can't have them (D-068): this is the defence behind
    that rule, so it is tested with them there."""
    stored: list[list[str]] = []
    for position, public in ((0, True), (1, False)):
        photo_id = uuid.uuid4()
        raw = f"raw/{minor}/{photo_id}"
        public_key = f"p/{photo_id}.jpg" if public else None
        db.add(
            Photo(
                id=photo_id,
                user_id=minor,
                kind=PhotoKind.PUBLIC,
                position=position,
                raw_key=raw,
                public_key=public_key,
            )
        )
        await fake_providers.storage.put_bytes(
            "velora-private", raw, b"x", "image/jpeg"
        )
        stored.append(["velora-private", raw])
        if public_key:
            await fake_providers.storage.put_bytes(
                "velora-public", public_key, b"x", "image/jpeg"
            )
            stored.append(["velora-public", public_key])
    await db.flush()
    return sorted(stored)


@pytest.mark.critical
async def test_under_eighteen_queues_its_files_deletion_before_the_rows_go(
    db: AsyncSession,
    client: AsyncClient,
    new_account: NewAccount,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
    clock: ModuleType,
) -> None:
    """🔒 7, files included (D-078, D-090): the keys read before the rows go,
    the job queued with them, the refusal's record kept; and the job, run once
    the user is gone, takes every file and reads each back as gone."""
    clock.freeze(NOON_IST)
    minor, token = await new_account()
    minor_id = minor.id
    stored = await _photos_with_files(db, fake_providers, minor_id)

    response = await _post_dob(client, token, "2010-01-01")

    assert _error(response)["code"] == "UNDERAGE"
    assert await _count(db, Photo, user_id=minor_id) == 0
    ban = await db.scalar(select(BannedIdentity))
    assert ban is not None and ban.reason == "underage"
    [job] = fake_queue.named(DELETE_FILES)
    assert (job.job_id, job.defer_by) == (f"delete_files:{minor_id}", CHECK_FILES_AFTER)
    assert job.kwargs["user_id"] == str(minor_id)
    assert job.kwargs["banned_id"] == str(ban.id)
    assert sorted(job.kwargs["objects"]) == stored
    # Queued, not done: the files wait for the job.
    assert len(fake_providers.storage.objects) == len(stored)

    done = await delete_files_job.delete_files(
        {
            "sessionmaker": SharedSession(db),
            "storage": fake_providers.storage,
            "queue": fake_queue,
        },
        **job.kwargs,
    )

    assert done == "deleted"
    assert fake_providers.storage.objects == {}
    # The image goes; the record that a refusal happened stays (rule 12).
    assert await _count(db, BannedIdentity, id=ban.id) == 1


@pytest.mark.critical
async def test_a_refusal_whose_deletion_cant_be_queued_fails_whole(
    db: AsyncSession,
    client: AsyncClient,
    new_account: NewAccount,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
    clock: ModuleType,
) -> None:
    """D-090: queued before the commit, so a queue that refuses takes the
    refusal with it: nothing deleted, no file loses its row, no ban written."""
    clock.freeze(NOON_IST)
    minor, token = await new_account()
    minor_id = minor.id
    await _photos_with_files(db, fake_providers, minor_id)
    fake_queue.fail = True

    response = await _post_dob(client, token, "2010-01-01")

    assert response.status_code == 500
    assert await _count(db, User, id=minor_id) == 1
    assert await _count(db, Photo, user_id=minor_id) == 2
    assert await _count(db, BannedIdentity) == 0


@pytest.mark.critical
async def test_a_refusals_selfie_and_its_verification_go_with_it(
    db: AsyncSession,
    client: AsyncClient,
    new_account: NewAccount,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
    clock: ModuleType,
) -> None:
    """D-078, as T-4.5 inherits it: a selfie is a photo, so its key is read
    before the rows go and its file queued for deletion with the rest, and its
    verification goes with the user. (D-068 keeps a selfie from existing at
    the dob step; this is the defence behind that rule.)"""
    clock.freeze(NOON_IST)
    minor, token = await new_account()
    minor_id = minor.id
    selfie_id = uuid.uuid4()
    raw = f"raw/{minor_id}/{selfie_id}"
    db.add(Photo(id=selfie_id, user_id=minor_id, kind=PhotoKind.SELFIE, raw_key=raw))
    await db.flush()
    db.add(Verification(user_id=minor_id, challenge="none", selfie_photo_id=selfie_id))
    await db.flush()
    await fake_providers.storage.put_bytes("velora-private", raw, b"x", "image/jpeg")

    response = await _post_dob(client, token, "2010-01-01")

    assert _error(response)["code"] == "UNDERAGE"
    assert await _count(db, Verification, user_id=minor_id) == 0
    assert await _count(db, Photo, user_id=minor_id) == 0
    [job] = fake_queue.named(DELETE_FILES)
    assert job.kwargs["objects"] == [["velora-private", raw]]


@pytest.mark.critical
async def test_a_refusals_face_photo_goes_with_it(
    db: AsyncSession,
    client: AsyncClient,
    new_account: NewAccount,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
    clock: ModuleType,
) -> None:
    """D-078, as T-4.12 inherits it: the face photo is a photo row (kind
    `verification`), so its key is read before the rows go and its file queued
    for deletion with the rest (06-TESTING #14, extended)."""
    clock.freeze(NOON_IST)
    minor, token = await new_account()
    minor_id = minor.id
    face_id = uuid.uuid4()
    raw = f"raw/{minor_id}/{face_id}"
    db.add(
        Photo(
            id=face_id,
            user_id=minor_id,
            kind=PhotoKind.VERIFICATION,
            raw_key=raw,
            status=ReviewStatus.APPROVED,
        )
    )
    await db.flush()
    await fake_providers.storage.put_bytes("velora-private", raw, b"x", "image/jpeg")

    response = await _post_dob(client, token, "2010-01-01")

    assert _error(response)["code"] == "UNDERAGE"
    assert await _count(db, Photo, user_id=minor_id) == 0
    [job] = fake_queue.named(DELETE_FILES)
    assert job.kwargs["objects"] == [["velora-private", raw]]


async def test_a_refusal_with_no_files_queues_nothing(
    db: AsyncSession,
    client: AsyncClient,
    new_account: NewAccount,
    fake_queue: FakeQueue,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON_IST)
    _, token = await new_account()

    response = await _post_dob(client, token, "2010-01-01")

    assert _error(response)["code"] == "UNDERAGE"
    assert fake_queue.jobs == []


def test_every_storage_key_on_a_deleted_table_is_in_the_file_list() -> None:
    """D-078: any file stored behind a user row joins the list, read before
    the rows go. A `*_key` column on a table the deletion takes, left off the
    list, would leave its file behind: this fails first."""
    listed = {
        (f.model.__tablename__, f.column) for f in users_repository.UNDERAGE_FILES
    }
    on_deleted_tables = {
        (attached.model.__tablename__, column.name)
        for attached in users_repository.UNDERAGE_DELETES
        for column in attached.model.__table__.columns
        if column.name.endswith("_key")
    }

    assert (
        listed == on_deleted_tables == {("photos", "raw_key"), ("photos", "public_key")}
    )
