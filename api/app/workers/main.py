"""The ARQ worker (T-4.4): `make worker` locally, `python -m app.workers`.

It runs the jobs the API queues (02-ARCHITECTURE §7), from the same image and
the same `Settings` as the API, as the same least-privilege database role. Its
context holds what the jobs need: `settings`, `sessionmaker`, `storage`,
`moderation`, `facematch` and `queue` (for jobs that queue a later try of
themselves).

- **It polls every `WORKER_POLL_DELAY_S`, 10 seconds** (D-091): on Upstash's
  Free plan that is 260,640 commands a month idle; ARQ's default 0.5 seconds
  would be over five million. The health key is written once an hour, the sum
  D-091 counted; abort and cron are off.
- **A wake runs `verify_selfie` at once** (D-261): a listener on a Redis
  channel of its own (`app/workers/wake.py`), started with the worker, so a
  woman's selfie is decided in seconds, not at the next look at the queue. The
  queued job stays the path that is sure to run.
- **It refuses to start** without what its jobs need: Sightengine's two keys
  where `MODERATION_PROVIDER` is `sightengine` (the API never moderates, so it
  needs neither), and both face models, exactly D-088's, where
  `FACEMATCH_PROVIDER` is `sface`. `Settings` has already refused anything
  else.
- **Logs keep rule 15.** ARQ logs each job's arguments as it starts it, and
  `delete_files`' arguments are storage keys: the worker logs the job's name and
  id instead. Its engine keeps query values out of errors (`hide_parameters`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from collections.abc import MutableMapping, Sequence
from typing import Any, Final
from uuid import UUID

import structlog
from arq import func
from arq.connections import RedisSettings
from arq.worker import Function, run_worker

from app.core import facemodels
from app.core.config import Settings, get_settings
from app.core.db import build_engine, build_sessionmaker
from app.core.logging import configure_logging
from app.core.providers import Providers, build_providers
from app.core.queue import (
    DELETE_FILES,
    MATCH_PHOTO,
    MODERATE_PHOTO,
    VERIFY_SELFIE,
    ArqQueue,
)
from app.workers.tasks import verify_selfie as verify_selfie_job
from app.workers.tasks.delete_files import delete_files
from app.workers.tasks.match_photo import MATCH_TRIES, match_photo
from app.workers.tasks.moderate_photo import MODERATE_TRIES, moderate_photo
from app.workers.wake import WakeListener, connect_to

log = structlog.get_logger(__name__)

JOBS: Final[Sequence[Function]] = (
    func(moderate_photo, name=MODERATE_PHOTO, max_tries=MODERATE_TRIES),
    func(delete_files, name=DELETE_FILES),
    func(
        verify_selfie_job.verify_selfie,
        name=VERIFY_SELFIE,
        max_tries=verify_selfie_job.VERIFY_TRIES,
    ),
    # T-4.12, D-393: a shown photo's face against the kept selfie, for the badge.
    func(match_photo, name=MATCH_PHOTO, max_tries=MATCH_TRIES),
)
# Jobs at once. Decoding is synchronous on the event loop, so only one image is
# ever decoded at a time, whatever this says (D-092, D-088's 1 GB); the others
# wait on storage or Sightengine, each holding a database session only briefly.
MAX_JOBS: Final = 4
# A job past this is cancelled and tried again: reading 8 MB, decoding and
# Sightengine's 30-second timeout fit well inside it.
JOB_TIMEOUT_S: Final = 120
HEALTH_CHECK_INTERVAL_S: Final = 3600  # once an hour: D-091's sum


class WorkerMisconfigured(Exception):
    """Something a job needs is missing. Names the settings, never a value."""


def refuse_unless_ready(settings: Settings) -> None:
    if settings.FACEMATCH_PROVIDER == "sface":
        wrong = facemodels.problems()
        if wrong:
            raise WorkerMisconfigured(
                f"FACEMATCH_PROVIDER=sface needs both face models: {'; '.join(wrong)}. "
                "The image fetches them; locally, `make models` (D-088)."
            )
    if settings.MODERATION_PROVIDER == "sightengine":
        missing = [
            name
            for name in ("SIGHTENGINE_API_USER", "SIGHTENGINE_API_SECRET")
            if not getattr(settings, name)
        ]
        if missing:
            raise WorkerMisconfigured(
                f"MODERATION_PROVIDER=sightengine needs {', '.join(missing)}: the "
                "worker scores every photo with them (infra/STAGING.md §4)."
            )


def redis_settings(settings: Settings) -> RedisSettings:
    """ARQ's connection to the API's Redis, TLS where the URL says rediss://."""
    return RedisSettings.from_dsn(settings.REDIS_URL)


async def open_resources(
    ctx: MutableMapping[str, Any], settings: Settings, providers: Providers
) -> None:
    engine = build_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        hide_parameters=True,
    )
    ctx.update(
        settings=settings,
        engine=engine,
        sessionmaker=build_sessionmaker(engine),
        # ARQ's own pool, so queuing opens no connections of its own.
        queue=ArqQueue(ctx["redis"]),
        storage=providers.storage,
        moderation=providers.moderation,
        facematch=providers.facematch,
    )
    # The models are read now, once, not at the first selfie.
    providers.facematch.load()


async def startup(ctx: MutableMapping[str, Any]) -> None:
    settings = get_settings()
    refuse_unless_ready(settings)
    await open_resources(ctx, settings, build_providers(settings))
    ctx["wake"] = asyncio.create_task(listen_for_wakes(ctx, settings).run())
    log.info(
        "worker.started",
        jobs=[job.name for job in JOBS],
        poll_delay_s=settings.WORKER_POLL_DELAY_S,
        env=settings.ENV,
    )


def listen_for_wakes(ctx: MutableMapping[str, Any], settings: Settings) -> WakeListener:
    async def handle(verification_id: UUID) -> object:
        return await verify_selfie_job.run(ctx, verification_id, via="wake")

    return WakeListener(connect_to(settings.REDIS_URL), handle)


async def shutdown(ctx: MutableMapping[str, Any]) -> None:
    """Release what `startup` opened. Safe if it never ran."""
    if "wake" in ctx:
        ctx["wake"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ctx["wake"]
    if "engine" in ctx:
        await ctx["engine"].dispose()
    for name in ("storage", "moderation"):
        if name in ctx:
            await ctx[name].aclose()


class WorkerSettings:
    """What `run_worker` reads. The Redis connection and the poll delay come
    from `Settings` at run time (`worker_options`)."""

    functions = JOBS
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = MAX_JOBS
    job_timeout = JOB_TIMEOUT_S
    health_check_interval = HEALTH_CHECK_INTERVAL_S
    allow_abort_jobs = False


def worker_options(settings: Settings) -> dict[str, Any]:
    return {
        "redis_settings": redis_settings(settings),
        "poll_delay": settings.WORKER_POLL_DELAY_S,
    }


# ARQ's "job started" line, `'%6.2fs → %s(%s)%s'`: its third argument is the
# job's arguments, written out.
_JOB_STARTED = "%6.2fs → %s(%s)%s"


class HideJobArguments(logging.Filter):
    """Rule 15: ARQ writes a job's arguments into its "started" line, and
    `delete_files`' are storage keys. Replaced with a mark; the line keeps the
    job's name, id and timing."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg == _JOB_STARTED and isinstance(record.args, tuple):
            waited, ref, _, extra = record.args
            record.args = (waited, ref, "…", extra)
        return True


def hide_job_arguments() -> None:
    logger = logging.getLogger("arq.worker")
    if not any(isinstance(f, HideJobArguments) for f in logger.filters):
        logger.addFilter(HideJobArguments())


def main(argv: Sequence[str] = ()) -> int:
    """Check the settings, then run until stopped. `--check` checks and exits:
    0 when the worker would start, 2 when it wouldn't, saying why."""
    settings = get_settings()
    try:
        refuse_unless_ready(settings)
    except WorkerMisconfigured as refusal:
        sys.stderr.write(f"worker: refused. {refusal}\n")
        return 2
    if "--check" in argv:
        sys.stderr.write("worker: settings ready.\n")
        return 0
    configure_logging(json_logs=not settings.debug)
    hide_job_arguments()
    run_worker(WorkerSettings, **worker_options(settings))  # type: ignore[arg-type]
    return 0
