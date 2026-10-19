"""`scripts/sentry-alerts` (T-9.12, D-1005) against a fake of Sentry's API:
`--check` passes on exactly SPEC and fails, saying what, on anything missing,
extra or different; `--apply` builds SPEC from nothing, and a second run
changes nothing; the token goes only in the Authorization header.

A fake, so these prove the script's logic, not Sentry's shapes: the first
real run is the founder's (infra/OBSERVABILITY.md)."""

from __future__ import annotations

import copy
import json
from typing import Any

import httpx
import pytest

from ops import sentry_alerts as sa

TOKEN = "sntryu_test-token-never-printed-0123456789"
ORG = "velora"
MEMBER = "4242"


class FakeSentry:
    """Sentry's state, and the calls this script makes against it."""

    def __init__(self) -> None:
        self.projects: dict[str, dict[str, Any]] = {
            sa.API_PROJECT: {"id": "11", "slug": sa.API_PROJECT},
            sa.WEB_PROJECT: {"id": "12", "slug": sa.WEB_PROJECT},
        }
        self.settings: dict[str, dict[str, bool]] = {
            slug: {
                "scrubIPAddresses": False,
                "dataScrubber": True,
                "dataScrubberDefaults": True,
            }
            for slug in self.projects
        }
        self.uptime: list[dict[str, Any]] = []
        self.workflows: list[dict[str, Any]] = []
        self.detectors: dict[str, list[dict[str, Any]]] = {
            "11": [{"id": "101", "type": sa.ERROR_DETECTOR}],
            "12": [{"id": "102", "type": sa.ERROR_DETECTOR}],
        }
        self.writes: list[str] = []
        self.authorizations: set[str] = set()
        self.urls: list[str] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.authorizations.add(request.headers.get("authorization", ""))
        self.urls.append(str(request.url))
        assert str(request.url).startswith(sa.API)
        path = request.url.path.removeprefix("/api/0")
        body: dict[str, Any] = json.loads(request.content) if request.content else {}
        key = (request.method, path)
        if request.method != "GET":
            self.writes.append(f"{request.method} {path}")
        if key == ("GET", "/organizations/"):
            return httpx.Response(200, json=[{"slug": ORG}])
        if key == ("GET", f"/organizations/{ORG}/projects/"):
            return httpx.Response(200, json=list(self.projects.values()))
        if key == ("GET", f"/organizations/{ORG}/members/"):
            return httpx.Response(200, json=[{"user": {"id": MEMBER}}])
        for slug in self.projects:
            if key == ("GET", f"/projects/{ORG}/{slug}/"):
                return httpx.Response(200, json={"slug": slug, **self.settings[slug]})
            if key == ("PUT", f"/projects/{ORG}/{slug}/"):
                self.settings[slug].update(body)
                return httpx.Response(200, json={"slug": slug, **self.settings[slug]})
        if key == ("GET", f"/organizations/{ORG}/uptime/"):
            return httpx.Response(200, json=self.uptime)
        if key == ("POST", f"/projects/{ORG}/{sa.API_PROJECT}/uptime/"):
            monitor = {
                "id": "301",
                "name": body["name"],
                "url": body["url"],
                "method": body["method"],
                "intervalSeconds": body["interval_seconds"],
                "timeoutMs": body["timeout_ms"],
                "environment": body["environment"],
                "status": body["status"],
                "projectSlug": sa.API_PROJECT,
            }
            self.uptime.append(monitor)
            self.detectors["11"].append({"id": "103", "type": sa.UPTIME_DETECTOR})
            return httpx.Response(201, json=monitor)
        if key == ("GET", f"/organizations/{ORG}/detectors/"):
            return httpx.Response(
                200, json=self.detectors[request.url.params["project"]]
            )
        if key == ("GET", f"/organizations/{ORG}/workflows/"):
            return httpx.Response(200, json=self.workflows)
        if key == ("POST", f"/organizations/{ORG}/workflows/"):
            self.workflows.append(_as_served("201", body))
            return httpx.Response(201, json=self.workflows[-1])
        for workflow in self.workflows:
            if key == ("PUT", f"/organizations/{ORG}/workflows/{workflow['id']}/"):
                workflow.update(_as_served(workflow["id"], body))
                return httpx.Response(200, json=workflow)
        return httpx.Response(404, json={"detail": f"no fake for {key}"})


def _as_served(id_: str, body: dict[str, Any]) -> dict[str, Any]:
    """What the documented response looks like for a body this script sent."""
    return {
        "id": id_,
        "name": body["name"],
        "enabled": body["enabled"],
        "environment": body["environment"],
        "config": body["config"],
        "detectorIds": [str(d) for d in body["detector_ids"]],
        "triggers": body["triggers"],
        "actionFilters": body["action_filters"],
    }


async def _run(
    fake: FakeSentry,
    flag: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, str]:
    monkeypatch.setenv(sa.TOKEN_VARIABLE, TOKEN)
    code = await sa.main_async([flag], transport=fake.transport())
    out = capsys.readouterr()
    return code, out.out + out.err


@pytest.fixture
def spec() -> FakeSentry:
    """Sentry exactly as SPEC: what --apply makes from nothing."""
    fake = FakeSentry()
    for slug in fake.settings:
        fake.settings[slug] = dict(sa.PROJECT_SETTINGS)
    fake.uptime = [{"id": "301", **sa.UPTIME}]
    fake.detectors["11"].append({"id": "103", "type": sa.UPTIME_DETECTOR})
    fake.workflows = [_as_served("201", sa._alert_body(MEMBER, ["101", "102", "103"]))]
    return fake


def test_the_plans_spec() -> None:
    """The Developer plan's: one uptime monitor on staging's /readyz, an email
    alert on every new or returning issue in both projects, scrubbing on."""
    assert sa.API == "https://de.sentry.io/api/0"  # the EU region
    assert sa.UPTIME["url"] == "https://api.staging.veloraapp.co.in/readyz"
    assert sa.ALERT_TRIGGERS == {
        "first_seen_event",
        "regression_event",
        "reappeared_event",
    }
    assert sa.PROJECT_SETTINGS == {
        "scrubIPAddresses": True,
        "dataScrubber": True,
        "dataScrubberDefaults": True,
    }


async def test_check_passes_on_exactly_spec_and_writes_nothing(
    spec: FakeSentry,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code, out = await _run(spec, "--check", capsys, monkeypatch)

    assert (code, out) == (0, "sentry-alerts: Sentry is exactly SPEC.\n")
    assert spec.writes == []


@pytest.mark.parametrize(
    ("change", "says"),
    [
        (lambda f: f.uptime.clear(), "uptime: no monitor"),
        (
            lambda f: f.uptime.append({**f.uptime[0], "id": "302", "name": "another"}),
            "uptime: 2 monitors (another, staging /readyz)",
        ),
        (
            lambda f: f.uptime[0].update(url="https://api.veloraapp.co.in/readyz"),
            "url is 'https://api.veloraapp.co.in/readyz'",
        ),
        (
            lambda f: f.settings[sa.WEB_PROJECT].update(scrubIPAddresses=False),
            "velora-web: scrubIPAddresses should be True",
        ),
        (
            lambda f: f.workflows.clear(),
            "alerts: no 'Velora: every new or returning issue'",
        ),
        (
            lambda f: f.workflows.append(
                {"id": "9", "name": "Send a notification for high priority issues"}
            ),
            "alerts: 1 not in SPEC (Send a notification for high priority issues)",
        ),
        (lambda f: f.workflows[0].update(enabled=False), "it is disabled"),
        (
            lambda f: f.workflows[0]["detectorIds"].remove("103"),
            "it watches detectors ['101', '102']",
        ),
        (
            lambda f: f.workflows[0]["triggers"]["conditions"].pop(),
            "triggers are ['first_seen_event', 'reappeared_event']",
        ),
        (
            lambda f: f.workflows[0]["actionFilters"][0]["actions"][0]["config"].update(
                targetIdentifier="1"
            ),
            "its one action isn't an email to the account's member",
        ),
        (
            lambda f: f.workflows[0]["actionFilters"][0]["conditions"].append(
                {"type": "level"}
            ),
            "an action filter has conditions",
        ),
    ],
    ids=[
        "no uptime",
        "two uptime",
        "uptime on production",
        "ip addresses stored",
        "no alert",
        "sentrys default alert",
        "alert off",
        "uptime unwatched",
        "a trigger missing",
        "email to someone else",
        "filtered",
    ],
)
async def test_check_fails_on_any_difference_and_says_which(
    spec: FakeSentry,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    change: Any,
    says: str,
) -> None:
    change(spec)

    code, out = await _run(spec, "--check", capsys, monkeypatch)

    assert code == 1
    assert says in out
    assert "exactly SPEC" not in out
    assert spec.writes == []


async def test_apply_builds_spec_from_nothing_and_a_second_run_changes_nothing(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    spec: FakeSentry,
) -> None:
    fake = FakeSentry()

    code, out = await _run(fake, "--apply", capsys, monkeypatch)

    assert code == 0, out
    assert "uptime: created staging /readyz" in out
    assert f"alert: created {sa.ALERT_NAME}" in out
    assert out.endswith("sentry-alerts: Sentry is exactly SPEC.\n")
    assert sorted(fake.writes) == [
        f"POST /organizations/{ORG}/workflows/",
        f"POST /projects/{ORG}/{sa.API_PROJECT}/uptime/",
        f"PUT /projects/{ORG}/{sa.API_PROJECT}/",
        f"PUT /projects/{ORG}/{sa.WEB_PROJECT}/",
    ]
    assert fake.workflows == spec.workflows
    assert fake.uptime[0] | {"id": "301"} == spec.uptime[0]

    fake.writes.clear()
    code, out = await _run(fake, "--apply", capsys, monkeypatch)
    assert (code, fake.writes) == (0, [])


async def test_apply_corrects_our_alert_but_never_deletes_another(
    spec: FakeSentry,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec.workflows[0].update(enabled=False)
    spec.workflows.append({"id": "9", "name": "Someone's own"})

    code, out = await _run(spec, "--apply", capsys, monkeypatch)

    assert code == 1
    assert "alert: corrected" in out
    assert "alerts: 1 not in SPEC (Someone's own)" in out
    assert spec.writes == [f"PUT /organizations/{ORG}/workflows/201/"]
    assert [w["name"] for w in spec.workflows] == [sa.ALERT_NAME, "Someone's own"]


async def test_the_token_is_sent_only_as_the_bearer_and_never_printed(
    spec: FakeSentry,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = copy.deepcopy(spec)
    broken.workflows.clear()

    for fake in (spec, broken):
        _, out = await _run(fake, "--check", capsys, monkeypatch)
        assert TOKEN not in out
        assert fake.authorizations == {f"Bearer {TOKEN}"}
        assert not [url for url in fake.urls if TOKEN in url]


async def test_no_token_is_refused_before_any_call(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(sa.TOKEN_VARIABLE, raising=False)
    fake = FakeSentry()

    code = await sa.main_async(["--check"], transport=fake.transport())

    assert code == 2
    assert "SENTRY_AUTH_TOKEN is unset" in capsys.readouterr().err
    assert fake.urls == []


@pytest.mark.parametrize(
    ("status", "says"),
    [
        (401, "401, the token was refused"),
        (403, "403, the token lacks a scope"),
        (500, "500, Sentry said: boom"),
    ],
)
async def test_sentrys_refusal_is_exit_3_in_its_own_words(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    says: str,
) -> None:
    monkeypatch.setenv(sa.TOKEN_VARIABLE, TOKEN)
    transport = httpx.MockTransport(lambda _: httpx.Response(status, text="boom"))

    code = await sa.main_async(["--check"], transport=transport)

    err = capsys.readouterr().err
    assert code == 3
    assert says in err
    assert TOKEN not in err


async def test_a_missing_project_is_named_with_what_exists(
    spec: FakeSentry,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del spec.projects[sa.WEB_PROJECT]

    code, out = await _run(spec, "--check", capsys, monkeypatch)

    assert code == 3
    assert "no project velora-web in velora (it has velora-api)" in out
