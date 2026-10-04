"""What an uploaded file is, by its bytes (D-089, T-4.2).

The type a browser declares is the client's to choose and can say anything, so
it never decides: the first bytes do. JPEG, PNG and WebP are accepted; HEIC is
not (it would need pillow-heif, D-089). T-4.4 opens and re-encodes the image,
which is the full check; this one decides, before anything is queued, whether
the upload is one of the three at all.
"""

from __future__ import annotations

from typing import Literal

ImageType = Literal["image/jpeg", "image/png", "image/webp"]
ACCEPTED_TYPES: tuple[ImageType, ...] = ("image/jpeg", "image/png", "image/webp")
# Enough for every signature below: WebP's is the longest, 12 bytes.
SNIFF_BYTES = 16
# What to tell someone whose file isn't one of them: what to do, not only no.
ACCEPTED_NAMES = "JPEG, PNG or WebP"


def sniff(prefix: bytes) -> ImageType | None:
    """The accepted type these first bytes start, or None."""
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        return "image/webp"
    return None
