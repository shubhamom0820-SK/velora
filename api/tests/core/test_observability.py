"""Errors and alerts to Sentry (T-9.12, D-1001 to D-1003): only where ENV
allows it, exactly the lines that are alerts, once each, and nothing personal
in any of them. Each test reads what the transport would have sent."""

from __future__ import annotations

from typing import Any

import pytest
import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from httpx import AsyncClient

from app.core.config import SENTRY_IN
from app.core.errors import AppError
from app.core.observability import ALERTING_WARNINGS, init_sentry, scrub
from tests.conftest import make_test_settings
from tests.sentry_capture import SentryEvents, sentry_events, stop

__all__ = ["sentry_events"]  # the fixture, imported for this module's tests

pytestmark = pytest.mark.usefixtures("test_redis")

log = structlog.get_logger("tests.observability")

# Things rule 15 forbids, planted where a request or an error could carry them.
PHONE = "+919812345678"
OTP = "482913"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.secret-token-body"
COOKIE = "refresh-cookie-value-7d1c"


def test_sentry_is_on_only_where_env_is_staging_or_production() -> None:
    """An allowlist (rule 16): a new ENV name sends nothing until it is added."""
    assert frozenset({"staging", "production"}) == SENTRY_IN
    assert init_sentry(make_test_settings(), "api") is False
    assert not sentry_sdk.get_client().is_active()


def test_the_warnings_that_are_alerts() -> None:
    """D-066's half cap, P-381's turnover, and a refused webhook: no others."""
    assert (
        frozenset(
            {"otp_daily_cap_half_used", "payments.turnover", "payments.webhook_refused"}
        )
        == ALERTING_WARNINGS
    )


def test_an_error_line_is_one_event_with_its_fields_release_and_component(
    sentry_events: SentryEvents,
) -> None:
    log.error("storage.delete_failed", banned_id="b-1", remaining=2)

    assert len(sentry_events) == 1
    event = sentry_events[0]
    assert event["level"] == "error"
    assert event["message"] == "storage.delete_failed"
    assert event["tags"]["event"] == "storage.delete_failed"
    assert event["tags"]["component"] == "api"
    assert event["environment"] == "staging"
    assert len(event["release"]) == 40
    assert event["contexts"]["log"] == {"banned_id": "b-1", "remaining": 2}
    assert event["fingerprint"] == ["storage.delete_failed", "error"]


# The error lines the alerts depend on (infra/OBSERVABILITY.md §3), by name:
# any error line is sent, and each must be its own issue, so its first time
# emails. `wallet.ledger_mismatch` is T-9.9's reconciliation (relayed by the
# founder, 18 October 2026).
@pytest.mark.parametrize(
    "name",
    [
        "unhandled_exception",
        "app_error_5xx",
        "storage.delete_failed",
        "job.failed",
        "minutely.failing",
        "queue.depth_high",
        "payments.turnover",
        "wallet.ledger_mismatch",
    ],
)
def test_each_alerting_error_is_an_issue_of_its_own(
    sentry_events: SentryEvents, name: str
) -> None:
    log.error(name)
    log.error("some.other_error")

    (event,) = sentry_events.named(name)
    assert event["level"] == "error"
    assert event["fingerprint"] == [name, "error"]
    assert len(sentry_events) == 2


# The plan's three, as literals: a test reading the constant would lose a case
# the moment one is dropped from it, and stay green.
@pytest.mark.parametrize(
    "name",
    ["otp_daily_cap_half_used", "payments.turnover", "payments.webhook_refused"],
)
def test_each_alerting_warning_is_sent(sentry_events: SentryEvents, name: str) -> None:
    log.warning(name, figure=1)

    assert [e["level"] for e in sentry_events.named(name)] == ["warning"]


def test_any_other_warning_and_anything_below_stay_in_the_logs(
    sentry_events: SentryEvents,
) -> None:
    log.warning("minutely.failed", work="thread_clock", error="OSError")
    log.warning("storage.delete_retrying")
    log.info("payments.turnover", paise=100)  # below ₹15 lakh: info
    log.info("storage.files_deleted")

    assert sentry_events == []


def test_the_turnovers_warning_and_error_are_two_issues(
    sentry_events: SentryEvents,
) -> None:
    """₹15 lakh, then ₹20 lakh: the second must alert though the first is open."""
    log.warning("payments.turnover", paise=1_500_000_00)
    log.error("payments.turnover", paise=2_000_000_00)

    assert [e["fingerprint"] for e in sentry_events] == [
        ["payments.turnover", "warning"],
        ["payments.turnover", "error"],
    ]


def test_an_exception_goes_by_type_and_stack_never_its_message(
    sentry_events: SentryEvents,
) -> None:
    """A Postgres DETAIL or an error built from a row carries values."""
    try:
        raise ValueError(f"Key (phone)=({PHONE}) already exists.")
    except ValueError:
        log.exception("unhandled_exception", exc_type="ValueError")

    assert len(sentry_events) == 1
    (exception,) = sentry_events[0]["exception"]["values"]
    assert exception["type"] == "ValueError"
    assert exception["value"] == ""
    assert exception["stacktrace"]["frames"]
    assert PHONE not in sentry_events.text()


def test_the_scrubber_drops_what_names_a_person() -> None:
    event: Any = {
        "request": {"headers": {"Cookie": COOKIE}},
        "user": {"ip_address": "203.0.113.9"},
        "breadcrumbs": {"values": [{"message": PHONE}]},
        "extra": {"otp": OTP},
        "exception": {"values": [{"type": "KeyError", "value": PHONE}]},
        "tags": {"event": "x"},
    }

    scrubbed = scrub(event, {})

    assert set(scrubbed) == {"exception", "tags"}
    assert scrubbed["exception"]["values"][0] == {"type": "KeyError", "value": ""}


async def test_a_500_is_reported_once_and_nothing_of_the_request_goes(
    app: FastAPI, client: AsyncClient, sentry_events: SentryEvents
) -> None:
    """The request carries a cookie, a bearer token, a query string and a
    body with a phone number and a code; the route reads them into locals.
    None of it may reach Sentry, and the client still gets the envelope."""

    @app.post("/v1/_test/boom")
    async def _boom(request: Request) -> None:
        body = await request.json()
        phone, code = body["phone"], body["code"]
        raise RuntimeError(f"failed for {phone} with {code}")

    response = await client.post(
        f"/v1/_test/boom?otp={OTP}&phone={PHONE}",
        json={"phone": PHONE, "code": OTP},
        headers={"Authorization": f"Bearer {TOKEN}", "Cookie": f"refresh={COOKIE}"},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    assert len(sentry_events) == 1
    event = sentry_events[0]
    assert event["tags"]["event"] == "unhandled_exception"
    assert event["exception"]["values"][-1]["type"] == "RuntimeError"
    assert event["contexts"]["log"]["path"] == "/v1/_test/boom"
    assert "request" not in event
    text = sentry_events.text()
    for planted in (PHONE, OTP, TOKEN, COOKIE):
        assert planted not in text
    # The route's locals held the body: no frame carries any variable.
    frames = [
        frame
        for value in event["exception"]["values"]
        for frame in value["stacktrace"]["frames"]
    ]
    assert frames
    assert not [frame for frame in frames if "vars" in frame]


async def test_a_deliberate_5xx_from_a_v1_route_is_reported(
    app: FastAPI, client: AsyncClient, sentry_events: SentryEvents
) -> None:
    @app.get("/v1/_test/unavailable")
    async def _unavailable() -> None:
        raise AppError("PROVIDER_UNAVAILABLE", "Down.", status=503)

    @app.get("/v1/_test/refused")
    async def _refused() -> None:
        raise AppError("FORBIDDEN", "No.", status=403)

    assert (await client.get("/v1/_test/unavailable")).status_code == 503
    assert (await client.get("/v1/_test/refused")).status_code == 403

    (event,) = sentry_events
    assert event["tags"]["event"] == "app_error_5xx"
    assert event["contexts"]["log"]["code"] == "PROVIDER_UNAVAILABLE"
    assert event["contexts"]["log"]["status"] == 503


async def test_a_probes_5xx_is_the_uptime_checks_not_an_event(
    app: FastAPI, client: AsyncClient, sentry_events: SentryEvents
) -> None:
    """The VM's healthcheck asks /readyz every 15 seconds: a Redis outage would be four events a
    minute a machine, the free plan's month in a day."""

    @app.get("/_test/not-ready")
    async def _not_ready() -> None:
        raise AppError("NOT_READY", "The service is not ready.", status=503)

    assert (await client.get("/_test/not-ready")).status_code == 503
    assert sentry_events == []


def test_nothing_is_sent_once_sentry_is_stopped(
    sentry_events: SentryEvents,
) -> None:
    stop()
    log.error("storage.delete_failed", banned_id="b-1", remaining=1)

    assert sentry_events == []
