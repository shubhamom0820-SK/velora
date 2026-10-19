"""Sentry's side of T-9.12, kept in the repo: what must be set up there, applied
and checked through Sentry's API (D-1005). `scripts/sentry-alerts` runs it.

    scripts/sentry-alerts --check    # read only: exit 0 only if Sentry is exactly SPEC
    scripts/sentry-alerts --apply    # create or correct what differs, then check

**What SPEC is**, for the free Developer plan, never a trial feature (the
founder, 16 October 2026): no metric alert, one uptime monitor, email only.
- Both projects scrub on Sentry's side too: IP addresses never stored, the
  default data scrubber on (D-1003; the SDKs already send none).
- **One uptime monitor**, on staging's `/readyz` for now (P-901 moves it to
  production's for the production checklist). `api.staging` is the Mumbai VM
  since P-49's cutover: one `A` record, the VM's static IP `34.47.244.114`,
  read from a public resolver on 18 October 2026, `/readyz` 200 through Caddy.
- **One alert**: an email to the account's one member whenever an issue is
  new, comes back after being resolved, or reappears after being archived, in
  either project, or the uptime monitor finds `/readyz` down. Every line the
  API, the worker and the web send is alert-worthy by construction (D-1002),
  so "an issue" is the alert: each 5xx, each job failed for good, each
  alerting warning. Resolve an issue once dealt with, and its next occurrence
  alerts again.

**The token** is read from `SENTRY_AUTH_TOKEN` and never printed, logged or put
in an argument. It lives in the founder's Keychain (infra/OBSERVABILITY.md says
how to run this with it); never in GitHub or the repo. Scopes: `org:read`,
`project:read`, `project:write`, `alerts:read`, `alerts:write`; `--check` needs
only the three reads.

**Proven against a fake of Sentry's API only** (`tests/ops`), until the
founder's first run: the alert and monitor endpoints are marked beta in
Sentry's documentation, and the uptime one isn't documented at all (its shape
is read from Sentry's own source, 16 October 2026). A shape Sentry has changed
fails here, loudly, with Sentry's own answer, never silently.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import httpx

# Sentry's EU region (the founder's choice): its API lives on its own host.
API: Final = "https://de.sentry.io/api/0"
TOKEN_VARIABLE: Final = "SENTRY_AUTH_TOKEN"

# The two projects (infra/OBSERVABILITY.md): the API and the worker share one,
# told apart by their `component` tag; the web has its own.
API_PROJECT: Final = "velora-api"
WEB_PROJECT: Final = "velora-web"
PROJECTS: Final = (API_PROJECT, WEB_PROJECT)

# Sentry-side scrubbing on both projects (D-1003).
PROJECT_SETTINGS: Final[Mapping[str, bool]] = {
    "scrubIPAddresses": True,
    "dataScrubber": True,
    "dataScrubberDefaults": True,
}

UPTIME: Final[Mapping[str, Any]] = {
    "name": "staging /readyz",
    "url": "https://api.staging.veloraapp.co.in/readyz",
    "method": "GET",
    "intervalSeconds": 60,
    "timeoutMs": 10_000,
    "environment": "staging",
    "projectSlug": API_PROJECT,
    "status": "active",
}

ALERT_NAME: Final = "Velora: every new or returning issue"
ALERT_TRIGGERS: Final = frozenset(
    {"first_seen_event", "regression_event", "reappeared_event"}
)
# Minutes between two emails for one issue; 0 is every time the triggers fire.
ALERT_FREQUENCY: Final = 0
ERROR_DETECTOR: Final = "error"
UPTIME_DETECTOR: Final = "uptime_domain_failure"


class Refused(Exception):
    """Sentry answered something this script can't go on from. Says what,
    with Sentry's own words, never the token."""


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    def problem(self, line: str) -> None:
        self.problems.append(line)


class Sentry:
    """The few calls this needs, bearer-authenticated."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get(self, path: str, **params: str) -> Any:
        return await self._call("GET", path, params=params or None)

    async def put(self, path: str, body: Mapping[str, Any]) -> Any:
        return await self._call("PUT", path, json=body)

    async def post(self, path: str, body: Mapping[str, Any]) -> Any:
        return await self._call("POST", path, json=body)

    async def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, f"{API}{path}", **kwargs)
        except httpx.HTTPError as error:
            raise Refused(
                f"{method} {path}: Sentry didn't answer ({type(error).__name__})"
            ) from None
        if response.status_code == 401:
            raise Refused(
                f"{method} {path}: 401, the token was refused (expired, or another account's)"
            )
        if response.status_code == 403:
            raise Refused(
                f"{method} {path}: 403, the token lacks a scope this needs (see the module's docstring)"
            )
        if response.status_code >= 400:
            raise Refused(
                f"{method} {path}: {response.status_code}, Sentry said: {response.text[:500]}"
            )
        return response.json() if response.content else None


async def _organization(sentry: Sentry) -> dict[str, Any]:
    orgs = await sentry.get("/organizations/")
    if len(orgs) != 1:
        raise Refused(
            f"the token sees {len(orgs)} organizations; this expects exactly one, Velora's"
        )
    return dict(orgs[0])


async def _projects(sentry: Sentry, org: str) -> dict[str, dict[str, Any]]:
    found = {
        p["slug"]: dict(p) for p in await sentry.get(f"/organizations/{org}/projects/")
    }
    missing = [slug for slug in PROJECTS if slug not in found]
    if missing:
        raise Refused(
            f"no project {', '.join(missing)} in {org} (it has {', '.join(sorted(found)) or 'none'}): "
            "create it, or correct PROJECTS here"
        )
    return {slug: found[slug] for slug in PROJECTS}


async def _member(sentry: Sentry, org: str) -> str:
    members = await sentry.get(f"/organizations/{org}/members/")
    ids = [m["user"]["id"] for m in members if m.get("user")]
    if len(ids) != 1:
        raise Refused(
            f"{org} has {len(ids)} members; the free plan has one, who gets the email"
        )
    return str(ids[0])


async def _check_projects(
    sentry: Sentry, org: str, report: Report, apply: bool
) -> None:
    for slug in PROJECTS:
        details = await sentry.get(f"/projects/{org}/{slug}/")
        wrong = {k: v for k, v in PROJECT_SETTINGS.items() if details.get(k) is not v}
        if not wrong:
            continue
        if apply:
            await sentry.put(f"/projects/{org}/{slug}/", dict(PROJECT_SETTINGS))
            report.changed.append(f"{slug}: set {', '.join(sorted(wrong))}")
        else:
            report.problem(
                f"{slug}: {', '.join(f'{k} should be {v}' for k, v in sorted(wrong.items()))}"
            )


def _uptime_differences(monitor: Mapping[str, Any]) -> list[str]:
    return [
        f"{key} is {monitor.get(key)!r}, not {value!r}"
        for key, value in UPTIME.items()
        if monitor.get(key) != value
    ]


async def _check_uptime(sentry: Sentry, org: str, report: Report, apply: bool) -> None:
    monitors = list(await sentry.get(f"/organizations/{org}/uptime/"))
    if not monitors:
        if apply:
            await sentry.post(
                f"/projects/{org}/{API_PROJECT}/uptime/",
                {
                    "name": UPTIME["name"],
                    "url": UPTIME["url"],
                    "method": UPTIME["method"],
                    "interval_seconds": UPTIME["intervalSeconds"],
                    "timeout_ms": UPTIME["timeoutMs"],
                    "environment": UPTIME["environment"],
                    "status": UPTIME["status"],
                    # /readyz's body is our own status, not anyone's data, but
                    # nothing is kept that isn't needed.
                    "response_capture_enabled": False,
                },
            )
            report.changed.append(f"uptime: created {UPTIME['name']}")
            return
        report.problem(
            f"uptime: no monitor; expected {UPTIME['name']} on {UPTIME['url']}"
        )
        return
    if len(monitors) > 1:
        names = ", ".join(sorted(str(m.get("name")) for m in monitors))
        report.problem(
            f"uptime: {len(monitors)} monitors ({names}); expected exactly one, {UPTIME['name']}"
        )
        return
    differences = _uptime_differences(monitors[0])
    if differences:
        report.problem(f"uptime: {UPTIME['name']}: {'; '.join(differences)}")


async def _detectors(
    sentry: Sentry, org: str, projects: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    """The detectors the alert must be connected to: each project's errors,
    and the uptime monitor's."""
    ids: list[str] = []
    for slug in PROJECTS:
        detectors = await sentry.get(
            f"/organizations/{org}/detectors/", project=str(projects[slug]["id"])
        )
        for wanted in (
            (ERROR_DETECTOR, UPTIME_DETECTOR)
            if slug == API_PROJECT
            else (ERROR_DETECTOR,)
        ):
            found = [str(d["id"]) for d in detectors if d.get("type") == wanted]
            if len(found) != 1:
                raise Refused(f"{slug}: {len(found)} {wanted} detectors; expected one")
            ids.extend(found)
    return sorted(ids)


def _alert_body(member: str, detectors: Sequence[str]) -> dict[str, Any]:
    return {
        "name": ALERT_NAME,
        "enabled": True,
        "environment": None,
        "config": {"frequency": ALERT_FREQUENCY},
        "detector_ids": [int(d) for d in detectors],
        "triggers": {
            "logicType": "any-short",
            "conditions": [
                {"type": kind, "comparison": True, "conditionResult": True}
                for kind in sorted(ALERT_TRIGGERS)
            ],
            "actions": [],
        },
        "action_filters": [
            {
                "logicType": "any-short",
                "conditions": [],
                "actions": [
                    {
                        "type": "email",
                        "integrationId": None,
                        "data": {},
                        "config": {"targetType": "user", "targetIdentifier": member},
                    }
                ],
            }
        ],
    }


def _alert_differences(
    alert: Mapping[str, Any], member: str, detectors: Sequence[str]
) -> list[str]:
    wrong: list[str] = []
    if alert.get("enabled") is not True:
        wrong.append("it is disabled")
    if (alert.get("config") or {}).get("frequency") != ALERT_FREQUENCY:
        wrong.append(f"frequency isn't {ALERT_FREQUENCY}")
    if alert.get("environment") is not None:
        wrong.append("it is limited to one environment")
    triggers = {
        c.get("type") for c in (alert.get("triggers") or {}).get("conditions", [])
    }
    if triggers != ALERT_TRIGGERS:
        wrong.append(
            f"triggers are {sorted(t for t in triggers if t)}, not {sorted(ALERT_TRIGGERS)}"
        )
    filters = alert.get("actionFilters") or []
    actions = [a for f in filters for a in f.get("actions", [])]
    if [f for f in filters if f.get("conditions")]:
        wrong.append(
            "an action filter has conditions, so some issues would send nothing"
        )
    emails = [
        a
        for a in actions
        if a.get("type") == "email"
        and (a.get("config") or {}).get("targetType") == "user"
        and str((a.get("config") or {}).get("targetIdentifier")) == member
    ]
    if len(emails) != 1 or len(actions) != 1:
        wrong.append("its one action isn't an email to the account's member")
    connected = sorted(str(d) for d in alert.get("detectorIds") or [])
    if connected != list(detectors):
        wrong.append(f"it watches detectors {connected}, not {list(detectors)}")
    return wrong


async def _check_alert(
    sentry: Sentry,
    org: str,
    projects: Mapping[str, Mapping[str, Any]],
    report: Report,
    apply: bool,
) -> None:
    member = await _member(sentry, org)
    detectors = await _detectors(sentry, org, projects)
    alerts = list(await sentry.get(f"/organizations/{org}/workflows/"))
    ours = [a for a in alerts if a.get("name") == ALERT_NAME]
    others = sorted(str(a.get("name")) for a in alerts if a.get("name") != ALERT_NAME)
    if others:
        # Never deleted from here: someone made them, or Sentry did by default.
        report.problem(
            f"alerts: {len(others)} not in SPEC ({', '.join(others)}): delete them in "
            "Sentry, or add them here"
        )
    if not ours:
        if apply:
            await sentry.post(
                f"/organizations/{org}/workflows/", _alert_body(member, detectors)
            )
            report.changed.append(f"alert: created {ALERT_NAME}")
        else:
            report.problem(f"alerts: no {ALERT_NAME!r}")
        return
    if len(ours) > 1:
        report.problem(f"alerts: {len(ours)} named {ALERT_NAME!r}; expected one")
        return
    differences = _alert_differences(ours[0], member, detectors)
    if not differences:
        return
    if apply:
        await sentry.put(
            f"/organizations/{org}/workflows/{ours[0]['id']}/",
            _alert_body(member, detectors),
        )
        report.changed.append(
            f"alert: corrected {ALERT_NAME} ({'; '.join(differences)})"
        )
    else:
        report.problem(f"alert {ALERT_NAME!r}: {'; '.join(differences)}")


async def run(client: httpx.AsyncClient, *, apply: bool) -> Report:
    sentry = Sentry(client)
    report = Report()
    org = (await _organization(sentry))["slug"]
    projects = await _projects(sentry, org)
    await _check_projects(sentry, org, report, apply)
    await _check_uptime(sentry, org, report, apply)
    await _check_alert(sentry, org, projects, report, apply)
    return report


async def main_async(
    argv: Sequence[str], transport: httpx.AsyncBaseTransport | None = None
) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/sentry-alerts", description=__doc__.split("\n")[0]
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="read only; exit 0 only if Sentry is exactly SPEC",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="create or correct what differs, then check",
    )
    args = parser.parse_args(argv)
    token = os.environ.get(TOKEN_VARIABLE, "")
    if not token:
        sys.stderr.write(
            f"sentry-alerts: {TOKEN_VARIABLE} is unset. It is read from the environment only, "
            "never an argument (infra/OBSERVABILITY.md says how to pull it from the Keychain).\n"
        )
        return 2
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(
        headers=headers, timeout=30.0, transport=transport
    ) as client:
        try:
            if args.apply:
                applied = await run(client, apply=True)
                for line in applied.changed:
                    sys.stdout.write(f"sentry-alerts: {line}\n")
            report = await run(client, apply=False)
        except Refused as refused:
            sys.stderr.write(f"sentry-alerts: refused. {refused}\n")
            return 3
    if report.problems:
        for line in report.problems:
            sys.stderr.write(f"sentry-alerts: not as SPEC: {line}\n")
        return 1
    sys.stdout.write("sentry-alerts: Sentry is exactly SPEC.\n")
    return 0


def main() -> int:
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
