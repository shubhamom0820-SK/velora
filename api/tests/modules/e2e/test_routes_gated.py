"""Every test-only route, whichever module it lives in, is served only where
the E2E runs, and none is ever in OpenAPI (T-9.13).

Each test route has its own test of its gate; this one reads the app's whole
route table, so a route added under `/test` anywhere, without a gate or behind
the wrong one, is red here even if nobody wrote it a test. D-963's role route
makes anyone an admin: the cost of one served by mistake."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

from app.main import contract_openapi, create_app
from tests.conftest import make_test_settings

TEST_PREFIX = "/v1/test/"


def _paths(app: FastAPI) -> list[str]:
    """Every route the app serves, each by its full path and by the path its
    own router gave it: FastAPI nests an included router's routes, and a
    root-level socket's full path reads empty, so either alone misses some."""
    paths: list[str] = []
    for context in iter_route_contexts(app.router.routes):
        paths.append(context.path or "")
        paths.append(str(getattr(context.original_route, "path", "")))
    return paths


def _test_paths(paths: list[str]) -> list[str]:
    return sorted({p for p in paths if p.startswith(TEST_PREFIX)})


def _anything_test(paths: list[str]) -> list[str]:
    return sorted({p for p in paths if "/test/" in p or p.startswith("/test")})


def test_the_e2e_is_served_its_routes() -> None:
    """Where the E2E runs, the table has them all, and the socket: the reading
    below can see a test route, so its empty answers elsewhere mean something."""
    every = _paths(create_app(make_test_settings()))
    paths = _test_paths(every)

    assert "/ws" in every and "/v1/ws/ticket" in every

    assert paths == [
        "/v1/test/payments/webhook",
        "/v1/test/sms/last-code",
        "/v1/test/threads/{thread_id}/expire",
        "/v1/test/users/{user_id}/role",
    ]


@pytest.mark.parametrize(
    "update",
    [
        {"ENV": "staging"},
        {"ENV": "production"},
        {"ENV": "preview"},
        {"ENV": "ci"},
        # A name nobody has listed: a blacklist would wave it through (rule 16).
        {"ENV": "env-nobody-has-named-2031"},
        {"ENV": "production", "SMS_PROVIDER": "msg91", "PAYMENTS_PROVIDER": "razorpay"},
    ],
    ids=lambda update: ",".join(f"{k}={v}" for k, v in update.items()),
)
def test_no_test_route_is_served_anywhere_else(update: dict[str, str]) -> None:
    settings = make_test_settings().model_copy(update=update)

    assert _anything_test(_paths(create_app(settings))) == []


@pytest.mark.parametrize(
    "schema",
    [
        lambda: create_app(make_test_settings()).openapi(),
        lambda: contract_openapi(make_test_settings()),
    ],
    ids=["served", "contract"],
)
def test_no_test_route_is_in_openapi_even_where_served(schema: Any) -> None:
    """Not the app's schema where the E2E runs, nor the contract `make types`
    reads, so the web's generated types never name one."""
    assert _anything_test(list(schema()["paths"])) == []
