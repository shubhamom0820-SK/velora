"""Liked you's rules (T-6.7, D-542). No I/O.

A handle names one like for one viewer: the first 128 bits of HMAC-SHA256,
keyed by `likes_handle_key` (core/security.py), over the viewer's id and the
liker's, in hex. The database computes it (pgcrypto's `hmac`), so the list can
be ordered and paged by it, and a reveal finds its like by it, without the
liker's id ever leaving the server. Another viewer's handle names nothing of
theirs, and a handle tells nobody whose it is.
"""

from __future__ import annotations

import re
from typing import Final

from app.core.enums import Gender, SwipeDirection

# What a like is: a like or a Super Like, never a pass.
LIKES: Final = frozenset({SwipeDirection.LIKE, SwipeDirection.SUPER})
# The handle's length in hex: 128 bits.
HANDLE_HEX: Final = 32
HANDLE: Final = re.compile(rf"[0-9a-f]{{{HANDLE_HEX}}}")


def sees_everyone(gender: Gender | None) -> bool:
    """D-002: a woman sees who liked her, free; a man reveals each."""
    return gender is Gender.FEMALE


def is_handle(value: str) -> bool:
    return HANDLE.fullmatch(value) is not None
