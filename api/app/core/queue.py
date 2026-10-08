"""Background jobs, the API's side (T-4.2): putting a job on ARQ's queue.

The worker that runs them arrives with T-4.4 (`app/workers/`); until it does,
a queued job waits in Redis. Jobs are named here, once, so the API and the
worker can't disagree about a name. Every job is idempotent and safe to retry
(02-ARCHITECTURE §7); a job id makes queuing the same work twice a no-op.

The queue shares the app's Redis connection pool (`app.state.redis`), so it
opens no connections of its own. Tests install a `FakeQueue`, which records
what was queued and runs nothing.

**A wake** (D-261, T-4.5) tells the worker a queued job is waiting now, for the
one job a person waits on: `verify_selfie`. It is a Redis PUBLISH, sent after
the job's transaction commits, which the worker hears at once instead of at its
next look at the queue, 10 seconds apart (D-091). It only makes the job sooner:
the queued job is still the one that is sure to run, so a wake that is lost
costs those 10 seconds, never the job. A failed or hung wake (1 second) is
logged and never fails the request.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Protocol

import structlog
from arq.connections import ArqRedis
from fastapi import Request
from redis.asyncio import Redis

log = structlog.get_logger(__name__)

MODERATE_PHOTO = "moderate_photo"
DELETE_FILES = "delete_files"
VERIFY_SELFIE = "verify_selfie"
LOG_TURNOVER = "log_turnover"  # a cron, never queued by the API (T-8.1)
# T-4.12, D-393: an approved public photo with a face compared with the kept
# selfie, for the badge. Nobody waits on it, so it has no wake.
MATCH_PHOTO = "match_photo"
# T-6.7 (D-543): an approved public photo's blurred copy, for Liked you.
# Nobody waits on it, so it has no wake.
BLUR_PHOTO = "blur_photo"
# T-8.4 (D-730): a granted album request's watermarked copies, made or, once
# the request is revoked, deleted. Nobody waits on it, so it has no wake.
WATERMARK_ALBUM = "watermark_album"
# T-9.6 (D-502): a copy of a user's own data, written to the private bucket;
# and its file deleted when its link expires, 24 hours after it was ready.
EXPORT_DATA = "export_data"
EXPIRE_EXPORT = "expire_export"
# T-9.6 (D-500): the daily job, at 03:30 IST, that erases deleted accounts and
# deletes any export file its own job left behind. Run by the worker's cron.
ERASE_ACCOUNTS = "erase_accounts"
WAKE_TIMEOUT_S = 1.0


def wake_channel(job: str) -> str:
    """The Redis channel the worker listens on for `job`'s wakes."""
    return f"wake:{job}"


# D-090: a refusal's files are deleted 60 seconds after it is queued, before its
# commit, once the user is gone; still there then, it checks once more.
DELETE_FILES_FIRST_CHECK = timedelta(seconds=60)


class Queue(Protocol):
    async def enqueue(
        self,
        job: str,
        *,
        job_id: str | None = None,
        defer_by: timedelta | None = None,
        **kwargs: Any,
    ) -> None:
        """Queue `job` with keyword arguments. With `job_id`, a job already
        queued under that id isn't queued again."""
        ...

    async def wake(self, job: str, value: str) -> None:
        """Tell the worker `job` is waiting for `value` (an id, never a key or
        anything rule 15 keeps out of logs). Call it only after the queuing
        transaction has committed. Never raises."""
        ...


class ArqQueue:
    def __init__(self, redis: Redis) -> None:
        self._arq = ArqRedis(connection_pool=redis.connection_pool)

    async def enqueue(
        self,
        job: str,
        *,
        job_id: str | None = None,
        defer_by: timedelta | None = None,
        **kwargs: Any,
    ) -> None:
        await self._arq.enqueue_job(job, _job_id=job_id, _defer_by=defer_by, **kwargs)

    async def wake(self, job: str, value: str) -> None:
        try:
            await asyncio.wait_for(
                self._arq.publish(wake_channel(job), value), WAKE_TIMEOUT_S
            )
        except Exception as error:  # noqa: BLE001 — the queued job still runs
            log.warning("queue.wake_failed", job=job, error=type(error).__name__)


@dataclass(frozen=True)
class QueuedJob:
    job: str
    job_id: str | None
    defer_by: timedelta | None
    kwargs: dict[str, Any]


@dataclass
class FakeQueue:
    """Records every job queued and every wake; `fail = True` makes the next
    `enqueue` raise, as Redis being down would. `on_wake`, if set, runs at
    each wake, so a test can see what was true when it was sent."""

    jobs: list[QueuedJob] = field(default_factory=list)
    fail: bool = False
    woken: list[tuple[str, str]] = field(default_factory=list)
    on_wake: Callable[[], None] | None = None

    async def enqueue(
        self,
        job: str,
        *,
        job_id: str | None = None,
        defer_by: timedelta | None = None,
        **kwargs: Any,
    ) -> None:
        if self.fail:
            self.fail = False
            raise ConnectionError("the queue refused the job")
        if job_id is not None and any(q.job_id == job_id for q in self.jobs):
            return
        self.jobs.append(QueuedJob(job, job_id, defer_by, kwargs))

    async def wake(self, job: str, value: str) -> None:
        if self.on_wake is not None:
            self.on_wake()
        self.woken.append((job, value))

    def named(self, job: str) -> list[QueuedJob]:
        return [q for q in self.jobs if q.job == job]


def get_queue(request: Request) -> Queue:
    """FastAPI dependency: the queue this app was built with."""
    queue: Queue = request.app.state.queue
    return queue
