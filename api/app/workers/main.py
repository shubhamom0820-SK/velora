"""The ARQ worker (T-4.4): `make worker` locally, `python -m app.workers`.

It runs the jobs the API queues (02-ARCHITECTURE §7), from the same image and
the same `Settings` as the API, as the same least-privilege database role. Its
context holds what the jobs need: `settings`, `sessionmaker`, `storage`,
`moderation`, `facematch` and `queue` (for jobs that queue a later try of
themselves).

- **It polls every `WORKER_POLL_DELAY_S`, 10 seconds** (D-091): on Upstash's
  Free plan that is 260,640 commands a month idle; ARQ's default 0.5 seconds
  would be over five million. The health key is written once an hour, the sum
  D-091 counted; abort is off.
- **Three crons, each once a day:** `reconcile_ledger` (T-9.9, D-940),
  `log_turnover` (D-483) and `erase_accounts` (T-9.6, D-500). ARQ checks their
  schedules in the heartbeat each poll already makes, so each adds a job's few
  commands a day, nothing per poll. Schedules are in UTC, whatever the
  machine's clock says.
- **The Thread's clock runs once a minute in the worker's own loop**
  (`app/workers/minutely.py`, D-640, T-7.6): `expire_threads` and
  `warn_expiring`, coordinated in Postgres, so they cost Redis nothing but the
  events they publish. An ARQ cron every minute would be about 864,000
  commands a month, over Free on its own.
- **A wake runs `verify_selfie` at once** (D-261): a listener on a Redis
  channel of its own (`app/workers/wake.py`), started with the worker, so a
  woman's selfie is decided in seconds, not at the next look at the queue. The
  queued job stays the path that is sure to run.
- **Fraud scoring runs every 10 minutes in a loop of its own** (T-9.2,
  `recompute_fraud`), the minute's kind of loop, coordinated in Postgres, so it
  costs Redis nothing but the sockets a freeze closes.
- **Pushes are sent from `push_outbox`, never as ARQ jobs** (T-9.4, D-850): a
  second listener, on `wake:send_push`, sends them the moment a notification
  commits, and the worker's minute sends any a lost wake left. An ARQ job a
  push would cost about 20 commands each, more than Free has for them.
- **It refuses to start** without what its jobs need: Sightengine's two keys
  where `MODERATION_PROVIDER` is `sightengine` (the API never moderates, so it
  needs neither), and both face models, exactly D-088's, where
  `FACEMATCH_PROVIDER` is `sface`. `Settings` has already refused anything
  else.
- **A job's events are published** (P-592): `sessionmaker` hands out sessions
  that publish their committed events once closed, as `get_session` does a
  request's, so a credit or a decision made here reaches the person's sockets.
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
from datetime import UTC
from typing import Any, Final
from uuid import UUID

import structlog
from arq import func
from arq.connections import RedisSettings
from arq.cron import CronJob, cron
from arq.worker import Function, run_worker

from app.core import facemodels
from app.core.config import Settings, get_settings
from app.core.db import build_engine, build_sessionmaker, publishing
from app.core.logging import configure_logging
from app.core.providers import Providers, build_providers
from app.core.queue import (
    BLUR_PHOTO,
    DELETE_FILES,
    ERASE_ACCOUNTS,
    EXPIRE_EXPORT,
    EXPORT_DATA,
    LOG_TURNOVER,
    MATCH_PHOTO,
    MODERATE_PHOTO,
    RECONCILE_LEDGER,
    SEND_PUSH,
    VERIFY_SELFIE,
    WATERMARK_ALBUM,
    ArqQueue,
    wake_channel,
)
from app.workers.minutely import Minutely
from app.workers.tasks import log_turnover as log_turnover_job
from app.workers.tasks import recompute_fraud, send_push, thread_clock
from app.workers.tasks import reconcile_ledger as reconcile_ledger_job
from app.workers.tasks import verify_selfie as verify_selfie_job
from app.workers.tasks.blur_photo import BLUR_TRIES, blur_photo
from app.workers.tasks.delete_files import delete_files
from app.workers.tasks.erase_accounts import erase_accounts
from app.workers.tasks.expire_export import EXPIRE_TRIES, expire_export
from app.workers.tasks.export_data import EXPORT_TRIES, export_data
from app.workers.tasks.match_photo import MATCH_TRIES, match_photo
from app.workers.tasks.moderate_photo import MODERATE_TRIES, moderate_photo
from app.workers.tasks.watermark_album import WATERMARK_TRIES, watermark_album
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
    # T-6.7, D-543: an approved public photo's blurred copy, for Liked you.
    func(blur_photo, name=BLUR_PHOTO, max_tries=BLUR_TRIES),
    # T-9.6, D-502: a user's own data, and its file deleted 24 hours on.
    func(export_data, name=EXPORT_DATA, max_tries=EXPORT_TRIES),
    func(expire_export, name=EXPIRE_EXPORT, max_tries=EXPIRE_TRIES),
    # T-8.4, D-730: a granted album request's watermarked copies, made or deleted.
    func(watermark_album, name=WATERMARK_ALBUM, max_tries=WATERMARK_TRIES),
)
# T-9.6, D-500: erasing deleted accounts, at 22:00 UTC, which is 03:30 IST.
# One run at a time across workers (`unique`), and a timeout of its own: it goes
# through every account due, one by one.
ERASE_AT_UTC: Final = (22, 0)
ERASE_TIMEOUT_S: Final = 1800
# Once a day each, in UTC (`WorkerSettings.timezone`).
CRON_JOBS: Final[Sequence[CronJob]] = (
    cron(
        reconcile_ledger_job.reconcile_ledger,
        name=RECONCILE_LEDGER,
        hour=reconcile_ledger_job.RUN_AT_UTC[0],
        minute=reconcile_ledger_job.RUN_AT_UTC[1],
    ),
    cron(
        log_turnover_job.log_turnover,
        name=LOG_TURNOVER,
        hour=log_turnover_job.RUN_AT_UTC[0],
        minute=log_turnover_job.RUN_AT_UTC[1],
    ),
    cron(
        erase_accounts,
        name=ERASE_ACCOUNTS,
        hour=ERASE_AT_UTC[0],
        minute=ERASE_AT_UTC[1],
        timeout=ERASE_TIMEOUT_S,
        max_tries=1,
    ),
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
        # Each job's committed events published as its session closes, as a
        # request's are (P-592): a reward credited here moves the balance.
        sessionmaker=publishing(build_sessionmaker(engine), ctx["redis"]),
        # ARQ's own pool, so queuing opens no connections of its own.
        queue=ArqQueue(ctx["redis"]),
        storage=providers.storage,
        moderation=providers.moderation,
        facematch=providers.facematch,
        push=providers.push,
    )
    # The models are read now, once, not at the first selfie.
    providers.facematch.load()


async def startup(ctx: MutableMapping[str, Any]) -> None:
    settings = get_settings()
    refuse_unless_ready(settings)
    await open_resources(ctx, settings, build_providers(settings))
    ctx["wake"] = asyncio.create_task(listen_for_wakes(ctx, settings).run())
    ctx["push_wake"] = asyncio.create_task(listen_for_pushes(ctx, settings).run())
    ctx["minutely"] = asyncio.create_task(each_minute(ctx).run())
    ctx["fraud"] = asyncio.create_task(every_ten_minutes(ctx).run())
    log.info(
        "worker.started",
        jobs=[job.name for job in JOBS],
        cron=[job.name for job in CRON_JOBS],
        minutely=[THREAD_CLOCK, SEND_PUSH],
        every_ten_minutes=[RECOMPUTE_FRAUD],
        poll_delay_s=settings.WORKER_POLL_DELAY_S,
        env=settings.ENV,
    )


def listen_for_wakes(ctx: MutableMapping[str, Any], settings: Settings) -> WakeListener:
    async def handle(verification_id: UUID) -> object:
        return await verify_selfie_job.run(ctx, verification_id, via="wake")

    return WakeListener(connect_to(settings.REDIS_URL), handle)


def listen_for_pushes(
    ctx: MutableMapping[str, Any], settings: Settings
) -> WakeListener:
    """T-9.4 (D-850): a wake names the user a push waits for; every waiting
    push is sent, whoever's."""

    async def handle(_user_id: UUID) -> object:
        return await send_push.run(ctx)

    return WakeListener(
        connect_to(settings.REDIS_URL),
        handle,
        channel=wake_channel(SEND_PUSH),
        id_name="user_id",
    )


# The worker's minute (D-640): the Thread's clock (T-7.6), then any push a lost
# wake left waiting (T-9.4), the clock's own warnings among them.
THREAD_CLOCK: Final = "thread_clock"


def each_minute(ctx: MutableMapping[str, Any]) -> Minutely:
    async def work() -> dict[str, int]:
        clock_done = await thread_clock.run(ctx)
        pushed = await send_push.run(ctx)
        return {**clock_done, **{f"push_{name}": n for name, n in pushed.items()}}

    return Minutely(work, name=THREAD_CLOCK)


# T-9.2: fraud scoring, every 10 minutes (02-ARCHITECTURE §7), in its own loop.
RECOMPUTE_FRAUD: Final = "recompute_fraud"


def every_ten_minutes(ctx: MutableMapping[str, Any]) -> Minutely:
    async def work() -> dict[str, int]:
        return await recompute_fraud.run(ctx)

    return Minutely(work, name=RECOMPUTE_FRAUD, every_s=recompute_fraud.EVERY_S)


async def shutdown(ctx: MutableMapping[str, Any]) -> None:
    """Release what `startup` opened. Safe if it never ran."""
    for task in ("minutely", "fraud", "wake", "push_wake"):
        if task in ctx:
            ctx[task].cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ctx[task]
    if "engine" in ctx:
        await ctx["engine"].dispose()
    for name in ("storage", "moderation", "push"):
        if name in ctx:
            await ctx[name].aclose()


class WorkerSettings:
    """What `run_worker` reads. The Redis connection and the poll delay come
    from `Settings` at run time (`worker_options`)."""

    functions = JOBS
    cron_jobs = CRON_JOBS
    # Cron schedules read this, not the machine's zone: a Mac in IST and Fly in
    # UTC would otherwise run the same cron five and a half hours apart.
    timezone = UTC
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
