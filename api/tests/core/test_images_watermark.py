"""`images.watermark` (T-8.4): an album copy, the viewer's `@username` tiled
diagonally over all of it at about 20% opacity. Faint, so the photo is still
the photo; everywhere, so no crop of any part of it leaves the name behind."""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageChops, ImageStat

from app.core import images


def _jpeg(size: tuple[int, int], colour: str) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, "JPEG", quality=95)
    return out.getvalue()


def _pixels(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data), formats=["JPEG"]) as image:
        return image.convert("RGB")


def _cells(size: tuple[int, int], across: int) -> list[tuple[int, int, int, int]]:
    width, height = size
    w, h = width // across, height // across
    return [
        (x * w, y * h, (x + 1) * w, (y + 1) * h)
        for y in range(across)
        for x in range(across)
    ]


@pytest.mark.parametrize("size", [(1200, 1600), (1600, 900), (320, 320)])
@pytest.mark.parametrize("colour", ["white", "black", "#7a9a5a"])
def test_the_name_is_on_every_part_of_the_photo_and_faint(
    size: tuple[int, int], colour: str
) -> None:
    """Each of 16 cells holds some of the name: a pixel moved well past what
    re-encoding moves one. The photo as a whole stays itself."""
    source = _jpeg(size, colour)

    marked = images.watermark(source, "@priya.k_21")

    plain, copy = _pixels(source), _pixels(marked)
    assert copy.size == plain.size
    difference = ImageChops.difference(copy, plain)
    for cell in _cells(size, 4):
        extrema = ImageStat.Stat(difference.crop(cell)).extrema
        assert max(high for _, high in extrema) > 25, cell
    # About 20% opacity: on average, a pixel moves a few levels, never most of
    # the way to white or black.
    assert sum(ImageStat.Stat(difference).mean) / 3 < 20


def test_each_viewer_gets_a_copy_of_his_own() -> None:
    source = _jpeg((800, 600), "teal")

    one, two = (images.watermark(source, name) for name in ("@aman", "@rahul.s"))

    assert one != two
    assert (
        sum(ImageStat.Stat(ImageChops.difference(_pixels(one), _pixels(two))).mean) > 0
    )


def test_it_is_a_fresh_jpeg_with_nothing_but_pixels() -> None:
    out = io.BytesIO()
    exif = Image.Exif()
    exif[0x010E] = "a description that must not survive"
    Image.new("RGB", (400, 300), "teal").save(out, "JPEG", exif=exif)

    marked = images.watermark(out.getvalue(), "@aman")

    assert marked.startswith(b"\xff\xd8\xff")
    with Image.open(io.BytesIO(marked)) as image:
        assert image.format == "JPEG"
        assert not image.getexif()
    assert b"must not survive" not in marked


@pytest.mark.parametrize(
    "data", [b"not an image", _jpeg((10, 10), "red")[:40], b"\x89PNG\r\n\x1a\n"]
)
def test_anything_but_a_readable_jpeg_is_refused(data: bytes) -> None:
    with pytest.raises(images.UnreadableImage):
        images.watermark(data, "@aman")
