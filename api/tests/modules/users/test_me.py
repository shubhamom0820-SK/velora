"""`GET /v1/me` and the dependencies behind every authenticated route (T-3.5):
`current_user`, `onboarded_user`, `require_role`, the 300-a-minute limit, the
throttled `last_active_at`, and D-067's 15-minute tail."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Annotated, Any
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user, onboarded_user, require_role
from app.core.enums import OnboardingStep, Role, UserStatus
from app.core.providers import FakeProviders
from app.core.security import decrypt_phone, make_access_token
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)
SETTINGS = make_test_settings()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _me(client: AsyncClient, token: str) -> Response:
    return await client.get("/v1/me", headers=_bearer(token))


# --- /me -----------------------------------------------------------------------------


async def test_me_is_exactly_the_contracts_fields(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(START)
    user, token = await make_user(gender="female")
    db.add_all(
        [ProfileIntent(user_id=user.id, intent_id=i) for i in (3, 1)]
        + [ProfileInterest(user_id=user.id, interest_id=i) for i in (7, 2, 9, 4, 5)]
    )
    await db.flush()

    profile = await db.get(Profile, user.id)
    assert profile is not None

    response = await _me(client, token)

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "role": "user",
        "status": "active",
        "onboarding_step": "done",
        "gender": "female",
        "age": 25,
        "is_verified": True,
        "has_pin": False,
        "referral_code": user.referral_code,
        "balance": 0,
        "profile": {
            "first_name": "Test",
            "username": profile.username,
            "about": "A test profile, with an about long enough for the rules.",
            "hometown": "Phagwara",
            "city": "Phagwara",
            "seeking": "men",
            "intent_ids": [1, 3],
            "interest_ids": [2, 4, 5, 7, 9],
            "is_hidden": False,
            "hide_age": False,
            "hide_distance": False,
            "show_kudos": True,
            "show_gifts": True,
        },
    }


async def test_me_says_whether_a_pin_is_set_never_the_hash(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()
    user.pin_hash = "$argon2id$v=19$m=19456,t=2,p=1$c29tZXNhbHQ$aGFzaA"
    await db.flush()

    response = await _me(client, token)

    assert response.json()["has_pin"] is True
    assert "argon2" not in response.text


async def test_me_never_sends_the_number_or_the_date_of_birth(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Data nothing displays isn't sent (D-067's discipline), in any format."""
    user, token = await make_user()
    phone = decrypt_phone(user.phone_enc, SETTINGS)
    national = phone.removeprefix("+91")
    assert user.dob is not None

    body = (await _me(client, token)).text

    for leaked in (
        phone,
        phone.removeprefix("+"),
        national,
        f"{national[:5]} {national[5:]}",
        user.phone_hash,
        user.dob.isoformat(),
        user.dob.strftime("%d/%m/%Y"),
        str(user.dob.year),
    ):
        assert leaked not in body
    assert not {"phone", "phone_hash", "phone_enc", "dob", "pin_hash"} & set(
        json.loads(body)
    )


async def test_a_paused_account_still_gets_me(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()
    user.status = UserStatus.PAUSED
    await db.flush()

    response = await _me(client, token)

    assert response.status_code == 200
    assert response.json()["status"] == "paused"


# --- current_user: the token says who, the row says what ---------------------------


async def test_no_token_is_auth_required(db: AsyncSession, client: AsyncClient) -> None:
    for headers in ({}, {"Authorization": ""}, {"Authorization": "Bearer "}):
        response = await client.get("/v1/me", headers=headers)
        assert response.status_code == 401
        assert _error(response) == {
            "code": "AUTH_REQUIRED",
            "message": "Sign in to continue.",
        }


async def test_a_token_under_another_scheme_is_auth_required(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()

    for header in (f"Basic {token}", f"Token {token}", token):
        response = await client.get("/v1/me", headers={"Authorization": header})
        assert _error(response)["code"] == "AUTH_REQUIRED"
    # The scheme's case doesn't matter (RFC 6750).
    assert (
        await client.get("/v1/me", headers={"Authorization": f"bearer {token}"})
    ).status_code == 200


async def test_an_expired_token_is_token_expired(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(START)
    _, token = await make_user()

    clock.advance(timedelta(minutes=15))
    response = await _me(client, token)

    assert response.status_code == 401
    assert _error(response)["code"] == "TOKEN_EXPIRED"


async def test_a_token_for_a_user_who_no_longer_exists_is_auth_required(
    db: AsyncSession, client: AsyncClient
) -> None:
    """D-072 deletes an under-18 account while its token lives on."""
    token = make_access_token(uuid4(), Role.USER, SETTINGS, auth_time=datetime.now(UTC))  # noqa: TID251

    response = await _me(client, token)

    assert response.status_code == 401
    assert _error(response)["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize(
    ("status", "code", "message"),
    [
        (UserStatus.BANNED, "ACCOUNT_BANNED", "This account has been banned."),
        (
            UserStatus.FROZEN,
            "ACCOUNT_FROZEN",
            "This account is frozen while we look into it.",
        ),
        (UserStatus.DELETED, "FORBIDDEN", "This account can't sign in."),
    ],
)
async def test_a_ban_or_freeze_takes_effect_at_the_next_request(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    status: UserStatus,
    code: str,
    message: str,
) -> None:
    user, token = await make_user()
    assert (await _me(client, token)).status_code == 200

    user.status = status
    await db.flush()
    response = await _me(client, token)

    assert response.status_code == 403
    assert _error(response) == {"code": code, "message": message}


async def test_a_revoked_sessions_token_works_until_it_expires(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """D-067's 15-minute tail, pinned so nobody mistakes it for a bug: after
    logout the access token still works, until it expires. Accepted, because
    closing it would mean a session read on every request."""
    clock.freeze(START)
    await client.post("/v1/auth/otp/send", json={"phone": "98123 45678"})
    signed_in = await client.post(
        "/v1/auth/otp/verify",
        json={"phone": "98123 45678", "otp": fake_providers.sms.sent[-1].code},
    )
    token = signed_in.json()["access_token"]
    jar = {
        header.split("=", 1)[0]: header.split("=", 1)[1].split(";")[0]
        for header in signed_in.headers.get_list("set-cookie")
    }
    logout = await client.post(
        "/v1/auth/logout",
        headers={
            "Cookie": f"refresh_local={jar['refresh_local']}; "
            f"csrf_local={jar['csrf_local']}",
            "X-CSRF": jar["csrf_local"],
        },
    )
    assert logout.status_code == 204

    clock.advance(timedelta(minutes=14, seconds=59))
    assert (await _me(client, token)).status_code == 200
    clock.advance(timedelta(seconds=1))
    assert _error(await _me(client, token))["code"] == "TOKEN_EXPIRED"


# --- The 300-a-minute limit (02-ARCHITECTURE §12) ----------------------------------


async def test_the_301st_request_in_a_minute_is_refused_for_that_user_alone(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(START)
    _, token = await make_user()
    _, other = await make_user()

    for _ in range(300):
        assert (await _me(client, token)).status_code == 200
    refused = await _me(client, token)

    assert refused.status_code == 429
    assert _error(refused) == {
        "code": "RATE_LIMITED",
        "message": "Too many tries. Wait a moment and try again.",
        "details": {"retry_after_s": 60},
    }
    assert (await _me(client, other)).status_code == 200
    clock.advance(timedelta(seconds=60))
    assert (await _me(client, token)).status_code == 200


async def test_the_limit_counts_before_the_database_is_read(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """A banned user still spends their allowance: the limit is by token."""
    clock.freeze(START)
    user, token = await make_user()
    user.status = UserStatus.BANNED
    await db.flush()

    for _ in range(300):
        assert (await _me(client, token)).status_code == 403
    assert (await _me(client, token)).status_code == 429


# --- last_active_at, at most once a minute -------------------------------------------


async def _last_active(db: AsyncSession, user_id: UUID) -> datetime | None:
    value: datetime | None = await db.scalar(
        text("select last_active_at from users where id = :id"), {"id": user_id}
    )
    return value


async def test_last_active_at_moves_at_most_once_a_minute(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(START)
    user, token = await make_user()
    user_id = user.id
    assert await _last_active(db, user_id) is None

    await _me(client, token)
    assert await _last_active(db, user_id) == START

    clock.advance(timedelta(seconds=59))
    await _me(client, token)
    assert await _last_active(db, user_id) == START

    clock.advance(timedelta(seconds=1))
    await _me(client, token)
    assert await _last_active(db, user_id) == START + timedelta(seconds=60)


async def test_a_refused_user_is_not_noted_as_active(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()
    user_id = user.id
    user.status = UserStatus.FROZEN
    await db.flush()

    assert (await _me(client, token)).status_code == 403

    assert await _last_active(db, user_id) is None


# --- onboarded_user and require_role, through routes of their own -------------------


@pytest.fixture
def guarded(app: FastAPI) -> FastAPI:
    @app.get("/v1/_test/onboarded")
    async def _onboarded(
        user: Annotated[User, Depends(onboarded_user)],
    ) -> dict[str, str]:
        return {"id": str(user.id)}

    @app.get("/v1/_test/moderation")
    async def _moderation(
        user: Annotated[User, Depends(require_role(Role.MODERATOR, Role.ADMIN))],
    ) -> dict[str, str]:
        return {"role": user.role.value}

    @app.post("/v1/_test/write")
    async def _write(
        user: Annotated[User, Depends(current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, str]:
        async with session.begin():
            user.onboarding_step = OnboardingStep.GENDER
        return {"step": user.onboarding_step.value}

    return app


async def test_onboarding_incomplete_names_the_step(
    db: AsyncSession, guarded: FastAPI, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await client.get("/v1/_test/onboarded", headers=_bearer(token))

    assert response.status_code == 403
    assert _error(response) == {
        "code": "ONBOARDING_INCOMPLETE",
        "message": "Finish setting up your profile first.",
        "details": {"step": "seeking"},
    }


async def test_an_onboarded_user_passes(
    db: AsyncSession, guarded: FastAPI, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()

    response = await client.get("/v1/_test/onboarded", headers=_bearer(token))

    assert response.json() == {"id": str(user.id)}


async def test_require_role_reads_the_row_never_the_token(
    db: AsyncSession, guarded: FastAPI, client: AsyncClient, make_user: MakeUser
) -> None:
    """A token signed while the user was a moderator, after a demotion: the
    row wins at once (D-067). And the reverse, a promotion."""
    demoted, _ = await make_user()
    as_moderator = make_access_token(
        demoted.id,
        Role.MODERATOR,
        SETTINGS,
        auth_time=datetime.now(UTC),  # noqa: TID251
    )
    promoted, as_user = await make_user()
    promoted.role = Role.ADMIN
    await db.flush()

    refused = await client.get("/v1/_test/moderation", headers=_bearer(as_moderator))
    allowed = await client.get("/v1/_test/moderation", headers=_bearer(as_user))

    assert refused.status_code == 403
    assert _error(refused) == {
        "code": "FORBIDDEN",
        "message": "You don't have access to this.",
    }
    assert allowed.json() == {"role": "admin"}


async def test_a_route_can_open_its_own_transaction_after_current_user(
    db: AsyncSession, guarded: FastAPI, client: AsyncClient, make_user: MakeUser
) -> None:
    """current_user reads in a transaction of its own and ends it, so a
    service's `async with session.begin()` after it works, as in production,
    where nothing else would end it."""
    _, token = await make_user(onboarded=False)

    response = await client.post("/v1/_test/write", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json() == {"step": "gender"}
