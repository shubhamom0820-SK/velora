"""Sign-in by phone (D-035). Path B's codes: send (T-3.2) and verify (T-3.3);
and the session every path ends in (T-3.3).

Every number is answered the same way and counts against the same limits,
banned and unknown ones included: a ban surfaces only at verify (D-066). No
phone number, code, hash, token or key is logged or put in an error (rule 15).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import timedelta

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, ratelimit
from app.core.config import Settings
from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.providers.sms import SmsProvider, SmsRecipientNotAllowed
from app.core.security import (
    E164,
    hash_otp,
    hash_phone,
    hash_token,
    make_access_token,
    new_csrf,
    new_otp_code,
    new_refresh_token,
    normalize_phone,
    otp_matches,
)
from app.modules.admin import service as admin_service
from app.modules.auth import otp_store, repository
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.users.schemas import Me

log = structlog.get_logger(__name__)

# D-066 and 02-ARCHITECTURE §12. Constants beside their decision, like D-060's:
# abuse limits a database write could quietly loosen aren't limits. The one
# tunable figure, the global daily cap, is `app_config.otp_sms_daily_cap`.
CODE_TTL_S = 5 * 60
RESEND_AFTER_S = 45
# (scope, limit, window) for each number: one code per 45 s, 5 an hour, 10 a day.
# The 45 s lock is a one-place window, so the clock moves it like the rest.
PHONE_LIMITS = (
    ("otp_resend", 1, RESEND_AFTER_S),
    ("otp_send_phone_hour", 5, 60 * 60),
    ("otp_send_phone_day", 10, 24 * 60 * 60),
)
# Wrong codes across every code a number is sent: verify records them (T-3.3);
# at 10 in 24 hours, send refuses too, until the window lets one go.
WRONG_CODES_SCOPE = "otp_wrong"
WRONG_CODES_LIMIT = 10
WRONG_CODES_WINDOW_S = 24 * 60 * 60
DAILY_CAP_KEY = "otp_sms_daily_cap"
# Wrong tries per code: the fifth uses the code up (D-066).
CODE_TRIES = 5
# A session is good for 30 days from its own rotation, with no absolute cap:
# someone active never pays for another sign-in SMS (D-067).
SESSION_TTL = timedelta(days=30)


async def send_code(
    session: AsyncSession,
    redis: Redis,
    sms: SmsProvider,
    settings: Settings,
    *,
    raw_phone: str,
) -> int:
    """Send a sign-in code to `raw_phone` and say when another may be asked for.

    A banned number gets exactly this, and nothing is sent. A code is stored for
    it all the same, never sent, so a wrong guess at verify is answered as it
    is for anyone else and the ban stays invisible to whoever doesn't hold the
    number (D-066).
    """
    phone = normalize_phone(raw_phone)
    phone_hash = hash_phone(phone, settings)
    await _refuse_a_number_over_its_limits(redis, phone_hash)

    async with session.begin():
        cap = await admin_service.config_int(session, DAILY_CAP_KEY)
        banned = await repository.is_banned(session, phone_hash)
    await _refuse_past_the_daily_cap(redis, cap)

    code = new_otp_code()
    await otp_store.save_code(
        redis,
        phone_hash,
        hash_otp(phone_hash, code, settings),
        expires_at=clock.now() + timedelta(seconds=CODE_TTL_S),
        ttl_s=CODE_TTL_S,
    )
    if banned:
        return RESEND_AFTER_S
    try:
        await sms.send_otp(phone, code)
    except SmsRecipientNotAllowed as refused:
        await otp_store.discard_code(redis, phone_hash)
        raise AppError("PROVIDER_UNAVAILABLE", str(refused), status=503) from None
    except Exception:
        # A code nobody received must not be left to guess at.
        await otp_store.discard_code(redis, phone_hash)
        raise
    return RESEND_AFTER_S


async def _refuse_a_number_over_its_limits(redis: Redis, phone_hash: str) -> None:
    wrong = await ratelimit.peek(
        redis,
        WRONG_CODES_SCOPE,
        phone_hash,
        limit=WRONG_CODES_LIMIT,
        window_s=WRONG_CODES_WINDOW_S,
    )
    if not wrong.allowed:
        raise _rate_limited(wrong.retry_after_s)
    for scope, limit, window_s in PHONE_LIMITS:
        verdict = await ratelimit.hit(
            redis, scope, phone_hash, limit=limit, window_s=window_s
        )
        if not verdict.allowed:
            raise _rate_limited(verdict.retry_after_s)


async def _refuse_past_the_daily_cap(redis: Redis, cap: int) -> None:
    """At most `cap` codes a day across every number, the day in IST.

    The worst case it bounds, at D-035's unconfirmed ₹0.20 an SMS, is ₹100 a
    day; the cost is that an attacker can spend it and stop Path B sign-ins for
    the rest of the day (D-066). The half-way warning goes to the logs, which
    nobody reads until T-9.12 routes alerts: a known gap.
    """
    sent = await otp_store.count_send(redis, clock.today_ist())
    if sent == math.ceil(cap / 2):
        log.warning("otp_daily_cap_half_used", sent=sent, cap=cap)
    if sent > cap:
        raise AppError(
            "PROVIDER_UNAVAILABLE",
            "We can't send sign-in codes right now. Try again later.",
            status=503,
        )


def _rate_limited(retry_after_s: int) -> AppError:
    return AppError(
        "RATE_LIMITED",
        "Too many tries. Wait a moment and try again.",
        status=429,
        details={"retry_after_s": retry_after_s},
    )


# --- Verify (T-3.3) --------------------------------------------------------------


@dataclass(frozen=True)
class NewSession:
    """What a sign-in hands back: the access token and `Me` for the body, the
    refresh token and CSRF value for the cookies (router)."""

    access_token: str
    refresh_token: str
    csrf: str
    me: Me


async def verify_code(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    raw_phone: str,
    code: str,
) -> NewSession:
    """Check `code` for `raw_phone`; on the right one, sign in, creating the
    account the first time.

    A wrong code counts against the code (5 tries) and the number (10 in 24
    hours, across every code), and the try that reaches either limit uses the
    code up: `OTP_TOO_MANY` (D-066). No code, or one past its 5 minutes, is
    `OTP_EXPIRED`. The right code is used up before anything else happens, so it
    signs in once.
    """
    phone = normalize_phone(raw_phone)
    phone_hash = hash_phone(phone, settings)
    locked = await ratelimit.peek(
        redis,
        WRONG_CODES_SCOPE,
        phone_hash,
        limit=WRONG_CODES_LIMIT,
        window_s=WRONG_CODES_WINDOW_S,
    )
    if not locked.allowed:
        raise _otp_too_many()

    stored = await otp_store.read_code(redis, phone_hash)
    if stored is None:
        raise _otp_expired()
    if clock.now().timestamp() * 1000 >= stored.expires_at_ms:
        await otp_store.discard_code(redis, phone_hash)
        raise _otp_expired()
    if not otp_matches(phone_hash, code, stored.code_hash, settings):
        await _count_a_wrong_code(redis, phone_hash)
    if not await otp_store.consume_code(redis, phone_hash, stored.code_hash):
        raise _otp_expired()
    return await sign_in(session, settings, phone)


async def _count_a_wrong_code(redis: Redis, phone_hash: str) -> None:
    """Always raises: `OTP_INVALID` with the tries left, or `OTP_TOO_MANY`."""
    recorded = await ratelimit.hit(
        redis,
        WRONG_CODES_SCOPE,
        phone_hash,
        limit=WRONG_CODES_LIMIT,
        window_s=WRONG_CODES_WINDOW_S,
    )
    tries = await otp_store.add_wrong_try(redis, phone_hash)
    if tries is None:
        raise _otp_expired()
    wrong_today = await ratelimit.used(
        redis, WRONG_CODES_SCOPE, phone_hash, window_s=WRONG_CODES_WINDOW_S
    )
    if not recorded.allowed or tries >= CODE_TRIES or wrong_today >= WRONG_CODES_LIMIT:
        await otp_store.discard_code(redis, phone_hash)
        raise _otp_too_many()
    # Whichever limit is nearer: the code's 5, or the number's 10 a day.
    attempts_left = min(CODE_TRIES - tries, WRONG_CODES_LIMIT - wrong_today)
    raise AppError(
        "OTP_INVALID",
        "That code isn't right.",
        status=400,
        details={"attempts_left": attempts_left},
    )


def _otp_expired() -> AppError:
    return AppError(
        "OTP_EXPIRED", "That code has expired. Ask for a new one.", status=400
    )


def _otp_too_many() -> AppError:
    return AppError(
        "OTP_TOO_MANY", "Too many wrong codes. Try again later.", status=429
    )


# --- Sign-in: every path ends here (T-3.3; T-3.14 reuses it) ------------------


async def sign_in(session: AsyncSession, settings: Settings, phone: E164) -> NewSession:
    """Sign in the holder of `phone`, proven by the caller: a banned number
    stops here, the account is found or created, and a new session family
    starts, all in one transaction (D-067)."""
    phone_hash = hash_phone(phone, settings)
    refresh_token = new_refresh_token()
    now = clock.now()
    async with session.begin():
        if await repository.is_banned(session, phone_hash):
            raise _account_banned()
        user, _created = await users_service.find_or_create_account(
            session, phone, settings
        )
        _refuse_who_may_not_sign_in(user)
        await repository.insert_session(
            session,
            user_id=user.id,
            family_id=uuid.uuid4(),
            token_hash=hash_token(refresh_token),
            expires_at=now + SESSION_TTL,
            auth_time=now,
        )
        me = await users_service.me(session, user)
    return NewSession(
        access_token=make_access_token(user.id, user.role, settings, auth_time=now),
        refresh_token=refresh_token,
        csrf=new_csrf(),
        me=me,
    )


# Who may sign in (D-067): an allowlist, so a status added later can't until
# someone decides. Paused people may: pausing hides a profile, not an account.
MAY_SIGN_IN = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})


def _refuse_who_may_not_sign_in(user: User) -> None:
    """Banned and frozen accounts get their own codes; `deleted` can't happen
    before T-9.6, which decides, so until then it's FORBIDDEN, like anything
    else not on the list."""
    if user.status in MAY_SIGN_IN:
        return
    if user.status is UserStatus.BANNED:
        raise _account_banned()
    if user.status is UserStatus.FROZEN:
        raise AppError(
            "ACCOUNT_FROZEN",
            "This account is frozen while we look into it.",
            status=403,
        )
    raise AppError("FORBIDDEN", "This account can't sign in.", status=403)


def _account_banned() -> AppError:
    return AppError("ACCOUNT_BANNED", "This account has been banned.", status=403)
