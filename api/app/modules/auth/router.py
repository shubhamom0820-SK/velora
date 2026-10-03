"""Sign-in routes (D-035), and the PIN lock (T-3.9).

`otp_router` is Path B, MSG91's codes, and `firebase_router` Path A, Firebase's
token exchange. `create_app()` mounts each only where `AUTH_PHONE_PROVIDER`
chooses it (D-066, D-085); everywhere else its routes 404. `router` holds what
every path shares, refresh and logout, mounted everywhere.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import (
    access_claims,
    app_redis,
    app_settings,
    client_ipv6_48,
    current_user,
    rate_limit,
    user_rate_limit,
)
from app.core.providers import Providers, get_providers
from app.core.security import AccessClaims
from app.modules.auth import service
from app.modules.auth.cookies import (
    clear_session_cookies,
    csrf_cookie_name,
    refresh_cookie_name,
    set_session_cookies,
)
from app.modules.auth.schemas import (
    AccessToken,
    FirebaseSignIn,
    OtpSend,
    OtpSent,
    OtpVerify,
    PinSet,
    PinVerify,
    SignedIn,
)
from app.modules.users.models import User

# 02-ARCHITECTURE §12, D-066: 20 sends an hour per client IP (an IPv6 /64), and
# 100 an hour per IPv6 /48, which one cloud customer can fill with 65,536 /64s.
# Both count before the body is read, invalid numbers included, like the
# waitlist's. The per-number limits and the daily cap are the service's.
OTP_SENDS_PER_IP = 20
OTP_SENDS_PER_IPV6_48 = 100
OTP_SEND_WINDOW_S = 60 * 60

# The double-submit header (D-024): the web reads the CSRF cookie and sends it
# back here, which a page on another site can't do.
CSRF_HEADER = "X-CSRF"

# D-069, 02-ARCHITECTURE §12: setting and checking a PIN share one limit, 10 a
# minute per user. Each check holds 19 MiB for about 18 ms, two at once per
# process (D-062), and five wrong ones lock the PIN anyway.
PIN_CHECKS_PER_MINUTE = 10
_pin_limit = Depends(user_rate_limit("pin", limit=PIN_CHECKS_PER_MINUTE, window_s=60))

# 02-ARCHITECTURE §12: 10 token exchanges an hour per client IP (an IPv6 /64),
# counted before the body is read, invalid tokens included. The 5 a phone is
# the service's, once the token has named the phone.
FIREBASE_EXCHANGES_PER_IP = 10
FIREBASE_EXCHANGE_WINDOW_S = 60 * 60

otp_router = APIRouter(prefix="/auth/otp", tags=["auth"])
firebase_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/auth", tags=["auth"])


@otp_router.post(
    "/send",
    dependencies=[
        Depends(
            rate_limit(
                "otp_send_ip", limit=OTP_SENDS_PER_IP, window_s=OTP_SEND_WINDOW_S
            )
        ),
        Depends(
            rate_limit(
                "otp_send_ipv6_48",
                limit=OTP_SENDS_PER_IPV6_48,
                window_s=OTP_SEND_WINDOW_S,
                bucket=client_ipv6_48,
            )
        ),
    ],
)
async def send_otp(
    body: OtpSend,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(app_redis)],
    settings: Annotated[Settings, Depends(app_settings)],
    providers: Annotated[Providers, Depends(get_providers)],
) -> OtpSent:
    resend_after_s = await service.send_code(
        session, redis, providers.sms, settings, raw_phone=body.phone
    )
    return OtpSent(resend_after_s=resend_after_s)


@otp_router.post("/verify")
async def verify_otp(
    body: OtpVerify,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(app_redis)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> SignedIn:
    signed_in = await service.verify_code(
        session, redis, settings, raw_phone=body.phone, code=body.otp
    )
    set_session_cookies(
        response,
        settings,
        refresh_token=signed_in.refresh_token,
        csrf=signed_in.csrf,
    )
    return SignedIn(access_token=signed_in.access_token, user=signed_in.me)


@firebase_router.post(
    "/firebase",
    dependencies=[
        Depends(
            rate_limit(
                "firebase_ip",
                limit=FIREBASE_EXCHANGES_PER_IP,
                window_s=FIREBASE_EXCHANGE_WINDOW_S,
            )
        )
    ],
)
async def sign_in_with_firebase(
    body: FirebaseSignIn,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(app_redis)],
    settings: Annotated[Settings, Depends(app_settings)],
    providers: Annotated[Providers, Depends(get_providers)],
) -> SignedIn:
    signed_in = await service.sign_in_with_firebase(
        session, redis, providers.firebase_keys, settings, id_token=body.id_token
    )
    set_session_cookies(
        response,
        settings,
        refresh_token=signed_in.refresh_token,
        csrf=signed_in.csrf,
    )
    return SignedIn(access_token=signed_in.access_token, user=signed_in.me)


def _credentials(request: Request, settings: Settings) -> dict[str, str | None]:
    """This environment's two cookies and the header, never another's (D-055)."""
    return {
        "refresh_token": request.cookies.get(refresh_cookie_name(settings)),
        "csrf_cookie": request.cookies.get(csrf_cookie_name(settings)),
        "csrf_header": request.headers.get(CSRF_HEADER),
    }


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> AccessToken:
    rotated = await service.refresh(
        session, settings, **_credentials(request, settings)
    )
    set_session_cookies(
        response, settings, refresh_token=rotated.refresh_token, csrf=rotated.csrf
    )
    return AccessToken(access_token=rotated.access_token)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> None:
    await service.logout(session, settings, **_credentials(request, settings))
    clear_session_cookies(response, settings)


@router.post("/pin/set", status_code=204, dependencies=[_pin_limit])
async def set_pin(
    body: PinSet,
    user: Annotated[User, Depends(current_user)],
    claims: Annotated[AccessClaims, Depends(access_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> None:
    await service.set_pin(
        session,
        settings,
        user_id=user.id,
        auth_time=claims.auth_time,
        pin=body.pin,
        current_pin=body.current_pin,
    )


@router.post("/pin/verify", status_code=204, dependencies=[_pin_limit])
async def verify_pin(
    body: PinVerify,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> None:
    await service.verify_pin(session, settings, user_id=user.id, pin=body.pin)
