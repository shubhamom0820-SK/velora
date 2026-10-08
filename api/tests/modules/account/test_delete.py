"""`DELETE /me` and what follows it (T-9.6, D-500): the account deleted at
once, restored by signing in again before the erasure, and its number free for
a new account after it; never a way around a ban (D-051)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.providers import FakeProviders
from app.core.providers.storage import FakeStorage
from app.core.security import E164, decrypt_phone, hash_phone
from app.modules.account import service as account_service
from app.modules.auth import repository as auth_repository
from app.modules.auth import service as auth_service
from app.modules.auth.models import Session
from app.modules.users import repository as users_repository
from app.modules.users.models import User
from tests.committed import fresh_man
from tests.conftest import MakeUser, make_test_settings
from tests.modules.account.test_erasure import NOW
from tests.modules.photos.test_moderate import Sessions

SETTINGS = make_test_settings()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


def _phone(user: User) -> str:
    assert user.phone_enc is not None
    return decrypt_phone(user.phone_enc, SETTINGS)


async def _sign_in(
    client: AsyncClient, fake_providers: FakeProviders, phone: str
) -> Response:
    sent = await client.post("/v1/auth/otp/send", json={"phone": phone})
    assert sent.status_code == 200
    code = fake_providers.sms.sent[-1].code
    return await client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": code})


async def _live_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    count = await db.scalar(
        text("select count(*) from sessions where user_id = :u and revoked_at is null"),
        {"u": user_id},
    )
    return int(count or 0)


@pytest.mark.critical
async def test_deleting_hides_the_account_at_once_and_signs_it_out_everywhere(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
) -> None:
    clock.freeze(NOW)
    user, token = await make_user()
    for _ in range(2):  # two devices
        db.add(
            Session(
                user_id=user.id,
                family_id=uuid.uuid4(),
                token_hash=uuid.uuid4().hex,
                expires_at=NOW + timedelta(days=30),
                auth_time=NOW,
            )
        )
    await db.execute(
        text(
            "insert into push_subscriptions (user_id, endpoint, p256dh, auth) "
            "values (:u, 'https://push.invalid/a', 'p', 'a')"
        ),
        {"u": user.id},
    )
    await db.flush()

    response = await client.delete("/v1/me", headers=_auth(token))

    assert response.status_code == 202
    erase_by = datetime.fromisoformat(response.json()["erase_by"])
    assert response.json().keys() == {"erase_by"}
    assert erase_by == NOW + timedelta(days=30)
    await db.refresh(user)
    assert user.status is UserStatus.DELETED
    assert user.deleted_requested_at == NOW
    assert user.anonymised_at is None
    assert await _live_sessions(db, user.id) == 0
    pushes = await db.scalar(
        text("select count(*) from push_subscriptions where user_id = :u"),
        {"u": user.id},
    )
    assert pushes == 0
    # The access token's last minutes (D-067) are signed out, everywhere.
    after = await client.get("/v1/me", headers=_auth(token))
    assert after.status_code == 401
    assert _error(after)["code"] == "SESSION_REVOKED"
    again = await client.delete("/v1/me", headers=_auth(token))
    assert _error(again)["code"] == "SESSION_REVOKED"


async def test_a_paused_account_can_be_deleted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()
    await client.post("/v1/me/pause", headers=_auth(token))

    response = await client.delete("/v1/me", headers=_auth(token))

    assert response.status_code == 202
    await db.refresh(user)
    assert user.status is UserStatus.DELETED


@pytest.mark.parametrize(
    ("status", "code"),
    [(UserStatus.BANNED, "ACCOUNT_BANNED"), (UserStatus.FROZEN, "ACCOUNT_FROZEN")],
)
async def test_a_ban_or_freeze_stops_a_deletion_even_one_already_let_in(
    db: AsyncSession, make_user: MakeUser, status: UserStatus, code: str
) -> None:
    """D-051: deleting is never a way around a ban. `current_user` refuses a
    banned account; this is the ban that lands after the request was let in,
    seen under the row's lock."""
    user, _ = await make_user()
    user_id = user.id  # read now: the refusal's rollback expires the object
    await db.execute(update(User).where(User.id == user_id).values(status=status))
    await db.commit()

    with pytest.raises(AppError) as refused:
        await account_service.delete_account(db, user)

    assert refused.value.code == code
    row = await db.scalar(select(User.status).where(User.id == user_id))
    assert row is status


# --- Signing in again (D-500) ---------------------------------------------------------


@pytest.mark.critical
async def test_signing_in_within_the_window_restores_the_account_and_its_velas(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    test_redis: Any,
) -> None:
    user, token = await make_user(credits=9)
    phone = _phone(user)
    await client.delete("/v1/me", headers=_auth(token))

    response = await _sign_in(client, fake_providers, phone)

    assert response.status_code == 200
    me = response.json()["user"]
    assert (me["id"], me["status"], me["balance"]) == (str(user.id), "active", 9)
    await db.refresh(user)
    assert user.status is UserStatus.ACTIVE
    assert user.deleted_requested_at is None


async def test_after_the_erasure_the_number_starts_a_new_account(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    test_redis: Any,
    clock: ModuleType,
) -> None:
    clock.freeze(NOW - timedelta(days=30))
    user, token = await make_user(credits=4)
    phone, phone_hash = _phone(user), user.phone_hash
    await client.delete("/v1/me", headers=_auth(token))
    clock.freeze(NOW)
    erased = await account_service.erase_due_accounts(
        Sessions(db),  # type: ignore[arg-type]
        storage=FakeStorage(),
        settings=SETTINGS,
    )
    assert erased == 1

    response = await _sign_in(client, fake_providers, phone)

    assert response.status_code == 200
    me = response.json()["user"]
    assert me["id"] != str(user.id)
    assert (me["status"], me["onboarding_step"], me["balance"]) == ("active", "dob", 0)
    rows = await db.execute(
        select(User.id, User.anonymised_at).where(User.phone_hash == phone_hash)
    )
    by_id = {str(i): at for i, at in rows}
    assert set(by_id) == {str(user.id), me["id"]}
    assert by_id[str(user.id)] is not None and by_id[me["id"]] is None


async def test_a_banned_number_stays_banned_after_the_erasure(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    test_redis: Any,
    clock: ModuleType,
) -> None:
    """D-051: the hash in `banned_identities` outlives the account. Read on
    Path B, where the API sends a banned number nothing (D-073): a code read
    from the fake SMS's store would be none, so the check is the sign-in's own
    refusal, given the number's code by hand."""
    clock.freeze(NOW - timedelta(days=30))
    user, token = await make_user()
    phone, phone_hash = _phone(user), user.phone_hash
    await client.delete("/v1/me", headers=_auth(token))
    await users_repository.ban_phone_hash(db, phone_hash, "ban")
    clock.freeze(NOW)
    await account_service.erase_due_accounts(
        Sessions(db),  # type: ignore[arg-type]
        storage=FakeStorage(),
        settings=SETTINGS,
    )

    with pytest.raises(AppError) as refused:
        await auth_service.sign_in(db, SETTINGS, E164(phone))

    assert refused.value.code == "ACCOUNT_BANNED"
    accounts = await db.scalar(
        text("select count(*) from users where phone_hash = :h"), {"h": phone_hash}
    )
    assert accounts == 1


# --- The race: a sign-in and the erasure at once (D-500) ----------------------------


class HeldDelete(FakeStorage):
    """Holds the erasure inside its transaction, the row locked, until told."""

    def __init__(self) -> None:
        super().__init__()
        self.inside = asyncio.Event()
        self.release = asyncio.Event()

    async def delete(self, bucket: str, key: str) -> None:
        self.inside.set()
        async with asyncio.timeout(10):
            await self.release.wait()
        await super().delete(bucket, key)


async def _committed_deleted_man(
    engine: AsyncEngine, storage: FakeStorage
) -> tuple[uuid.UUID, str]:
    """A man, deleted 30 days ago, with one photo for the erasure to hold on."""
    man = await fresh_man(engine)
    key = f"raw/{man}/{uuid.uuid4()}"
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(
                status=UserStatus.DELETED, deleted_requested_at=NOW - timedelta(days=30)
            )
        )
        await session.execute(
            text(
                "insert into photos (user_id, kind, raw_key) values (:u, 'private', :k)"
            ),
            {"u": man, "k": key},
        )
        token = await session.scalar(select(User.phone_enc).where(User.id == man))
    await storage.put_bytes(SETTINGS.R2_BUCKET_PRIVATE, key, b"x", "image/jpeg")
    assert token is not None
    return man, decrypt_phone(token, SETTINGS)


async def _take_back(engine: AsyncEngine, phone: str) -> None:
    """Every account the race left on the number, gone: an erased row would
    make every later downgrade refuse (D-500), and committed rows are this
    test's to remove (06-TESTING)."""
    phone_hash = hash_phone(E164(phone), SETTINGS)
    async with AsyncSession(engine) as session, session.begin():
        ids = list(
            await session.scalars(select(User.id).where(User.phone_hash == phone_hash))
        )
        for user_id in ids:
            await users_repository.delete_account(session, user_id)


@pytest.mark.parametrize("first", ["erasure", "sign_in"])
async def test_a_sign_in_and_the_erasure_at_once_never_leave_both_or_neither(
    test_engine: AsyncEngine,
    clock: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    first: str,
) -> None:
    """Both take the row's lock. The overlap is forced, and asserted: the
    second waits while the first holds it. Erasure first: the sign-in finds no
    live account and starts a new one. Sign-in first: the account is restored,
    and the erasure finds nothing due.

    Both are always seen through to the end, under a time limit, before any
    assertion: if one fails, the test fails saying so, and never hangs with
    the other still holding its session (found breaking T-9.6's guards)."""
    clock.freeze(NOW)
    storage = HeldDelete()
    man, phone = await _committed_deleted_man(test_engine, storage)
    sessionmaker = SessionmakerOn(test_engine)
    tasks: list[asyncio.Task[Any]] = []
    try:
        if first == "erasure":
            erasing = asyncio.create_task(
                account_service.erase_account(
                    sessionmaker,  # type: ignore[arg-type]
                    man,
                    NOW - account_service.ERASE_AFTER,
                    storage,
                    SETTINGS,
                )
            )
            tasks.append(erasing)
            async with asyncio.timeout(10):
                await storage.inside.wait()
            async with AsyncSession(test_engine, expire_on_commit=False) as session:
                signing_in = asyncio.create_task(
                    auth_service.sign_in(session, SETTINGS, E164(phone))
                )
                tasks.append(signing_in)
                await asyncio.sleep(0.5)
                waited = not signing_in.done()
                storage.release.set()
                async with asyncio.timeout(20):
                    erased_it, signed_in = await asyncio.gather(
                        erasing, signing_in, return_exceptions=True
                    )
            assert waited, "the sign-in didn't wait for the lock"
            assert erased_it is True, erased_it
            assert not isinstance(signed_in, BaseException), signed_in
            assert signed_in.me.id != man
            assert signed_in.me.onboarding_step.value == "dob"
        else:
            entered, release = asyncio.Event(), asyncio.Event()
            real_insert = auth_repository.insert_session

            async def held_insert(*args: Any, **kwargs: Any) -> Any:
                entered.set()
                async with asyncio.timeout(10):
                    await release.wait()
                return await real_insert(*args, **kwargs)

            monkeypatch.setattr(auth_repository, "insert_session", held_insert)
            async with AsyncSession(test_engine, expire_on_commit=False) as session:
                signing_in = asyncio.create_task(
                    auth_service.sign_in(session, SETTINGS, E164(phone))
                )
                tasks.append(signing_in)
                async with asyncio.timeout(10):
                    await entered.wait()
                storage.release.set()
                erasing = asyncio.create_task(
                    account_service.erase_account(
                        sessionmaker,  # type: ignore[arg-type]
                        man,
                        NOW - account_service.ERASE_AFTER,
                        storage,
                        SETTINGS,
                    )
                )
                tasks.append(erasing)
                await asyncio.sleep(0.5)
                waited = not erasing.done()
                release.set()
                async with asyncio.timeout(20):
                    signed_in, erased_it = await asyncio.gather(
                        signing_in, erasing, return_exceptions=True
                    )
            assert waited, "the erasure didn't wait for the lock"
            assert erased_it is False, erased_it
            assert not isinstance(signed_in, BaseException), signed_in
            assert signed_in.me.id == man
            assert signed_in.me.status is UserStatus.ACTIVE
        async with AsyncSession(test_engine) as session:
            erased = await session.scalar(
                select(User.anonymised_at).where(User.id == man)
            )
        assert (erased is not None) is (first == "erasure")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await _take_back(test_engine, phone)


class SessionmakerOn:
    """A sessionmaker on the real engine, each session its own connection."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    def __call__(self) -> AsyncSession:
        return AsyncSession(self.engine, expire_on_commit=False)
