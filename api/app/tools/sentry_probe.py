"""T-9.12's test error (P-904): one event to Sentry from inside a container, as
`infra/OBSERVABILITY.md` §4 asks of each component, through the same line every
alert takes: a log line at error level, which `report_to_sentry` sends.

It starts Sentry as the API or the worker starts it (`init_sentry`, the
container's own DSN and release), logs `sentry_probe` at error level, waits for
the send, and prints the event's id, the component, the environment and the
release, so the event can be found in Sentry and read back. Nothing else: no
setting's value, no DSN.

Runs only where Sentry is on, staging and production (`config.SENTRY_IN`, an
allowlist, rule 16). On the staging VM:

    sudo docker compose -p velora exec -T api python -m app.tools.sentry_probe --component api
    sudo docker compose -p velora exec -T worker python -m app.tools.sentry_probe --component worker

Exit 0 when the event was handed to Sentry's transport and flushed, 1 when it
wasn't (said why), 2 when it may not run here or was called wrongly.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Final, TextIO, cast

import sentry_sdk
import structlog
from sentry_sdk.transport import Transport

from app.core.config import SENTRY_IN, get_settings
from app.core.logging import configure_logging
from app.core.observability import Component, init_sentry

EVENT: Final = "sentry_probe"
FLUSH_S: Final = 10.0

log = structlog.get_logger(__name__)


def main(
    argv: Sequence[str] = (),
    out: TextIO = sys.stdout,
    *,
    transport: Transport | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tools.sentry_probe")
    parser.add_argument("--component", choices=("api", "worker"), required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    component = cast(Component, args.component)
    settings = get_settings()
    if settings.ENV not in SENTRY_IN:
        out.write(
            f"sentry_probe: refused, ENV={settings.ENV} "
            f"(only {', '.join(sorted(SENTRY_IN))}, where Sentry is on)\n"
        )
        return 2
    configure_logging(json_logs=True)
    if not init_sentry(settings, component, transport=transport):
        out.write("sentry_probe: FAILED, Sentry didn't start\n")
        return 1
    log.error(EVENT, note="T-9.12's test error (infra/OBSERVABILITY.md §4)")
    event_id = sentry_sdk.last_event_id()
    sentry_sdk.flush(timeout=FLUSH_S)
    if not event_id:
        out.write("sentry_probe: FAILED, no event was made\n")
        return 1
    out.write(
        f"sentry_probe: sent {event_id} as {component}, ENV={settings.ENV}, "
        f"release {settings.SENTRY_RELEASE}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
