"""Sentry started as staging starts it, its events kept instead of sent
(T-9.12): `sentry_events` in a test reads exactly what would have left."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from app.core.logging import configure_logging
from app.core.observability import Component, init_sentry
from tests.conftest import make_test_settings
from tests.keys import sentry_settings


class SentryEvents(list[dict[str, Any]]):
    def text(self) -> str:
        """Every event, whole, as it would be serialised: for "nowhere in it"."""
        return "\n".join(json.dumps(e, default=str) for e in self)

    def named(self, name: str) -> list[dict[str, Any]]:
        return [e for e in self if e.get("tags", {}).get("event") == name]


class Kept(Transport):
    """A transport that keeps each event. Nothing leaves the machine."""

    def __init__(self) -> None:
        super().__init__(None)
        self.events = SentryEvents()

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            self.events.append(dict(event))


def start(component: Component = "api") -> Kept:
    settings = make_test_settings().model_copy(
        update={"ENV": "staging", **sentry_settings()}
    )
    kept = Kept()
    assert init_sentry(settings, component, transport=kept)
    return kept


def stop() -> None:
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
    sentry_sdk.get_global_scope().remove_tag("component")


@pytest.fixture
def sentry_events() -> Iterator[SentryEvents]:
    configure_logging(json_logs=True)
    kept = start()
    try:
        yield kept.events
    finally:
        stop()


@pytest.fixture
def worker_sentry_events() -> Iterator[SentryEvents]:
    """As `sentry_events`, started as the worker starts it."""
    configure_logging(json_logs=True)
    kept = start("worker")
    try:
        yield kept.events
    finally:
        stop()
