"""Sign-in routes (D-035).

`otp_router` is Path B, MSG91's codes. `create_app()` mounts it only where
`AUTH_PHONE_PROVIDER` allows (D-066); everywhere else its routes 404.
`router` holds what every path shares, refresh and logout, mounted everywhere.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_redis, app_settings, client_ipv6_48, rate_limit
from app.core.providers import Providers, get_providers
from app.modules.auth import service
from app.modules.auth.cookies import (
    clear_session_cookies,
    csrf_cookie_name,
    refresh_cookie_name,
    set_session_cookies,
)
from app.modules.auth.schemas import (
    AccessToken,
    OtpSend,
    OtpSent,
    OtpVerify,
    SignedIn,
)

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

otp_router = APIRouter(prefix="/auth/otp", tags=["auth"])
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
