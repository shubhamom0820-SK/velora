"""`images.blur` (T-6.7, D-543): the picture a man sees in place of someone
who liked him. It must carry no more than its few pixels: no face a person, or
a face detector, could find, and nothing of the original's detail.

The faces are NASA's public-domain portraits in `tests/fixtures/faces/`; the
detector is YuNet, the model the selfie check runs (D-088). Needs the models
(`make models`); skipped locally without them, failed in CI.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from app.core import images
from app.core.images import reencode
from app.core.providers.facematch import SFaceFaceMatch
from tests.infra import require_models

FACES = Path(__file__).resolve().parents[1] / "fixtures" / "faces"


def _portrait(name: str) -> bytes:
    """A portrait as the public bucket holds one: our re-encode's JPEG."""
    return reencode((FACES / f"{name}.jpg").read_bytes(), "image/jpeg").data


def _open(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data), formats=["JPEG"]) as image:
        return image.convert("RGB")


@pytest.mark.parametrize("name", ["chari_2017", "chari_2021", "williams_2004"])
def test_a_face_found_in_the_photo_is_found_in_no_blur_of_it(name: str) -> None:
    """The privacy the paywall rests on, read the way a machine would read it."""
    require_models()
    detector = SFaceFaceMatch()
    original = _portrait(name)
    faces = asyncio.run(detector.compare(original, [])).faces_in_selfie
    assert faces == 1

    blurred = images.blur(original)

    assert asyncio.run(detector.compare(blurred, [])).faces_in_selfie == 0


@pytest.mark.parametrize("name", ["chari_2017", "three_people"])
def test_a_blur_holds_no_more_than_its_few_pixels(name: str) -> None:
    """Shrunk to its source's size and spread back, a blur is what it was:
    nothing in it is finer than `BLUR_SOURCE_SIDE` pixels across."""
    blurred = _open(images.blur(_portrait(name)))
    width, height = blurred.size
    side = images.BLUR_SOURCE_SIDE
    scale = side / max(width, height)
    small = blurred.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.BOX,
    )
    again = small.resize(blurred.size, Image.Resampling.BICUBIC)

    difference = ImageStat.Stat(ImageChops.difference(blurred, again)).mean

    assert max(difference) < 4


def test_its_longest_side_is_the_tiles_and_its_shape_the_photos() -> None:
    original = _open(_portrait("chari_2017"))
    blurred = _open(images.blur(_portrait("chari_2017")))

    assert max(blurred.size) == images.BLUR_SIDE
    assert abs(blurred.width / blurred.height - original.width / original.height) < 0.1


def test_what_isnt_a_jpeg_is_unreadable() -> None:
    with pytest.raises(images.UnreadableImage):
        images.blur(b"not an image at all")
