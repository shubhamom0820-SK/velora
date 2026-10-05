"""The local S3's CORS rule on the private bucket (T-4.6, T-4.9), read the way
a browser reads it: by the preflight it sends before a cross-origin PUT with a
Content-Type. The web on http://127.0.0.1:3000, and the E2E's production build
on http://127.0.0.1:3100, upload photos straight to `velora-private` on
http://127.0.0.1:9000, so without the rule no local upload works, and without
its limits a local upload passes that staging's rule (PUT, Content-Type, its
own origin) refuses.

`s3-init` sets it (`infra/s3/private-cors.xml`) at every `make infra-up`, and
in CI. A failure here on a machine whose stack predates T-4.9 means: run
`make infra-up` again."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from tests.infra import LOCAL_S3_URL, S3_DOWN_REASON, S3_UP, in_ci, infra_policy

WEB = "http://127.0.0.1:3000"
# The E2E's web (web/playwright.config.ts, T-4.9): one rule of its own.
E2E_WEB = "http://127.0.0.1:3100"
ADMITTED = (WEB, E2E_WEB)
# A key nobody stores: a preflight asks about the request, not the object.
OBJECT = f"{LOCAL_S3_URL}/velora-private/raw/cors-probe/cors-probe"


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    decision = infra_policy(reachable=S3_UP, ci=in_ci())
    if decision == "skip":
        pytest.skip(S3_DOWN_REASON)
    if decision == "fail":
        pytest.fail(
            f"CI requires the local S3, and it is not reachable ({S3_DOWN_REASON})."
        )
    async with httpx.AsyncClient(timeout=10) as client:
        yield client


async def _preflight(
    http: httpx.AsyncClient, origin: str, method: str, headers: str
) -> httpx.Response:
    return await http.options(
        OBJECT,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


def _allowed(response: httpx.Response, name: str) -> set[str]:
    value = response.headers.get(f"Access-Control-Allow-{name}", "")
    return {part.strip().lower() for part in value.split(",") if part.strip()}


@pytest.mark.parametrize("origin", ADMITTED)
async def test_each_local_web_may_put_a_photo_with_its_content_type(
    http: httpx.AsyncClient, origin: str
) -> None:
    response = await _preflight(http, origin, "PUT", "content-type")

    assert response.status_code == 200, (
        f"{response.status_code}: the private bucket has no CORS rule for "
        f"{origin}. Run `make infra-up` again (T-4.6, T-4.9)."
    )
    assert response.headers["Access-Control-Allow-Origin"] == origin
    assert _allowed(response, "Methods") == {"put"}
    assert _allowed(response, "Headers") == {"content-type"}


@pytest.mark.parametrize(
    "origin",
    [
        # `localhost` is another origin, and refused (CLAUDE.md: 127.0.0.1).
        "http://localhost:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3001",
        "https://staging.veloraapp.co.in",
        "https://evil.example",
    ],
)
async def test_no_other_origin_may(http: httpx.AsyncClient, origin: str) -> None:
    """SeaweedFS answers every origin unless a bucket has a rule of its own."""
    response = await _preflight(http, origin, "PUT", "content-type")

    assert "Access-Control-Allow-Origin" not in response.headers
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ADMITTED)
@pytest.mark.parametrize("method", ["DELETE", "GET", "POST"])
async def test_no_other_method_may(
    http: httpx.AsyncClient, origin: str, method: str
) -> None:
    response = await _preflight(http, origin, method, "content-type")

    assert method.lower() not in _allowed(response, "Methods")


@pytest.mark.parametrize("origin", ADMITTED)
async def test_no_other_header_may(http: httpx.AsyncClient, origin: str) -> None:
    response = await _preflight(http, origin, "PUT", "content-type,x-amz-acl")

    assert "x-amz-acl" not in _allowed(response, "Headers")
