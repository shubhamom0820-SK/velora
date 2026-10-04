"""Storage keys (T-4.1): one shape per kind of file, built from UUIDs only."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest

from app.core.storage_keys import (
    album_key,
    public_photo_key,
    public_url,
    raw_key,
    voice_key,
)
from tests.conftest import make_test_settings

A = uuid.UUID("11111111-1111-4111-8111-111111111111")
B = uuid.UUID("22222222-2222-4222-8222-222222222222")


def test_each_kind_of_file_has_its_shape() -> None:
    assert raw_key(A, B) == f"raw/{A}/{B}"
    assert public_photo_key(B) == f"p/{B}.jpg"
    assert voice_key(A, B) == f"voice/{A}/{B}.webm"
    assert album_key(A, B) == f"album/{A}/{B}.jpg"


@pytest.mark.parametrize("smuggled", ["../other-user", f"{A}/../..", str(A), 7])
def test_anything_but_a_uuid_is_refused(smuggled: Any) -> None:
    """A string that slipped past the types, even one that looks like a UUID,
    never becomes part of a key."""
    builders: tuple[Callable[[], str], ...] = (
        lambda: raw_key(smuggled, B),
        lambda: raw_key(A, smuggled),
        lambda: public_photo_key(smuggled),
        lambda: voice_key(smuggled, B),
        lambda: album_key(A, smuggled),
    )
    for build in builders:
        with pytest.raises(TypeError, match="built from UUIDs"):
            build()


def test_a_public_key_is_served_from_the_cdn() -> None:
    settings = make_test_settings().model_copy(
        update={"PUBLIC_CDN_URL": "https://cdn.staging.veloraapp.co.in"}
    )

    assert public_url(settings, public_photo_key(B)) == (
        f"https://cdn.staging.veloraapp.co.in/p/{B}.jpg"
    )
