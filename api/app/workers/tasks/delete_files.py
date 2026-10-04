"""`delete_files`: an under-18 refusal's files, deleted once the user is gone
(D-078, in D-090's order; T-4.2).

The refusal queues this before it commits, with the keys it read before the rows
went. So the job can't tell, by being run, whether the refusal committed: it
asks. A user who is gone was refused, and their files go. A user still there
60 seconds on is asked about once more, 4 minutes later, in case the refusal's
transaction was slow; still there then, the refusal rolled back, and nothing is
deleted: the guard that keeps a photo of someone never refused.

A delete that answers success isn't proof the object left: each one is read
back, and the job succeeds only if every one is gone; storage that fails to
answer counts as not gone. It tries 4 times in all;
the last failure is logged at error level. Logs name the refusal's record, the
`banned_identities` row, by its id: never a key, a signed URL or a number
(rule 15).

The worker's context carries `sessionmaker`, `storage` and `queue`; T-4.4's
`WorkerSettings` builds them, and tests pass their own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog

from app.core.providers.storage import ObjectNotFound, StorageProvider
from app.core.queue import DELETE_FILES, Queue
from app.modules.users import service as users_service

log = structlog.get_logger(__name__)

SECOND_CHECK = timedelta(minutes=4)  # with the first's minute, 5 after the refusal
RETRY_DELETE_IN = timedelta(minutes=1)
DELETE_TRIES = 4  # the first, and three more (D-090)


async def delete_files(
    ctx: Mapping[str, Any],
    *,
    user_id: str,
    banned_id: str,
    objects: Sequence[Sequence[str]],
    check: int = 1,
    delete_try: int = 1,
) -> str:
    queue: Queue = ctx["queue"]
    storage: StorageProvider = ctx["storage"]
    async with ctx["sessionmaker"]() as session:
        present = await users_service.account_exists(session, UUID(user_id))

    def again(**changed: Any) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "banned_id": banned_id,
            "objects": objects,
            "check": check,
            "delete_try": delete_try,
            **changed,
        }

    if present:
        if check == 1:
            await queue.enqueue(DELETE_FILES, defer_by=SECOND_CHECK, **again(check=2))
            log.info("storage.delete_waiting", banned_id=banned_id)
            return "the user is still there: asking again"
        log.info("storage.delete_skipped", banned_id=banned_id)
        return "the refusal rolled back: nothing deleted"

    for bucket, key in objects:
        try:
            await storage.delete(bucket, key)
        except Exception:  # noqa: BLE001, S112 — the read-back below decides
            continue
    remaining = [obj for obj in objects if not await _gone(storage, obj)]
    if not remaining:
        log.info("storage.files_deleted", banned_id=banned_id, files=len(objects))
        return "deleted"
    if delete_try < DELETE_TRIES:
        await queue.enqueue(
            DELETE_FILES, defer_by=RETRY_DELETE_IN, **again(delete_try=delete_try + 1)
        )
        log.warning(
            "storage.delete_retrying",
            banned_id=banned_id,
            remaining=len(remaining),
            delete_try=delete_try,
        )
        return "some are still there: trying again"
    log.error("storage.delete_failed", banned_id=banned_id, remaining=len(remaining))
    return "failed"


async def _gone(storage: StorageProvider, obj: Sequence[str]) -> bool:
    bucket, key = obj
    try:
        await storage.head(bucket, key)
    except ObjectNotFound:
        return True
    except Exception:  # noqa: BLE001 — unreadable is not proof it left
        return False
    return False
