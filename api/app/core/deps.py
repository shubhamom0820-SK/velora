"""FastAPI dependencies shared across modules (02-ARCHITECTURE.md §2).

`rate_limit` arrives first, with the waitlist (T-2.3); `current_user` and
`require_role` follow with T-3.5.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core import ratelimit
from app.core.config import SOCKET_CLIENT_IP_ALLOWED_IN, Settings
from app.core.errors import AppError

# The bucket for a request whose address can't be read. On Fly every request
# arrives with the proxy's header, so one without it, or with a garbled one, came
# some other way; all such requests share this one bucket, so leaving the header
# out or mangling it can't escape a limit.
UNKNOWN_CLIENT = "unknown"


def client_bucket(request: Request) -> str:
    """Who a per-IP limit counts this request against (D-056).

    The address comes from `CLIENT_IP_HEADER`, set by the platform's proxy
    (`Fly-Client-IP`). Never from `X-Forwarded-For`, whose leftmost entries the
    client writes, and never from `request.client` outside local: behind Fly
    that is the proxy, or, through uvicorn's forwarded-header handling, the
    client's own choice again. A limiter keyed on either passes every test,
    because no test forges a header, and limits nothing.
    """
    settings: Settings = request.app.state.settings
    raw: str | None
    if settings.CLIENT_IP_HEADER:
        raw = request.headers.get(settings.CLIENT_IP_HEADER)
    elif settings.ENV in SOCKET_CLIENT_IP_ALLOWED_IN and request.client is not None:
        raw = request.client.host
    else:
        raw = None
    return bucket_for(raw)


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
    scope: str, *, limit: int, window_s: int
) -> Callable[[Request], Awaitable[None]]:
    """A dependency allowing `limit` requests per client per `window_s` seconds.

    It runs before the body is checked against its schema, so a request with
    an invalid email counts too (only a body that isn't JSON at all is refused
    first). If Redis can't be reached the request fails (500) rather than going
    through unlimited: an abuse limit that switches off under strain isn't one.
    """

    async def dependency(request: Request) -> None:
        verdict = await ratelimit.hit(
            request.app.state.redis,
            scope,
            client_bucket(request),
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
