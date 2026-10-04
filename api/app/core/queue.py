"""Background jobs, the API's side (T-4.2): putting a job on ARQ's queue.

The worker that runs them arrives with T-4.4 (`app/workers/`); until it does,
a queued job waits in Redis. Jobs are named here, once, so the API and the
worker can't disagree about a name. Every job is idempotent and safe to retry
(02-ARCHITECTURE §7); a job id makes queuing the same work twice a no-op.

The queue shares the app's Redis connection pool (`app.state.redis`), so it
opens no connections of its own. Tests install a `FakeQueue`, which records
what was queued and runs nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Protocol

from arq.connections import ArqRedis
from fastapi import Request
from redis.asyncio import Redis

MODERATE_PHOTO = "moderate_photo"
DELETE_FILES = "delete_files"
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


@dataclass(frozen=True)
class QueuedJob:
    job: str
    job_id: str | None
    defer_by: timedelta | None
    kwargs: dict[str, Any]


@dataclass
class FakeQueue:
    """Records every job queued; `fail = True` makes the next `enqueue` raise,
    as Redis being down would."""

    jobs: list[QueuedJob] = field(default_factory=list)
    fail: bool = False

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

    def named(self, job: str) -> list[QueuedJob]:
        return [q for q in self.jobs if q.job == job]


def get_queue(request: Request) -> Queue:
    """FastAPI dependency: the queue this app was built with."""
    queue: Queue = request.app.state.queue
    return queue
