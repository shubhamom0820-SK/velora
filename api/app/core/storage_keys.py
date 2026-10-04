"""Where each kind of file lives in storage (T-4.1): the keys, built here only.

Every part of a key is a UUID, so nothing a user types can shape one: no `..`,
no slash, no other user's prefix. Which bucket each goes in is the caller's,
by D-027: originals, selfies, album copies and voice notes in the private
bucket; approved public photos in the public one, served from `PUBLIC_CDN_URL`.
"""

from __future__ import annotations

from uuid import UUID

from app.core.config import Settings


def raw_key(user_id: UUID, photo_id: UUID) -> str:
    """An upload as the browser PUT it, in the private bucket (T-4.2)."""
    return f"raw/{_id(user_id)}/{_id(photo_id)}"


def public_photo_key(photo_id: UUID) -> str:
    """An approved public photo, re-encoded, in the public bucket (T-4.4)."""
    return f"p/{_id(photo_id)}.jpg"


def voice_key(thread_id: UUID, message_id: UUID) -> str:
    """A voice note, in the private bucket (T-7.9)."""
    return f"voice/{_id(thread_id)}/{_id(message_id)}.webm"


def album_key(photo_id: UUID, viewer_id: UUID) -> str:
    """A private-album photo watermarked for one viewer, in the private bucket (T-8.4)."""
    return f"album/{_id(photo_id)}/{_id(viewer_id)}.jpg"


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
