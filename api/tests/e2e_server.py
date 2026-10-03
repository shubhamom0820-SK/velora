"""The API for the E2E (T-3.13): `uv run python -m tests.e2e_server`.

Importing `tests.infra` takes a P-55 slot, so this run has a database and a
Redis database of its own, created empty: an E2E run and any number of pytest
runs never meet, and a run starts with no accounts, bans or rate-limit windows
left by the last. The slot is held until this process ends.

Local only, by construction: `ENV=local` and every provider the fake. The
fake SMS keeps its outbox in this process, which is why it's one worker: the
test-only `/v1/test/sms/last-code` reads it there (`app/modules/e2e/`).
"""

from __future__ import annotations

import os
import sys

import uvicorn
from alembic.config import Config

from alembic import command
from tests.infra import API_DIR, RUN_SLOT

# Where Playwright's webServer and the web build expect them (web/playwright.config.ts).
API_PORT = 8100
WEB_ORIGIN = "http://127.0.0.1:3100"


def main() -> None:
    if RUN_SLOT is None:
        sys.exit(
            "e2e: Postgres or Redis isn't reachable. Start them with `make infra-up`."
        )
    os.environ["DATABASE_URL"] = RUN_SLOT.database_url
    os.environ["REDIS_URL"] = RUN_SLOT.redis_url
    os.environ["ENV"] = "local"
    from app.core.config import PUBLIC_TEST_KEYS, Settings
    from app.main import create_app

    settings = Settings(
        _env_file=None,
        ENV="local",
        DATABASE_URL=RUN_SLOT.database_url,
        REDIS_URL=RUN_SLOT.redis_url,
        CORS_ORIGINS=[WEB_ORIGIN],
        AUTH_PHONE_PROVIDER="fake",
        SMS_PROVIDER="fake",
        **PUBLIC_TEST_KEYS,  # type: ignore[arg-type]
    )
    alembic = Config(str(API_DIR / "alembic.ini"))
    alembic.set_main_option("sqlalchemy.url", RUN_SLOT.database_url)
    command.upgrade(alembic, "head")
    sys.stderr.write(
        f"e2e: slot {RUN_SLOT.number}, API on http://127.0.0.1:{API_PORT}\n"
    )
    app = create_app(settings)
    # The fake SMS echoes codes to the terminal for a developer; here the
    # terminal is CI's log, and an OTP never goes in a log (rule 15).
    app.state.providers.sms.echo = False
    uvicorn.run(app, host="127.0.0.1", port=API_PORT, workers=1)


if __name__ == "__main__":
    main()
