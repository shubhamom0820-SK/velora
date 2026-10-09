"""The API for the E2E (T-3.13, T-4.9): `uv run python -m tests.e2e_server`.

Importing `tests.infra` takes a P-55 slot, so this run has a database and a
Redis database of its own, created empty: an E2E run and any number of pytest
runs never meet, and a run starts with no accounts, bans or rate-limit windows
left by the last. The slot is held until this process ends.

Local only, by construction: `ENV=local`, settings built here and never read
from `.env`, and every provider the fake but two:
- **Storage is the local S3** (SeaweedFS, D-086), as `make dev`'s is: the
  journeys upload photos and a selfie from the browser, by presigned PUT, which
  the fake's `fake-storage://` links can't take. The buckets are shared with
  every pytest run and `make dev` (P-55 gives the S3 no slot); each object's
  key carries its user's id, so runs never meet there either.
- **The face match is the real one** (`sface`, D-088): J2's "your selfie
  matches your photos" is then the models' own verdict on the browser's
  selfie, and a test that could never fail proves nothing (D-330). The models
  must be in `api/models` (`make models`; CI fetches them), checked before
  anything starts, with the worker's own refusal.

**The worker runs beside the API**, a child of this process (D-330): photo
moderation and the selfie's comparison are its jobs, and without it no photo is
ever approved, so T-4.8's completion refuses everyone. It is `python -m
app.workers` with this run's database, Redis and the settings above in its
environment, and a working directory outside `api/`, so the founder's `api/.env`
can't reach its `Settings` either. **It polls every 0.5 seconds, not D-091's
10:** D-091's interval is Upstash's per-command price on the deployed Redis;
this Redis is Docker's and free, and at 10 seconds every run would wait that
long on each photo for nothing. The wake (D-261) still decides the selfie.

The fake SMS keeps its outbox in this process, which is why it's one uvicorn
worker: the test-only `/v1/test/sms/last-code` reads it there (`app/modules/e2e/`).

**Each browser context is a client of its own (P-680, D-890).** Every journey
reaches this API from one socket address, 127.0.0.1, so read from the socket
they would share D-066's 20 OTP sends an hour, and the suite outgrew them. The
per-IP limits here read `E2E_CLIENT_IP_HEADER` instead, which `web/e2e/
fixtures.ts` sets to an address of each context's own on its requests to this
API: each person in a journey is a client, as on the phone, and the limit stays
D-066's. A request without it shares one bucket (D-056), as on Fly. Only ENV
local may read such a header: a deployed build reads Fly-Client-IP and nothing
else (`PROXY_CLIENT_IP_HEADERS`), and this file is never in the image.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

import uvicorn
from alembic.config import Config

from alembic import command
from tests.infra import API_DIR, LOCAL_S3_URL, RUN_SLOT, S3_DOWN_REASON, S3_UP

if TYPE_CHECKING:
    from app.core.config import Settings

# Where Playwright's webServer and the web build expect them (web/playwright.config.ts).
API_PORT = 8100
WEB_ORIGIN = "http://127.0.0.1:3100"
# Each browser context's own client address, set by web/e2e/fixtures.ts (D-890).
E2E_CLIENT_IP_HEADER: Final = "X-E2E-Client-IP"

# The local S3's buckets and development credentials, as `api/.env.example` and
# `infra/s3/s3.json` have them: public by design, local and CI only (D-086),
# which is why the secret's line carries gitleaks' allow marker.
STORAGE: Final[Mapping[str, str]] = {
    "STORAGE_PROVIDER": "s3",
    "R2_ENDPOINT_URL": LOCAL_S3_URL,
    "R2_ACCESS_KEY_ID": "velora-local",
    "R2_SECRET_ACCESS_KEY": "velora-local-secret",  # gitleaks:allow
    "R2_BUCKET_PUBLIC": "velora-public",
    "R2_BUCKET_PRIVATE": "velora-private",
    "PUBLIC_CDN_URL": f"{LOCAL_S3_URL}/velora-public",
}

PROVIDERS: Final[Mapping[str, str]] = {
    "AUTH_PHONE_PROVIDER": "fake",
    "SMS_PROVIDER": "fake",
    "PAYMENTS_PROVIDER": "fake",
    "MODERATION_PROVIDER": "fake",
    "FACEMATCH_PROVIDER": "sface",
    "PUSH_PROVIDER": "fake",
}

# The worker's look at the queue, for this run alone: see the module's docstring.
WORKER_POLL_DELAY_S: Final = "0.5"
# How long the worker gets to stop once the API has.
WORKER_STOP_S: Final = 10


def shared_settings() -> dict[str, str]:
    """Every setting the API and the worker must agree on, as the environment
    the worker reads and the keyword arguments the API's `Settings` takes."""
    from app.core.config import PUBLIC_TEST_KEYS

    assert RUN_SLOT is not None
    return {
        "ENV": "local",
        "DATABASE_URL": RUN_SLOT.database_url,
        "REDIS_URL": RUN_SLOT.redis_url,
        **PUBLIC_TEST_KEYS,
        **PROVIDERS,
        **STORAGE,
        "WORKER_POLL_DELAY_S": WORKER_POLL_DELAY_S,
    }


def e2e_settings(shared: Mapping[str, str]) -> Settings:
    """The API's settings: the shared ones, the web's origin, and the client's
    address from each browser context's header (D-890). Never from `.env`."""
    from app.core.config import Settings

    return Settings(
        _env_file=None,
        CORS_ORIGINS=[WEB_ORIGIN],
        CLIENT_IP_HEADER=E2E_CLIENT_IP_HEADER,
        **shared,  # type: ignore[arg-type]
    )


def start_worker(shared: Mapping[str, str]) -> subprocess.Popen[bytes]:
    """`python -m app.workers` on this run's slot. `app` isn't installed into
    the venv, so `PYTHONPATH` names `api/`; the working directory is `tests/`,
    which has no `.env`, so nothing but this environment reaches its settings.
    Its stdout and stderr are this process's, which Playwright keeps or shows,
    unbuffered so a line is there when it happens, not at exit."""
    return subprocess.Popen(
        [sys.executable, "-m", "app.workers"],
        cwd=API_DIR / "tests",
        env={
            **os.environ,
            **shared,
            "PYTHONPATH": str(API_DIR),
            "PYTHONUNBUFFERED": "1",
        },
    )


def stop_worker(worker: subprocess.Popen[bytes]) -> None:
    """Stop the worker, once; safe to call again."""
    if worker.poll() is not None:
        return
    worker.terminate()
    try:
        worker.wait(timeout=WORKER_STOP_S)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait()


def stop_worker_with_this_process(worker: subprocess.Popen[bytes]) -> None:
    """When this process is told to stop, the worker goes first.

    uvicorn takes SIGINT and SIGTERM for its graceful shutdown, then puts the
    handlers it found back and raises the signal again, so the process ends
    the way it was told to (its `capture_signals`). A `finally` after
    `uvicorn.run` never runs on that path; this handler, the one it finds and
    puts back, does: it stops the worker, then lets the signal end the process
    as it would have. Playwright stops the API this way at the end of a run."""

    def handle(signum: int, frame: object) -> None:
        stop_worker(worker)
        signal.signal(signum, signal.SIG_DFL)
        signal.raise_signal(signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, handle)


def main() -> None:
    if RUN_SLOT is None:
        sys.exit(
            "e2e: Postgres or Redis isn't reachable. Start them with `make infra-up`."
        )
    if not S3_UP:
        sys.exit(f"e2e: {S3_DOWN_REASON}: the journeys upload photos to it (T-4.9).")
    shared = shared_settings()
    os.environ.update(shared)
    from app.main import create_app
    from app.workers.main import WorkerMisconfigured, refuse_unless_ready

    settings = e2e_settings(shared)
    try:
        # The worker's own check, here, so a missing model stops the run now,
        # not as a journey waiting on a selfie that is never compared.
        refuse_unless_ready(settings)
    except WorkerMisconfigured as refusal:
        sys.exit(f"e2e: {refusal}")
    alembic = Config(str(API_DIR / "alembic.ini"))
    alembic.set_main_option("sqlalchemy.url", RUN_SLOT.database_url)
    command.upgrade(alembic, "head")
    sys.stderr.write(
        f"e2e: slot {RUN_SLOT.number}, API on http://127.0.0.1:{API_PORT}, "
        "the worker beside it\n"
    )
    app = create_app(settings)
    # The fake SMS echoes codes to the terminal for a developer; here the
    # terminal is CI's log, and an OTP never goes in a log (rule 15).
    app.state.providers.sms.echo = False
    worker = start_worker(shared)
    stop_worker_with_this_process(worker)
    try:
        uvicorn.run(app, host="127.0.0.1", port=API_PORT, workers=1)
    finally:
        # uvicorn returning on its own (the port taken, say): the signal path
        # above never ran.
        stop_worker(worker)


if __name__ == "__main__":
    main()
