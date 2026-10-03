"""Sign-in by phone (D-035). Path B's codes: send (T-3.2).

Every number is answered the same way and counts against the same limits,
banned and unknown ones included: a ban surfaces only at verify (D-066). No
phone number, code, hash or key is logged or put in an error (rule 15).
"""

from __future__ import annotations

import math
from datetime import timedelta

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, ratelimit
from app.core.config import Settings
from app.core.errors import AppError
from app.core.providers.sms import SmsProvider, SmsRecipientNotAllowed
from app.core.security import hash_otp, hash_phone, new_otp_code, normalize_phone
from app.modules.admin import service as admin_service
from app.modules.auth import otp_store, repository

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
