"""Kudos (T-8.5, D-007, D-680): one of four fixed positive notes, given once
ever to someone you have talked with, shown only as counts by kind and only
where the recipient allows (`show_kudos`, read by the public profile). Never
who gave it.

"Talked with" (D-680): the pair's Thread has `kudos_min_messages` messages
and each of the two has written at least one. Its status doesn't matter: an
expired Thread was still a conversation.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Kudos as KudosKind
from app.core.enums import UserStatus
from app.core.errors import AppError
from app.modules.admin import service as admin_service
from app.modules.kudos import repository
from app.modules.kudos.schemas import GiveKudosRequest, Kudos, KudosGiven, KudosState
from app.modules.threads.models import Thread
from app.modules.users.models import User

MIN_MESSAGES_KEY = "kudos_min_messages"


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


def _too_early() -> AppError:
    return AppError(
        "NOT_ALLOWED",
        "Talk a little more first.",
        status=422,
        details={"why": "too_early"},
    )


async def _talked(
    session: AsyncSession,
    thread: Thread,
    a: UUID,
    b: UUID,
    *,
    config: admin_service.ConfigCache | None,
) -> bool:
    """D-680's "talked with", the one rule `give` and `state` both read: the
    pair's Thread has `kudos_min_messages` messages and each has written."""
    least = await admin_service.config_int(session, MIN_MESSAGES_KEY, cache=config)
    if thread.message_count < least:
        return False
    for writer in (a, b):
        if not await repository.has_written(session, thread.id, writer):
            return False
    return True


async def state(
    session: AsyncSession,
    viewer_id: UUID,
    other_id: UUID,
    thread: Thread,
    *,
    config: admin_service.ConfigCache | None = None,
) -> KudosState:
    """Whether `viewer_id` may give `other_id` kudos in their `thread`, in the
    caller's transaction (D-790): `given` once they have, whatever its kind;
    `too_early` until they have talked (D-680); else `can_give`. Kudos the
    other way is the other person's own and changes nothing here."""
    if await repository.given(session, viewer_id, other_id):
        return "given"
    if not await _talked(session, thread, viewer_id, other_id, config=config):
        return "too_early"
    return "can_give"


async def give(
    session: AsyncSession,
    user: User,
    request: GiveKudosRequest,
    *,
    config: admin_service.ConfigCache | None = None,
) -> KudosGiven:
    """`request.kind` from `user` to `request.to_id`, once ever.

    No Thread between them, a block either way, an id nobody holds or your
    own are all `NOT_FOUND`, one body; a deleted account gets nothing more
    (D-555); a conversation too short, or one-sided, is `NOT_ALLOWED`; a
    second kudos to the same person, whatever its kind, `ALREADY_EXISTS`.
    """
    user_id = user.id
    async with session.begin():
        thread = await repository.thread_between(session, user_id, request.to_id)
        if thread is None:
            raise _not_found()
        if await repository.status_of(session, request.to_id) is UserStatus.DELETED:
            raise AppError("ACCOUNT_DELETED", "They deleted their account.", status=410)
        if not await _talked(session, thread, user_id, request.to_id, config=config):
            raise _too_early()
        created_at = await repository.add(
            session,
            from_id=user_id,
            to_id=request.to_id,
            kind=request.kind,
            thread_id=thread.id,
        )
        if created_at is None:
            raise AppError(
                "ALREADY_EXISTS", "You've already given them kudos.", status=409
            )
    return KudosGiven(to_id=request.to_id, kind=request.kind, created_at=created_at)


async def mine(session: AsyncSession, user: User) -> list[Kudos]:
    """The kinds `user` was given, each with how many gave it, in the kinds'
    own order; whether they show them or not, since they're theirs."""
    async with session.begin():
        counts = await repository.received(session, user.id)
    return [
        Kudos(kind=kind, count=counts[kind]) for kind in KudosKind if kind in counts
    ]
