"""FastAPI dependencies shared across modules (02-ARCHITECTURE.md §2).

`rate_limit` arrived with the waitlist (T-2.3); `current_user`,
`onboarded_user` and `require_role` with T-3.5.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.config import SOCKET_CLIENT_IP_ALLOWED_IN, Settings
from app.core.db import get_session
from app.core.enums import OnboardingStep, Role
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.modules.users import service as users_service
from app.modules.users.models import User

# The bucket for a request whose address can't be read. On Fly every request
# arrives with the proxy's header, so one without it, or with a garbled one, came
# some other way; all such requests share this one bucket, so leaving the header
# out or mangling it can't escape a limit.
UNKNOWN_CLIENT = "unknown"


def app_settings(request: Request) -> Settings:
    """The settings this app was built with, never the global ones (P-05)."""
    settings: Settings = request.app.state.settings
    return settings


def app_redis(request: Request) -> Redis:
    """This app's Redis client."""
    redis: Redis = request.app.state.redis
    return redis


def client_address(request: Request) -> str | None:
    """The client's address as the platform's proxy saw it (D-056), unparsed.

    It comes from `CLIENT_IP_HEADER`, set by the platform's proxy
    (`Fly-Client-IP`). Never from `X-Forwarded-For`, whose leftmost entries the
    client writes, and never from `request.client` outside local: behind Fly
    that is the proxy, or, through uvicorn's forwarded-header handling, the
    client's own choice again. A limiter keyed on either passes every test,
    because no test forges a header, and limits nothing.
    """
    settings: Settings = request.app.state.settings
    if settings.CLIENT_IP_HEADER:
        return request.headers.get(settings.CLIENT_IP_HEADER)
    if settings.ENV in SOCKET_CLIENT_IP_ALLOWED_IN and request.client is not None:
        return request.client.host
    return None


def client_bucket(request: Request) -> str:
    """Who a per-IP limit counts this request against (D-056)."""
    return bucket_for(client_address(request))


def client_ipv6_48(request: Request) -> str | None:
    """The IPv6 /48 the request came from, or None for anything else.

    One cloud customer is routinely handed a whole /48: 65,536 /64s, each its
    own per-IP bucket. Limiting the /48 as well caps what one such network can
    spend on SMS (D-066). An IPv4 address, IPv4-mapped included, and an
    unreadable one have no /48; they're limited by `client_bucket` alone.
    """
    raw = client_address(request)
    if not raw:
        return None
    try:
        ip = ipaddress.ip_address(raw.strip())
    except ValueError:
        return None
    if not isinstance(ip, ipaddress.IPv6Address) or ip.ipv4_mapped is not None:
        return None
    return str(ipaddress.IPv6Network((ip, 48), strict=False))


def bucket_for(raw: str | None) -> str:
    """An IPv4 address as itself; an IPv6 address as its /64.

    One home connection is usually handed a whole IPv6 /64, so a limit on the
    single address would let one person rotate through billions of them.
    """
    if not raw:
        return UNKNOWN_CLIENT
    try:
        ip = ipaddress.ip_address(raw.strip())
    except ValueError:
        return UNKNOWN_CLIENT
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)


def rate_limit(
    scope: str,
    *,
    limit: int,
    window_s: int,
    bucket: Callable[[Request], str | None] = client_bucket,
) -> Callable[[Request], Awaitable[None]]:
    """A dependency allowing `limit` requests per client per `window_s` seconds.

    `bucket` says who a request counts against: the client's IP by default. A
    request it has no bucket for (None) isn't limited by this dependency.

    It runs before the body is checked against its schema, so a request with
    an invalid email counts too (only a body that isn't JSON at all is refused
    first). If Redis can't be reached the request fails (500) rather than going
    through unlimited: an abuse limit that switches off under strain isn't one.
    """

    async def dependency(request: Request) -> None:
        who = bucket(request)
        if who is None:
            return
        verdict = await ratelimit.hit(
            request.app.state.redis,
            scope,
            who,
            limit=limit,
            window_s=window_s,
        )
        if not verdict.allowed:
            raise AppError(
                "RATE_LIMITED",
                "Too many tries. Wait a moment and try again.",
                status=429,
                details={"retry_after_s": verdict.retry_after_s},
            )

    return dependency


# --- Who is asking (T-3.5) --------------------------------------------------------

# 02-ARCHITECTURE §12's default: every authenticated route has it, through
# current_user, keyed on the user rather than the address.
USER_REQUESTS_PER_MINUTE = 300


def _bearer_token(request: Request) -> str:
    scheme, _, token = (request.headers.get("Authorization") or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AppError("AUTH_REQUIRED", "Sign in to continue.", status=401)
    return token.strip()


async def current_user(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> User:
    """The signed-in user, loaded from the database on every request.

    The token proves who; the row decides what they may do. A ban or freeze
    therefore takes effect at the next request, and so does a change of role
    (D-067). What doesn't: a revoked session's access token keeps working until
    it expires, up to 15 minutes, after a logout, a reuse attack or five wrong
    PINs (D-067, D-069). Accepted: closing it would mean a session read per
    request.
    """
    claims = decode_access_token(_bearer_token(request), request.app.state.settings)
    redis: Redis = request.app.state.redis
    verdict = await ratelimit.hit(
        redis, "user", str(claims.user_id), limit=USER_REQUESTS_PER_MINUTE, window_s=60
    )
    if not verdict.allowed:
        raise AppError(
            "RATE_LIMITED",
            "Too many tries. Wait a moment and try again.",
            status=429,
            details={"retry_after_s": verdict.retry_after_s},
        )
    user = await users_service.user_for_request(session, redis, claims.user_id)
    if user is None:
        raise AppError("AUTH_REQUIRED", "Sign in to continue.", status=401)
    return user


async def onboarded_user(user: Annotated[User, Depends(current_user)]) -> User:
    """A signed-in user who has finished onboarding; otherwise
    `ONBOARDING_INCOMPLETE`, naming the step they're at (D-068)."""
    if user.onboarding_step is not OnboardingStep.DONE:
        raise AppError(
            "ONBOARDING_INCOMPLETE",
            "Finish setting up your profile first.",
            status=403,
            details={"step": user.onboarding_step.value},
        )
    return user


def require_role(*roles: Role) -> Callable[..., Awaitable[User]]:
    """A dependency allowing only users whose role, read from their row, is one
    of `roles`. Never the token's `role`: a demotion takes effect at the next
    request, not 15 minutes later (D-067)."""
    allowed = frozenset(roles)

    async def dependency(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in allowed:
            raise AppError("FORBIDDEN", "You don't have access to this.", status=403)
        return user

    return dependency
