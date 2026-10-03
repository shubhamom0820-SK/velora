"""The two auth cookies (D-054, D-055, D-067).

- The refresh cookie: the opaque refresh token. HttpOnly, so only the API ever
  reads it; host-only on the API (no `Domain`); sent only to `/v1/auth`.
- The CSRF cookie: `new_csrf()`'s value, readable by the web, which sends it
  back as `X-CSRF`. Scoped to `COOKIE_DOMAIN`, so the web on the parent domain
  can read it; host-only where that's empty, locally.

Both are named for their environment, with no fallback: a bare name would make
one environment the default every other collides with (D-055). Both are
`Secure` everywhere, locally too: Safari keeps no Secure cookie over plain
`http://127.0.0.1`, so local sign-in needs Chrome or Firefox (D-067, CLAUDE.md).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import Response

from app.core.config import Settings

# Every environment's own suffix (D-055). A KeyError, never a default, for one
# not listed here.
COOKIE_SUFFIX: dict[str, str] = {
    "production": "prod",
    "staging": "staging",
    "local": "local",
}
REFRESH_COOKIE_PATH = "/v1/auth"
CSRF_COOKIE_PATH = "/"
# A refresh token is good for 30 days from its own rotation (D-067), and the
# CSRF value is renewed with it.
COOKIE_LIFETIME = timedelta(days=30)
_SAME_SITE: Literal["lax"] = "lax"


def refresh_cookie_name(settings: Settings) -> str:
    return f"refresh_{COOKIE_SUFFIX[settings.ENV]}"


def csrf_cookie_name(settings: Settings) -> str:
    return f"csrf_{COOKIE_SUFFIX[settings.ENV]}"


def set_session_cookies(
    response: Response, settings: Settings, *, refresh_token: str, csrf: str
) -> None:
    max_age = int(COOKIE_LIFETIME.total_seconds())
    response.set_cookie(
        refresh_cookie_name(settings),
        refresh_token,
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite=_SAME_SITE,
    )
    response.set_cookie(
        csrf_cookie_name(settings),
        csrf,
        max_age=max_age,
        path=CSRF_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN or None,
        secure=True,
        httponly=False,
        samesite=_SAME_SITE,
    )
