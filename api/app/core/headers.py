"""Security headers on the API's own responses (P-42, T-3.3).

- `X-Content-Type-Options: nosniff` on every response, so no browser reads a
  JSON body as HTML.
- `Cache-Control: no-store` on every `/v1` response: sign-in hands back an
  access token, and `/me` and everything after it one person's data, which a
  browser or a shared cache must never keep (a shared phone, the back button).

The web's own headers are Next's (D-059); these are the API's. A 500 is built by
Starlette outside every middleware, so `errors.py` applies the same headers
there.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

VERSIONED_PREFIX = "/v1/"


def security_headers(path: str) -> dict[str, str]:
    """The headers a response to `path` carries."""
    headers = {"X-Content-Type-Options": "nosniff"}
    if path == VERSIONED_PREFIX.rstrip("/") or path.startswith(VERSIONED_PREFIX):
        headers["Cache-Control"] = "no-store"
    return headers


class SecurityHeadersMiddleware:
    """Adds `security_headers()` to every HTTP response, replacing any value a
    route set for the same header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = security_headers(scope["path"])

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in extra.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
