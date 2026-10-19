"""T-9.12's test error (P-904, app/tools/sentry_probe.py): one event, tagged
as the component that sent it, through the alert's own path; and only where
Sentry is on."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest

from app.tools import sentry_probe
from tests.conftest import make_test_settings
from tests.keys import sentry_settings
from tests.sentry_capture import Kept, stop


@pytest.fixture
def staging(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, str]]:
    sentry = sentry_settings()
    settings = make_test_settings().model_copy(update={"ENV": "staging", **sentry})
    monkeypatch.setattr(sentry_probe, "get_settings", lambda: settings)
    try:
        yield sentry
    finally:
        stop()


@pytest.mark.parametrize("component", ["api", "worker"])
def test_it_sends_one_error_as_its_component_and_names_it(
    staging: dict[str, str], component: str
) -> None:
    kept, out = Kept(), io.StringIO()

    code = sentry_probe.main(["--component", component], out, transport=kept)

    assert code == 0, out.getvalue()
    (event,) = kept.events
    assert event["level"] == "error"
    assert event["tags"] == {
        **event["tags"],
        "event": "sentry_probe",
        "component": component,
    }
    assert event["release"] == staging["SENTRY_RELEASE"]
    assert event["environment"] == "staging"
    assert out.getvalue() == (
        f"sentry_probe: sent {event['event_id']} as {component}, ENV=staging, "
        f"release {staging['SENTRY_RELEASE']}\n"
    )
    # Never the DSN, or its key.
    assert (
        staging["SENTRY_DSN"].split("@")[0].removeprefix("https://")
        not in out.getvalue()
    )


def test_it_refuses_where_sentry_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sentry_probe, "get_settings", make_test_settings)
    kept, out = Kept(), io.StringIO()

    code = sentry_probe.main(["--component", "api"], out, transport=kept)

    assert code == 2
    assert out.getvalue() == (
        "sentry_probe: refused, ENV=local (only production, staging, where Sentry is on)\n"
    )
    assert kept.events == []


@pytest.mark.parametrize("argv", [[], ["--component", "web"]], ids=["none", "web"])
def test_a_component_it_doesnt_know_is_refused(
    staging: dict[str, str], argv: list[str]
) -> None:
    assert sentry_probe.main(argv, io.StringIO(), transport=Kept()) == 2
