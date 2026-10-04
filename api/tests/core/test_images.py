"""What an upload is, by its bytes (D-089): JPEG, PNG and WebP, and nothing else."""

from __future__ import annotations

import pytest

from app.core.images import ACCEPTED_TYPES, sniff
from tests.images import GIF, HEIC, HTML, JPEG, PNG, WEBP


@pytest.mark.parametrize(
    ("data", "expected"),
    [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp")],
)
def test_the_three_accepted_types_are_known_by_their_bytes(
    data: bytes, expected: str
) -> None:
    assert sniff(data[:16]) == expected


@pytest.mark.parametrize(
    "data",
    [HEIC, GIF, HTML, b"", b"\xff\xd8", b"RIFF\x00\x00\x00\x00WAVE", b"\x89PNG"],
    ids=[
        "heic",
        "gif",
        "html",
        "empty",
        "half-a-jpeg",
        "riff-but-not-webp",
        "half-a-png",
    ],
)
def test_anything_else_is_none(data: bytes) -> None:
    assert sniff(data[:16]) is None


def test_exactly_three_types_are_accepted() -> None:
    assert ACCEPTED_TYPES == ("image/jpeg", "image/png", "image/webp")
