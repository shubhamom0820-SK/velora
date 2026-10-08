"""`POST /v1/auth/refresh` and `/v1/auth/logout` (T-3.4): rotation, the
10-second grace and reuse detection (D-067, 🔒 15), CSRF, `auth_time` carried
unchanged (D-071), and logout by cookie, clearing both."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import jwt
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import events
from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.providers import FakeProviders
from app.core.security import (
    E164,
    hash_phone,
    hash_token,
    make_access_token,
    new_csrf,
    new_refresh_token,
    normalize_phone,
)
from app.modules.auth import service
from app.modules.auth.models import Session
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import make_test_settings

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)
TYPED = "98123 45678"
SETTINGS = make_test_settings()
THIRTY_DAYS = 30 * 24 * 60 * 60


class Device:
    """One browser: the cookies it holds, sent back as a browser would."""

    def __init__(self, response: Response) -> None:
        self.refresh = ""
        self.csrf = ""
        self.take(response)

    def take(self, response: Response) -> None:
        cookies = _cookies(response)
        self.refresh = cookies["refresh_local"][0]
        self.csrf = cookies["csrf_local"][0]

    def headers(self, *, csrf: str | None = None) -> dict[str, str]:
        sent = self.csrf if csrf is None else csrf
        headers = {"Cookie": f"refresh_local={self.refresh}; csrf_local={self.csrf}"}
        if sent:
            headers["X-CSRF"] = sent
        return headers


def _cookies(response: Response) -> dict[str, tuple[str, dict[str, str | bool]]]:
    cookies: dict[str, tuple[str, dict[str, str | bool]]] = {}
    for header in response.headers.get_list("set-cookie"):
        first, *rest = [part.strip() for part in header.split(";")]
        name, _, value = first.partition("=")
        attributes: dict[str, str | bool] = {}
        for part in rest:
            key, sep, val = part.partition("=")
            attributes[key.lower()] = val if sep else True
        cookies[name] = (value, attributes)
    return cookies


async def _sign_in(client: AsyncClient, fake_providers: FakeProviders) -> Device:
    await client.post("/v1/auth/otp/send", json={"phone": TYPED})
    code = fake_providers.sms.sent[-1].code
    response = await client.post(
        "/v1/auth/otp/verify", json={"phone": TYPED, "otp": code}
    )
    assert response.status_code == 200
    return Device(response)


async def _signed_in_user(db: AsyncSession) -> User | None:
    """The account `_sign_in` made, by its number: never just any user, since
    other tests in the run commit users of their own (06-TESTING)."""
    phone_hash = hash_phone(normalize_phone(TYPED), SETTINGS)
    user: User | None = await db.scalar(
        select(User).where(User.phone_hash == phone_hash)
    )
    return user


async def _refresh(client: AsyncClient, device: Device, **kwargs: Any) -> Response:
    return await client.post("/v1/auth/refresh", headers=device.headers(**kwargs))


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _sessions(db: AsyncSession) -> list[Session]:
    rows = await db.scalars(select(Session).order_by(Session.created_at, Session.id))
    return list(rows.all())


REVOKED = {
    "code": "SESSION_REVOKED",
    "message": "You've been signed out. Sign in again.",
}
AUTH_REQUIRED = {"code": "AUTH_REQUIRED", "message": "Sign in to continue."}


# --- Rotation ----------------------------------------------------------------------


async def test_a_refresh_rotates_the_token_and_the_csrf_value(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    device = await _sign_in(client, fake_providers)
    old_refresh, old_csrf = device.refresh, device.csrf
    clock.advance(timedelta(minutes=14))

    response = await _refresh(client, device)

    assert response.status_code == 200
    assert set(response.json()) == {"access_token"}
    device.take(response)
    assert device.refresh != old_refresh and device.csrf != old_csrf
    old, new = sorted(await _sessions(db), key=lambda s: s.revoked_at is None)
    assert old.token_hash == hash_token(old_refresh)
    assert new.token_hash == hash_token(device.refresh)
    assert (old.revoked_at, old.replaced_by) == (START + timedelta(minutes=14), new.id)
    assert new.revoked_at is None
    assert new.family_id == old.family_id and new.user_id == old.user_id
    # Thirty days from this rotation, not from sign-in (D-067).
    assert new.expires_at == START + timedelta(minutes=14, days=30)


async def test_the_rotated_cookies_have_the_sign_in_cookies_attributes(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    device = await _sign_in(client, fake_providers)

    cookies = _cookies(await _refresh(client, device))

    assert set(cookies) == {"refresh_local", "csrf_local"}
    assert cookies["refresh_local"][1] == {
        "httponly": True,
        "max-age": str(THIRTY_DAYS),
        "path": "/v1/auth",
        "samesite": "lax",
        "secure": True,
    }
    assert cookies["csrf_local"][1] == {
        "max-age": str(THIRTY_DAYS),
        "path": "/",
        "samesite": "lax",
        "secure": True,
    }


async def test_auth_time_survives_every_rotation(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    device = await _sign_in(client, fake_providers)

    for hours in range(1, 4):
        clock.advance(timedelta(hours=1))
        response = await _refresh(client, device)
        assert response.status_code == 200
        device.take(response)
        claims = jwt.decode(
            response.json()["access_token"], options={"verify_signature": False}
        )
        assert claims["auth_time"] == int(START.timestamp())
        assert claims["iat"] == int((START + timedelta(hours=hours)).timestamp())

    assert {s.auth_time for s in await _sessions(db)} == {START}


async def test_a_new_access_token_carries_the_users_role_now(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
) -> None:
    device = await _sign_in(client, fake_providers)
    user = await db.scalar(
        select(User).where(
            User.phone_hash == hash_phone(E164("+919812345678"), SETTINGS)
        )
    )
    assert user is not None
    from app.core.enums import Role

    user.role = Role.MODERATOR
    await db.flush()

    token = (await _refresh(client, device)).json()["access_token"]

    assert jwt.decode(token, options={"verify_signature": False})["role"] == "moderator"


# --- Reuse: the grace and the family (D-067, 🔒 15) -----------------------------


@pytest.mark.critical
async def test_reuse_more_than_ten_seconds_later_revokes_the_family(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    clock.freeze(START)
    device = await _sign_in(client, fake_providers)
    stolen = Device.__new__(Device)
    stolen.refresh, stolen.csrf = device.refresh, device.csrf
    rotated = await _refresh(client, device)
    device.take(rotated)

    clock.advance(timedelta(seconds=10))
    replay = await _refresh(client, stolen)

    assert replay.status_code == 401
    assert _error(replay) == REVOKED
    sessions = await _sessions(db)
    assert all(s.revoked_at is not None for s in sessions)
    # The rotated one keeps when it was rotated; only the live one is revoked now.
    assert sorted(s.revoked_at for s in sessions if s.revoked_at) == [
        START,
        START + timedelta(seconds=10),
    ]
    # And the user's sockets close with it (T-7.4).
    assert _closed_sockets(published) == [sessions[0].user_id]
    # The rightful device is signed out too: the family is gone.
    after = await _refresh(client, device)
    assert _error(after) == REVOKED


@pytest.mark.critical
async def test_reuse_within_ten_seconds_is_refused_and_leaves_the_family(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """Two tabs refreshing at once: the second presents the token the first
    has just rotated (D-067)."""
    clock.freeze(START)
    first_tab = await _sign_in(client, fake_providers)
    second_tab = Device.__new__(Device)
    second_tab.refresh, second_tab.csrf = first_tab.refresh, first_tab.csrf
    first_tab.take(await _refresh(client, first_tab))

    clock.advance(timedelta(seconds=9, microseconds=999_999))
    late = await _refresh(client, second_tab)

    assert late.status_code == 401
    assert _error(late) == REVOKED
    live = [s for s in await _sessions(db) if s.revoked_at is None]
    assert len(live) == 1
    assert (await _refresh(client, first_tab)).status_code == 200


async def test_two_refreshes_at_once_rotate_a_token_once(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On two connections, as two workers would be. Each waits, after reading
    the session, for the other to have read it too, up to a second: so without
    the row lock both read it unrotated and both rotate it, forking the family.
    With the lock the second can't read it until the first commits, the first
    stops waiting, and the second finds it rotated, inside the grace. Written
    for real, so it cleans up after itself."""
    token, csrf = new_refresh_token(), new_csrf()
    user_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                "insert into users (id, phone_hash, phone_enc, referral_code) "
                "values (:id, :h, '\\x00', :code)"
            ),
            {"id": user_id, "h": f"race-{user_id}", "code": f"RACE{user_id.hex[:8]}"},
        )
        await conn.execute(
            text(
                "insert into sessions (user_id, family_id, token_hash, expires_at, "
                "auth_time) values (:u, gen_random_uuid(), :t, "
                "now() + interval '30 days', now())"
            ),
            {"u": user_id, "t": hash_token(token)},
        )

    arrived = 0
    both_read = asyncio.Event()
    real_get_user = users_service.get_user

    async def get_user_once_both_have_read(
        session: AsyncSession, uid: uuid.UUID
    ) -> User:
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            both_read.set()
        try:
            await asyncio.wait_for(both_read.wait(), timeout=1)
        except TimeoutError:
            pass
        return await real_get_user(session, uid)

    monkeypatch.setattr(users_service, "get_user", get_user_once_both_have_read)

    async def attempt() -> str:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            try:
                await service.refresh(
                    session,
                    SETTINGS,
                    refresh_token=token,
                    csrf_cookie=csrf,
                    csrf_header=csrf,
                )
            except AppError as error:
                return error.code
            return "rotated"

    try:
        results = await asyncio.gather(attempt(), attempt())
        async with test_engine.connect() as conn:
            count = await conn.scalar(
                text("select count(*) from sessions where user_id = :u"),
                {"u": user_id},
            )
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(text("delete from users where id = :u"), {"u": user_id})

    assert sorted(results) == ["SESSION_REVOKED", "rotated"]
    assert count == 2
    assert arrived == 1  # the second never read the row unrotated


# --- Authenticated by the cookie and X-CSRF -------------------------------------


@pytest.mark.parametrize(
    "csrf",
    ["", "not-the-cookie", "x" * 43],
    ids=["missing", "different", "same length, different"],
)
async def test_without_the_matching_csrf_header_nothing_rotates(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    csrf: str,
) -> None:
    device = await _sign_in(client, fake_providers)

    response = await _refresh(client, device, csrf=csrf)

    assert response.status_code == 401
    assert _error(response) == AUTH_REQUIRED
    assert len(await _sessions(db)) == 1
    assert "set-cookie" not in response.headers


async def test_a_missing_cookie_is_auth_required(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    device = await _sign_in(client, fake_providers)

    no_refresh = await client.post(
        "/v1/auth/refresh",
        headers={"Cookie": f"csrf_local={device.csrf}", "X-CSRF": device.csrf},
    )
    no_csrf_cookie = await client.post(
        "/v1/auth/refresh",
        headers={"Cookie": f"refresh_local={device.refresh}", "X-CSRF": device.csrf},
    )

    no_csrf_at_all = await client.post(
        "/v1/auth/refresh", headers={"Cookie": f"refresh_local={device.refresh}"}
    )

    assert _error(no_refresh) == AUTH_REQUIRED
    assert _error(no_csrf_cookie) == AUTH_REQUIRED
    # Neither the cookie nor the header: two missing values never match.
    assert _error(no_csrf_at_all) == AUTH_REQUIRED
    assert len(await _sessions(db)) == 1


async def test_a_token_we_never_issued_is_auth_required(
    db: AsyncSession, client: AsyncClient
) -> None:
    csrf = new_csrf()
    response = await client.post(
        "/v1/auth/refresh",
        headers={
            "Cookie": f"refresh_local={new_refresh_token()}; csrf_local={csrf}",
            "X-CSRF": csrf,
        },
    )

    assert response.status_code == 401
    assert _error(response) == AUTH_REQUIRED


@pytest.mark.parametrize(
    "cookies",
    [
        "refresh_staging={refresh}; csrf_local={csrf}",
        "refresh_local={refresh}; csrf_prod={csrf}",
    ],
    ids=["staging's refresh cookie", "production's CSRF cookie"],
)
async def test_another_environments_cookie_is_not_read(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders, cookies: str
) -> None:
    """Locally only `refresh_local` and `csrf_local` count (D-055). One cookie
    under another environment's name, the other right: still refused."""
    device = await _sign_in(client, fake_providers)

    response = await client.post(
        "/v1/auth/refresh",
        headers={
            "Cookie": cookies.format(refresh=device.refresh, csrf=device.csrf),
            "X-CSRF": device.csrf,
        },
    )

    assert _error(response) == AUTH_REQUIRED
    assert len(await _sessions(db)) == 1


async def test_a_session_past_thirty_days_is_auth_required(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    device = await _sign_in(client, fake_providers)

    clock.advance(timedelta(days=30))
    response = await _refresh(client, device)

    assert response.status_code == 401
    assert _error(response) == AUTH_REQUIRED


@pytest.mark.parametrize(
    ("status", "http_status", "code"),
    [
        (UserStatus.BANNED, 403, "ACCOUNT_BANNED"),
        (UserStatus.FROZEN, 403, "ACCOUNT_FROZEN"),
        # Deleting revokes every session (T-9.6); one that somehow survived is
        # signed out all the same (D-500).
        (UserStatus.DELETED, 401, "SESSION_REVOKED"),
    ],
)
async def test_an_account_that_cant_sign_in_cant_refresh_either(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    status: UserStatus,
    http_status: int,
    code: str,
) -> None:
    device = await _sign_in(client, fake_providers)
    user = await _signed_in_user(db)
    assert user is not None
    user.status = status
    await db.flush()

    response = await _refresh(client, device)

    assert response.status_code == http_status
    assert _error(response)["code"] == code
    assert len(await _sessions(db)) == 1


# --- Logout ---------------------------------------------------------------------------


async def test_logout_works_with_an_expired_access_token_and_clears_both_cookies(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    device = await _sign_in(client, fake_providers)
    user = await _signed_in_user(db)
    assert user is not None
    expired = make_access_token(user.id, user.role, SETTINGS, auth_time=START)
    clock.advance(timedelta(minutes=16))

    response = await client.post(
        "/v1/auth/logout",
        headers={**device.headers(), "Authorization": f"Bearer {expired}"},
    )

    assert response.status_code == 204
    assert response.content == b""
    cookies = _cookies(response)
    assert set(cookies) == {"refresh_local", "csrf_local"}
    refresh_value, refresh_attrs = cookies["refresh_local"]
    csrf_value, csrf_attrs = cookies["csrf_local"]
    assert refresh_value in ('""', "")
    assert csrf_value in ('""', "")
    assert {k: v for k, v in refresh_attrs.items() if k != "expires"} == {
        "httponly": True,
        "max-age": "0",
        "path": "/v1/auth",
        "samesite": "lax",
        "secure": True,
    }
    assert {k: v for k, v in csrf_attrs.items() if k != "expires"} == {
        "max-age": "0",
        "path": "/",
        "samesite": "lax",
        "secure": True,
    }
    assert all(
        s.revoked_at == START + timedelta(minutes=16) for s in await _sessions(db)
    )


async def test_logout_revokes_the_whole_family_but_not_another_devices(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    clock.freeze(START)
    phone_device = await _sign_in(client, fake_providers)
    clock.advance(timedelta(minutes=1))
    laptop = await _sign_in(client, fake_providers)
    phone_device.take(await _refresh(client, phone_device))

    published.clear()
    response = await client.post("/v1/auth/logout", headers=phone_device.headers())

    assert response.status_code == 204
    # Its sockets close (T-7.4); the laptop's reconnect, its tokens still good.
    user_ids = {s.user_id for s in await _sessions(db)}
    assert _closed_sockets(published) == list(user_ids)
    assert _error(await _refresh(client, phone_device)) == REVOKED
    assert (await _refresh(client, laptop)).status_code == 200


async def test_logout_without_csrf_revokes_nothing(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    device = await _sign_in(client, fake_providers)

    response = await client.post("/v1/auth/logout", headers=device.headers(csrf=""))

    assert response.status_code == 401
    assert _error(response) == AUTH_REQUIRED
    assert "set-cookie" not in response.headers
    assert all(s.revoked_at is None for s in await _sessions(db))


async def test_logout_clears_the_csrf_cookie_on_its_domain(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    """Staging and production scope it to COOKIE_DOMAIN; the clearing cookie
    must name the same domain, or the browser keeps the original."""
    from fastapi import Response as FastAPIResponse

    from app.modules.auth.cookies import clear_session_cookies

    settings = SETTINGS.model_copy(
        update={"ENV": "staging", "COOKIE_DOMAIN": "staging.veloraapp.co.in"}
    )
    response = FastAPIResponse()
    clear_session_cookies(response, settings)
    cleared = {
        header.split("=", 1)[0]: header
        for header in response.headers.getlist("set-cookie")
    }

    assert set(cleared) == {"refresh_staging", "csrf_staging"}
    assert "Domain=staging.veloraapp.co.in" in cleared["csrf_staging"]
    assert "Domain" not in cleared["refresh_staging"]


async def test_the_refresh_routes_are_served_on_firebase_too(
    db: AsyncSession,
) -> None:
    """Every sign-in path ends in a session, so refresh and logout answer
    whatever AUTH_PHONE_PROVIDER says; only Path B's routes are gated. Asked of
    the app itself: served means 401, not the 404 Path B gets."""
    from httpx import ASGITransport

    from app.core.db import get_session
    from app.main import close_resources, create_app
    from tests.infra import session_for_the_app

    app = create_app(SETTINGS.model_copy(update={"AUTH_PHONE_PROVIDER": "firebase"}))
    app.dependency_overrides[get_session] = session_for_the_app
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            refresh = await client.post("/v1/auth/refresh")
            logout = await client.post("/v1/auth/logout")
            send = await client.post("/v1/auth/otp/send", json={"phone": TYPED})
    finally:
        await close_resources(app)

    assert (refresh.status_code, _error(refresh)) == (401, AUTH_REQUIRED)
    assert (logout.status_code, _error(logout)) == (401, AUTH_REQUIRED)
    assert (send.status_code, _error(send)["code"]) == (404, "NOT_FOUND")


def _closed_sockets(published: list[events.Event]) -> list[uuid.UUID]:
    """Whose sockets a request closed (T-7.4)."""
    return [e.user_id for e in published if e.type == events.CLOSE_SOCKETS]
