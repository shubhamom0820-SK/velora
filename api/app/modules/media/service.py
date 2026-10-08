"""A voice note's upload URL (T-7.9, D-620): a woman's alone (D-010), in a
Thread of hers.

The browser PUTs the recording straight to the private bucket (D-027); the
server never handles the bytes on the way in. What arrived is judged at the
send (`messages.service.check_voice`), by its bytes, never by this type.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audio
from app.core.config import Settings
from app.core.errors import AppError
from app.core.providers.storage import StorageProvider
from app.core.storage_keys import voice_upload_key
from app.modules.media.schemas import VoiceUpload
from app.modules.messages import repository as messages_repository
from app.modules.messages import rules as messages_rules
from app.modules.messages import service as messages_service
from app.modules.users.models import User

UPLOAD_TTL_S = 300  # D-027: a presigned PUT lasts 5 minutes


async def voice_upload_url(
    session: AsyncSession,
    user: User,
    thread_id: UUID,
    content_type: str,
    *,
    storage: StorageProvider,
    settings: Settings,
) -> VoiceUpload:
    """A place for one voice note in the Thread, and the URL to PUT it to.

    In order: a man, or anyone with no gender, `NOT_ALLOWED` (an allowlist);
    a type that isn't one of the three, `UNSUPPORTED_AUDIO`, the answer its
    bytes would get; a Thread that isn't hers, or across a block, `NOT_FOUND`.
    An expired Thread takes her messages (D-097), so it gives her a URL too.
    """
    if not messages_rules.may_send_voice(user.gender):
        raise AppError("NOT_ALLOWED", "That can't be sent here.", status=422)
    if content_type not in audio.ACCEPTED_TYPES:
        raise messages_service.unsupported_audio()
    kind = next(t for t in audio.ACCEPTED_TYPES if t == content_type)
    async with session.begin():
        thread = await messages_repository.thread_of(session, thread_id, user.id)
        if thread is None:
            raise AppError("NOT_FOUND", "Not found.", status=404)
    message_id = uuid4()
    key = voice_upload_key(thread_id, message_id, kind)
    signed = await storage.presign_put(
        settings.R2_BUCKET_PRIVATE,
        key,
        kind,
        messages_service.MAX_VOICE_BYTES,
        ttl=UPLOAD_TTL_S,
    )
    return VoiceUpload(
        message_id=message_id,
        media_key=key,
        put_url=signed.url,
        headers=dict(signed.headers),
    )
