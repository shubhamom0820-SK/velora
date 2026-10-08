"""Where each kind of file lives in storage (T-4.1): the keys, built here only.

Every part of a key is a UUID, so nothing a user types can shape one: no `..`,
no slash, no other user's prefix. Which bucket each goes in is the caller's,
by D-027: originals, selfies, album copies and voice notes in the private
bucket; approved public photos in the public one, served from `PUBLIC_CDN_URL`.
"""

from __future__ import annotations

import re
from typing import NamedTuple
from uuid import UUID

from app.core.audio import EXTENSION, AudioType
from app.core.config import Settings


def raw_key(user_id: UUID, photo_id: UUID) -> str:
    """An upload as the browser PUT it, in the private bucket (T-4.2)."""
    return f"raw/{_id(user_id)}/{_id(photo_id)}"


def scored_key(user_id: UUID, photo_id: UUID) -> str:
    """An approved private photo, re-encoded: the bytes moderation scored, in
    the private bucket, under a prefix no upload URL ever covers (P-79, D-700)."""
    return f"scored/{_id(user_id)}/{_id(photo_id)}.jpg"


def public_photo_key(photo_id: UUID) -> str:
    """An approved public photo, re-encoded, in the public bucket (T-4.4)."""
    return f"p/{_id(photo_id)}.jpg"


def blurred_photo_key(blur_id: UUID) -> str:
    """An approved public photo's blurred copy, in the public bucket (T-6.7,
    D-543). Its id is a fresh one, never the photo's: `p/{photo id}.jpg` is
    the photo itself, so a key derived from it would name the unblurred one."""
    return f"b/{_id(blur_id)}.jpg"


def voice_key(thread_id: UUID, file_id: UUID, kind: AudioType) -> str:
    """A voice note as sent, in the private bucket (T-7.9): the bytes the
    server measured, written by the server under a `file_id` of its own, new
    each time. No client is ever given a URL to write here, and no write lands
    on a file a message already keeps, so what a man unlocks can't be swapped
    after it was checked (D-620)."""
    return f"voice/{_id(thread_id)}/{_id(file_id)}.{EXTENSION[kind]}"


def voice_upload_key(thread_id: UUID, message_id: UUID, kind: AudioType) -> str:
    """A voice note as the browser PUT it, in the private bucket (T-7.9), under
    the extension of the type it was signed for. Read once, at the send."""
    return f"voice-uploads/{_id(thread_id)}/{_id(message_id)}.{EXTENSION[kind]}"


class VoiceKey(NamedTuple):
    thread_id: UUID
    message_id: UUID
    kind: AudioType


_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_VOICE_UPLOAD = re.compile(rf"voice-uploads/({_UUID})/({_UUID})\.([a-z0-9]+)")
_KIND_OF = {extension: kind for kind, extension in EXTENSION.items()}


def parse_voice_upload_key(key: str) -> VoiceKey | None:
    """What `voice_upload_key` built this key from, or None if it didn't build
    it: a key a client sends back is read, never trusted as a path (D-620)."""
    found = _VOICE_UPLOAD.fullmatch(key)
    if found is None or found.group(3) not in _KIND_OF:
        return None
    # Lowercase hex in UUID's own layout, matched whole: the key as built.
    thread_id, message_id = UUID(found.group(1)), UUID(found.group(2))
    return VoiceKey(thread_id, message_id, _KIND_OF[found.group(3)])


def album_key(request_id: UUID, photo_id: UUID) -> str:
    """A private photo watermarked for one granted album request's viewer, in
    the private bucket (T-8.4, D-730). Under the request's id, never the
    viewer's: a man who asks again after a revoke gets new keys, so the old
    request's late cleanup can't delete the new request's copies."""
    return f"album/{_id(request_id)}/{_id(photo_id)}.jpg"


def export_key(user_id: UUID, export_id: UUID) -> str:
    """A copy of a user's own data, in the private bucket, for 24 hours (T-9.6)."""
    return f"exports/{_id(user_id)}/{_id(export_id)}.json"


def public_url(settings: Settings, key: str) -> str:
    """Where a public-bucket object is served. `Settings` holds the base to
    `https://` with no trailing slash outside local."""
    return f"{settings.PUBLIC_CDN_URL}/{key}"


def _id(value: UUID) -> str:
    # Typed as UUID, checked as one too: a str that slipped past the types
    # would otherwise go straight into a key.
    if not isinstance(value, UUID):
        raise TypeError(
            f"storage keys are built from UUIDs, not {type(value).__name__}"
        )
    return str(value)
