"""Sign-in by phone (D-035). Path B's codes: send (T-3.2) and verify (T-3.3);
Path A's Firebase token exchange (T-3.14); the session every path ends in
(T-3.3); and the PIN lock (T-3.9).

Every number is answered the same way and counts against the same limits,
banned and unknown ones included: a ban surfaces only at verify (D-066). No
phone number, code, hash, token or key is logged or put in an error (rule 15).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events, ratelimit
from app.core.config import Settings
from app.core.enums import OnboardingStep
from app.core.errors import AppError, invalid_field
from app.core.providers.firebase import FirebaseKeys
from app.core.providers.sms import SmsProvider, SmsRecipientNotAllowed
from app.core.security import (
    E164,
    PinCheck,
    check_pin,
    csrf_matches,
    firebase_token_invalid,
    hash_otp,
    hash_phone,
    hash_pin,
    hash_token,
    make_access_token,
    new_csrf,
    new_otp_code,
    new_refresh_token,
    normalize_phone,
    otp_matches,
    verify_firebase_id_token,
)
from app.modules.admin import service as admin_service
from app.modules.auth import firebase_store, otp_store, pins, repository
from app.modules.auth.models import Session as SessionRow
from app.modules.users import service as users_service
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
# A token rotated this recently is refused without its family being revoked:
# two tabs refreshing at once present the same token, and the second must not
# sign both out (D-067). Older than this, it's a stolen token being replayed.
REUSE_GRACE = timedelta(seconds=10)


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


# --- Path A: the Firebase token exchange (T-3.14, D-085) -------------------------

# 02-ARCHITECTURE §12: 5 sign-ins a phone an hour. The router holds the 10 an IP.
FIREBASE_SIGN_INS_PER_PHONE = 5
FIREBASE_SIGN_IN_WINDOW_S = 60 * 60


async def sign_in_with_firebase(
    session: AsyncSession,
    redis: Redis,
    keys: FirebaseKeys,
    settings: Settings,
    *,
    id_token: str,
) -> NewSession:
    """Swap a Firebase ID token for a session of ours, exactly as Path B's
    verify ends: `sign_in()`, banned numbers and all.

    Firebase proved the number by SMS; the token says so, once checked
    (`verify_firebase_id_token`). Then India only (`PHONE_NOT_SUPPORTED`), then
    used once, then 5 sign-ins a phone an hour. A replayed token is refused
    before it counts against the number, so replaying someone's token can't
    lock them out. A number Firebase texted that `normalize_phone` still
    refuses gets its usual answer, as it would on Path B.
    """
    verified = await verify_firebase_id_token(id_token, keys, settings)
    phone = normalize_phone(verified.phone_number)
    ttl_s = math.ceil((verified.expires_at - clock.now()).total_seconds())
    if not await firebase_store.spend(redis, hash_token(id_token), ttl_s=ttl_s):
        log.info("firebase_token_refused", reason="reused")
        raise firebase_token_invalid()
    verdict = await ratelimit.hit(
        redis,
        "firebase_phone",
        hash_phone(phone, settings),
        limit=FIREBASE_SIGN_INS_PER_PHONE,
        window_s=FIREBASE_SIGN_IN_WINDOW_S,
    )
    if not verdict.allowed:
        raise _rate_limited(verdict.retry_after_s)
    return await sign_in(session, settings, phone)


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
        if users_service.restore_if_deleted(user):
            log.info("account.restored", user_id=str(user.id))
        users_service.refuse_who_may_not_sign_in(user)
        # A fresh sign-in is D-069's way back from a locked PIN: proof of the
        # number, which is the account.
        user.pin_failed = 0
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


def _account_banned() -> AppError:
    return users_service.account_banned()


# --- Refresh and logout (T-3.4) ---------------------------------------------------


@dataclass(frozen=True)
class Rotated:
    access_token: str
    refresh_token: str
    csrf: str


async def refresh(
    session: AsyncSession,
    settings: Settings,
    *,
    refresh_token: str | None,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> Rotated:
    """Swap a refresh token for a new one and a fresh access token.

    Authenticated by the refresh cookie and `X-CSRF` matching the CSRF cookie
    (D-024, D-055). A token already rotated is refused: within 10 seconds,
    leaving its family alone (two tabs); after that, revoking the family, since
    only a copy of the token can still be presenting it (D-067). The new
    session carries the family's `auth_time` unchanged (D-071).
    """
    now = clock.now()
    async with session.begin():
        current = await _authenticated_session(
            session, refresh_token, csrf_cookie, csrf_header
        )
        if current.revoked_at is None:
            return await _rotate(session, settings, current, now)
        if now - current.revoked_at >= REUSE_GRACE:
            await repository.revoke_family(
                session, user_id=current.user_id, family_id=current.family_id, at=now
            )
            events.close_sockets(session, current.user_id)
    # After the transaction commits, so a family revoked above stays revoked.
    raise _session_revoked()


async def _rotate(
    session: AsyncSession, settings: Settings, current: SessionRow, now: datetime
) -> Rotated:
    """Replace `current` with a new session of the same family."""
    if current.expires_at <= now:
        raise _auth_required()
    user = await users_service.get_user(session, current.user_id)
    users_service.refuse_who_may_not_sign_in(user)
    new_token = new_refresh_token()
    successor = await repository.insert_session(
        session,
        user_id=current.user_id,
        family_id=current.family_id,
        token_hash=hash_token(new_token),
        expires_at=now + SESSION_TTL,
        auth_time=current.auth_time,
    )
    current.revoked_at = now
    current.replaced_by = successor.id
    return Rotated(
        access_token=make_access_token(
            user.id, user.role, settings, auth_time=current.auth_time
        ),
        refresh_token=new_token,
        csrf=new_csrf(),
    )


async def logout(
    session: AsyncSession,
    settings: Settings,
    *,
    refresh_token: str | None,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> None:
    """End this device's session family: authenticated like refresh, never by
    the access token, so it works once that has expired (D-067). Each revoked
    session's access token still works for up to 15 minutes."""
    async with session.begin():
        current = await _authenticated_session(
            session, refresh_token, csrf_cookie, csrf_header
        )
        await repository.revoke_family(
            session,
            user_id=current.user_id,
            family_id=current.family_id,
            at=clock.now(),
        )
        events.close_sockets(session, current.user_id)


async def _authenticated_session(
    session: AsyncSession,
    refresh_token: str | None,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> SessionRow:
    """The session the refresh cookie names, locked, once `X-CSRF` matches the
    CSRF cookie. Anything missing or wrong is `AUTH_REQUIRED`, saying no more."""
    if not csrf_matches(csrf_header, csrf_cookie) or not refresh_token:
        raise _auth_required()
    current = await repository.session_by_token_hash_for_update(
        session, hash_token(refresh_token)
    )
    if current is None:
        raise _auth_required()
    return current


async def sign_out_everywhere(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every session of the user, in the caller's transaction: a
    deleted account (T-9.6). Access tokens keep their last minutes (D-067),
    which `current_user` answers with `SESSION_REVOKED`."""
    await repository.revoke_every_session(session, user_id=user_id, at=clock.now())
    events.close_sockets(session, user_id)


def _auth_required() -> AppError:
    return AppError("AUTH_REQUIRED", "Sign in to continue.", status=401)


def _session_revoked() -> AppError:
    return AppError(
        "SESSION_REVOKED", "You've been signed out. Sign in again.", status=401
    )


# --- The PIN lock (T-3.9) ---------------------------------------------------------
#
# What the lock doesn't do (D-069, with D-067): it deters whoever picks up an
# unlocked phone; it protects nothing. The web keeps a working access token
# behind the lock screen, and five wrong PINs revoke the sessions while each
# one's access token works for up to 15 minutes more. Never build on it as a
# security boundary.

# Wrong PINs before every session is revoked (D-069).
PIN_TRIES = 5
# Within this long of a fresh sign-in, read from the token's `auth_time`
# (D-071), a PIN changes without the current one: D-069's "forgot PIN" is sign
# out, sign in by OTP, set a new one. Ten minutes on, it needs the current PIN.
FRESH_SIGN_IN = timedelta(minutes=10)


async def verify_pin(
    session: AsyncSession, settings: Settings, *, user_id: uuid.UUID, pin: str
) -> None:
    """`POST /auth/pin/verify`: returns for the right PIN, raises otherwise."""
    await _check_the_users_pin(session, settings, user_id=user_id, pin=pin)


async def _check_the_users_pin(
    session: AsyncSession, settings: Settings, *, user_id: uuid.UUID, pin: str
) -> None:
    """Check `pin` against the user's, counting the try first.

    The try is counted and committed before the hash is checked, in one
    statement that refuses a sixth: tries made at once are each counted, a
    request that dies mid-check has still spent its try, and no more than five
    are ever made between resets (D-069). The right PIN clears the count. A
    stored hash `check_pin` refuses gives the try back: it wasn't a guess, and
    the way out is a fresh sign-in (`reset_required`). At five, every session
    of the user is revoked, and stays so for whatever is tried after.
    """
    async with session.begin():
        user = await users_service.get_user(session, user_id)
        stored = user.pin_hash
        if stored is None:
            raise AppError("NOT_ALLOWED", "You haven't set a PIN.", status=422)
        tries = await users_service.take_pin_try(session, user_id, PIN_TRIES)
        if tries is None:
            await repository.revoke_every_session(
                session, user_id=user_id, at=clock.now()
            )
            events.close_sockets(session, user_id)
    if tries is None:
        raise _session_revoked()

    outcome = await check_pin(pin, stored, settings)
    if outcome is PinCheck.MATCH:
        async with session.begin():
            await users_service.clear_pin_tries(session, user_id)
        return
    if outcome is PinCheck.REFUSED:
        async with session.begin():
            await users_service.give_back_pin_try(session, user_id)
        raise AppError(
            "PIN_INVALID",
            "Your PIN can't be checked. Sign in again to set a new one.",
            status=401,
            details={"reset_required": True},
        )
    if tries >= PIN_TRIES:
        async with session.begin():
            await repository.revoke_every_session(
                session, user_id=user_id, at=clock.now()
            )
            events.close_sockets(session, user_id)
        raise _session_revoked()
    raise AppError(
        "PIN_INVALID",
        "That PIN isn't right.",
        status=401,
        details={"attempts_left": PIN_TRIES - tries},
    )


async def set_pin(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: uuid.UUID,
    auth_time: datetime,
    pin: str,
    current_pin: str | None,
) -> None:
    """`POST /auth/pin/set`: a first PIN, or a new one.

    D-069's rules for what a PIN may be. A PIN already set changes only with
    the current one, which counts as a try like any, unless this device's
    session family signed in within 10 minutes (`auth_time`, D-071). At the
    `pin` onboarding step setting one advances to `selfie`; before it, it is
    `ONBOARDING_INCOMPLETE` (D-068).
    """
    problem = pins.pin_problem(pin)
    if problem is not None:
        raise invalid_field("pin", problem)
    async with session.begin():
        user = await users_service.locked_user(session, user_id)
        users_service.at_step(user, OnboardingStep.PIN)
        changing = user.pin_hash is not None
    fresh = clock.now() - auth_time < FRESH_SIGN_IN
    proven = False
    if changing and not fresh:
        if current_pin is None:
            raise _current_pin_needed()
        await _check_the_users_pin(session, settings, user_id=user_id, pin=current_pin)
        proven = True

    # ~18 ms of argon2, outside any transaction (D-062).
    new_hash = await hash_pin(pin, settings)
    async with session.begin():
        user = await users_service.locked_user(session, user_id)
        advancing = users_service.at_step(user, OnboardingStep.PIN)
        # A PIN set by another request meanwhile needs the proof this one skipped.
        if user.pin_hash is not None and not fresh and not proven:
            raise _current_pin_needed()
        users_service.store_pin(user, new_hash)
        if advancing:
            users_service.advance_past(user, OnboardingStep.PIN)


def _current_pin_needed() -> AppError:
    return invalid_field(
        "current_pin",
        "is needed to change your PIN, unless you signed in within 10 minutes",
    )
