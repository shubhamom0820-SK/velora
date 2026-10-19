"""Errors and alerts to Sentry (T-9.12): the API and the worker.

- **On only where ENV is staging or production** (`config.SENTRY_IN`, an
  allowlist, rule 16), where the DSN and the release are required at startup.
  Anywhere else nothing is sent, whatever SENTRY_DSN says.
- **The log line is the report** (D-1002). `report_to_sentry`, one structlog
  processor, sends every line at error level, and the warnings in
  `ALERTING_WARNINGS`, so a failure is reported where it is already logged and
  nothing has a second call to forget. An unhandled 500 is the
  `unhandled_exception` line `errors.py` logs; a job's last failed try is the
  job's own error line, and ARQ's own failures are routed to one by
  `workers/main.py`.
- **No personal data leaves for Sentry's EU region** (D-1003; D-048 keeps the
  data in India). Nothing reads a request: no framework integration, no
  request bodies, headers, cookies, query strings, users or IP addresses, no
  breadcrumbs, no frame locals. An exception is reported by its type and stack,
  never its message, which can carry a row's values (a Postgres DETAIL). What
  goes is the log line's own fields, which rule 15 already keeps clean.
- **Release is the commit** (`SENTRY_RELEASE`, the image's GIT_SHA), and each
  event is tagged with its `component`, api or worker, both in one project.

The SDK sends from a thread of its own, so a report never waits on the event
loop and the event loop never waits on Sentry (rule 7 is about the loop).
"""

from __future__ import annotations

import sys
from collections.abc import MutableMapping
from types import TracebackType
from typing import TYPE_CHECKING, Any, Final, Literal

import sentry_sdk
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.integrations.excepthook import ExcepthookIntegration
from sentry_sdk.transport import Transport
from sentry_sdk.types import Event, Hint

if TYPE_CHECKING:
    from sentry_sdk._types import DataCollectionUserOptions

from app.core.config import SENTRY_IN, Settings

Component = Literal["api", "worker"]

# Warnings that are alerts (D-1002); every other warning stays in the logs.
ALERTING_WARNINGS: Final[frozenset[str]] = frozenset(
    {
        # D-066: half the day's SMS cap spent, the first sign of an attack.
        "otp_daily_cap_half_used",
        # D-483, P-381: the year's turnover past ₹15 lakh (info below it, so
        # never sent; past ₹20 lakh it is an error and goes anyway).
        "payments.turnover",
        # T-9.12: a webhook whose signature didn't match, or had none.
        "payments.webhook_refused",
    }
)
# What the SDK may collect by itself: nothing (D-1003). With no integration
# reading requests most of this has nothing to act on; it is set so a later
# integration can't start collecting by default. Source lines stay: they are
# our code, not anyone's data.
DATA_COLLECTION: Final[DataCollectionUserOptions] = {
    "user_info": False,
    "cookies": {"mode": "off"},
    "http_headers": {"request": {"mode": "off"}},
    "http_bodies": [],
    "url_query_params": {"mode": "off"},
    "graphql": {"document": False, "variables": False},
    "gen_ai": {"inputs": False, "outputs": False},
    "database_query_data": False,
    "queues": False,
    "stack_frame_variables": False,
}
_ALERTING_LEVELS: Final = frozenset({"error", "critical"})
# structlog's own keys, which the event carries in its own fields.
_NOT_FIELDS: Final = frozenset({"event", "level", "timestamp", "exc_info"})


def init_sentry(
    settings: Settings,
    component: Component,
    *,
    transport: type[Transport] | Transport | None = None,
) -> bool:
    """Start reporting where ENV allows it. True if it did. `transport` is for
    tests, which read what would have been sent."""
    if settings.ENV not in SENTRY_IN:
        return False
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        release=settings.SENTRY_RELEASE,
        # Only these three: flush at exit, one report per exception, and a
        # crash outside a request. Nothing that reads a request, a log or an
        # outgoing call (D-1003).
        default_integrations=False,
        auto_enabling_integrations=False,
        integrations=[
            AtexitIntegration(),
            DedupeIntegration(),
            ExcepthookIntegration(),
        ],
        data_collection=DATA_COLLECTION,
        max_breadcrumbs=0,
        before_send=scrub,
        # No tracing, no client reports: errors and alerts only (D-1000).
        traces_sample_rate=None,
        send_client_reports=False,
        transport=transport,
    )
    sentry_sdk.get_global_scope().set_tag("component", component)
    return True


def scrub(event: Event, _hint: Hint) -> Event:
    """The last step before an event leaves (D-1003): whatever an SDK default
    or a later change attached, no request, user or breadcrumb goes, and no
    exception's message."""
    for key in ("request", "user", "breadcrumbs", "extra"):
        event.pop(key, None)  # type: ignore[misc]
    for exception in event.get("exception", {}).get("values", []):
        exception["value"] = ""
    return event


def report_to_sentry(
    _logger: object, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """structlog processor: an alerting line goes to Sentry too (D-1002).

    Runs after the level is added and before the exception is formatted, so it
    reads `exc_info` itself. A no-op while Sentry isn't started.
    """
    level = event_dict.get("level")
    name = event_dict.get("event")
    alerting = level in _ALERTING_LEVELS or (
        level == "warning" and name in ALERTING_WARNINGS
    )
    if alerting and isinstance(name, str) and sentry_sdk.get_client().is_active():
        _report(name, str(level), event_dict)
    return event_dict


def _report(name: str, level: str, event_dict: MutableMapping[str, Any]) -> None:
    fields = {k: v for k, v in event_dict.items() if k not in _NOT_FIELDS}
    error = _exception(event_dict.get("exc_info"))
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("event", name)
        if "request_id" in fields:
            scope.set_tag("request_id", str(fields["request_id"]))
        scope.set_context("log", fields)
        if error is not None:
            # Grouped by its stack, as Sentry groups any exception.
            scope.set_level("error")
            sentry_sdk.capture_exception(error)
        else:
            # One issue per line and level: the turnover's warning at ₹15 lakh
            # and its error at ₹20 lakh are two issues, so the second alerts too.
            scope.fingerprint = [name, level]
            sentry_sdk.capture_message(name, level=level)  # type: ignore[arg-type]


def _exception(exc_info: object) -> BaseException | None:
    if isinstance(exc_info, BaseException):
        return exc_info
    if isinstance(exc_info, tuple) and len(exc_info) == 3:
        candidate = exc_info[1]
        return candidate if isinstance(candidate, BaseException) else None
    if exc_info is True:
        current: tuple[Any, BaseException | None, TracebackType | None]
        current = sys.exc_info()
        return current[1]
    return None
