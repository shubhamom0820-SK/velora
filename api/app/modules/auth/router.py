"""Sign-in routes (D-035).

`otp_router` is Path B, MSG91's codes. `create_app()` mounts it only where
`AUTH_PHONE_PROVIDER` allows (D-066); everywhere else its routes 404.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_redis, app_settings, client_ipv6_48, rate_limit
from app.core.providers import Providers, get_providers
from app.modules.auth import service
from app.modules.auth.schemas import OtpSend, OtpSent

# 02-ARCHITECTURE §12, D-066: 20 sends an hour per client IP (an IPv6 /64), and
# 100 an hour per IPv6 /48, which one cloud customer can fill with 65,536 /64s.
# Both count before the body is read, invalid numbers included, like the
# waitlist's. The per-number limits and the daily cap are the service's.
OTP_SENDS_PER_IP = 20
OTP_SENDS_PER_IPV6_48 = 100
OTP_SEND_WINDOW_S = 60 * 60

otp_router = APIRouter(prefix="/auth/otp", tags=["auth"])


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
