"""D-092's three conditions on `images.reencode` (T-4.4).

1. **A full decode and re-encode.** The photos in `tests/fixtures/located/`
   genuinely carry a location: GPS in EXIF, coordinates in XMP, a comment, a PNG
   text chunk and bytes after the image, in JPEG, PNG and WebP. Two readers
   that aren't Pillow confirmed it on 4 October 2026 (Apple's ImageIO and
   exifread 3.0.0, both reading 12.9716 N, 77.5946 E, 920 m); the first test
   here re-checks the bytes themselves, so the location tests can't pass on
   files that never had one. Any location surviving fails critical #14.
2. **The decompression is bounded,** tested with actual bombs: small files
   that would decode to tens of megabytes or gigabytes.
3. **Pillow is pinned exactly.**
"""

from __future__ import annotations

import io
import struct
import tomllib
import zlib
from collections.abc import Iterator
from pathlib import Path

import PIL
import pytest
from PIL import Image, ImageFile

from app.core import images
from app.core.images import (
    LONGEST_SIDE,
    MAX_PIXELS,
    ImageType,
    TooManyPixels,
    UnreadableImage,
    reencode,
)
from tests.fixtures.located import make

LOCATED = Path(__file__).resolve().parent.parent / "fixtures" / "located"
PHOTOS: dict[ImageType, str] = {
    "image/jpeg": "located.jpg",
    "image/png": "located.png",
    "image/webp": "located.webp",
}
API = Path(__file__).resolve().parents[2]


def _rationals(*values: tuple[int, int]) -> list[bytes]:
    """EXIF stores 17.76 seconds as 444/25: each, as either byte order writes it."""
    return [struct.pack(order + "LL", *v) for v in values for order in "<>"]


SECONDS = _rationals((444, 25), (1014, 25))  # 17.76" N and 40.56" E
# What carries the location, by format: each must be in the photo...
CARRIED: dict[ImageType, list[bytes]] = {
    "image/jpeg": [
        b"Exif\x00\x00",
        make.MAKE.encode(),
        make.XMP_MARK.encode(),
        make.COMMENT_MARK.encode(),
        make.TRAILER_MARK.encode(),
        make.COORDINATES.encode(),
        b"ICC_PROFILE",
    ],
    "image/png": [
        b"eXIf",
        make.MAKE.encode(),
        make.XMP_MARK.encode(),
        make.TEXT_MARK.encode(),
        make.TRAILER_MARK.encode(),
        make.COORDINATES.encode(),
    ],
    "image/webp": [b"EXIF", b"XMP ", make.MAKE.encode(), make.XMP_MARK.encode()],
}
# ...and none of all of them, nor any metadata container, in what comes out.
NEVER_OUT = sorted(
    {*(m for marks in CARRIED.values() for m in marks), *SECONDS, b"GPS", b"xmp"}
)


def _photo(image_type: ImageType) -> bytes:
    return (LOCATED / PHOTOS[image_type]).read_bytes()


def _segments(jpeg: bytes) -> Iterator[tuple[int, bytes]]:
    """A JPEG's markers and their payloads, read by hand: no Pillow involved.
    After SOS the entropy-coded data runs to EOI, which must end the file."""
    assert jpeg[:2] == b"\xff\xd8", "not a JPEG"
    yield 0xD8, b""
    at = 2
    while at < len(jpeg):
        assert jpeg[at] == 0xFF, f"no marker at {at}"
        marker = jpeg[at + 1]
        if marker == 0xD9:
            yield marker, jpeg[at + 2 :]  # what follows EOI
            return
        length = int.from_bytes(jpeg[at + 2 : at + 4], "big")
        yield marker, jpeg[at + 4 : at + 2 + length]
        at += 2 + length
        if marker == 0xDA:
            end = jpeg.rindex(b"\xff\xd9")
            yield 0xD9, jpeg[end + 2 :]
            return
    raise AssertionError("no EOI")


# Exactly these, nothing else: SOI, APP0 (JFIF), DQT, SOF0, DHT, SOS, EOI.
ALLOWED_MARKERS = {0xD8, 0xE0, 0xDB, 0xC0, 0xC4, 0xDA, 0xD9}


@pytest.mark.parametrize("image_type", list(PHOTOS))
def test_the_photos_really_carry_a_location(image_type: ImageType) -> None:
    """Read from the bytes, not by Pillow: what the next test proves gone was
    there to begin with."""
    photo = _photo(image_type)
    for mark in CARRIED[image_type]:
        assert mark in photo, mark
    assert any(seconds in photo for seconds in SECONDS[:2])  # latitude's
    assert any(seconds in photo for seconds in SECONDS[2:])  # longitude's


@pytest.mark.critical
@pytest.mark.parametrize("image_type", list(PHOTOS))
def test_no_location_survives_the_reencode(image_type: ImageType) -> None:
    """Critical #14 (D-092's first condition): nothing of the original but
    its pixels reaches the JPEG we store."""
    out = reencode(_photo(image_type), image_type).data

    # Every header before the pixels, and the whole file for marks long enough
    # that compressed pixels can't spell them by chance.
    headers = out[: out.index(b"\xff\xda")]
    survived = [
        mark
        for mark in NEVER_OUT
        if mark in headers or (len(mark) >= 8 and mark in out)
    ]
    assert survived == []
    segments = list(_segments(out))
    assert {marker for marker, _ in segments} <= ALLOWED_MARKERS
    [app0] = [payload for marker, payload in segments if marker == 0xE0]
    assert app0.startswith(b"JFIF\x00")
    assert segments[-1] == (0xD9, b"")  # nothing after the image's end
    with Image.open(io.BytesIO(out)) as again:
        assert dict(again.getexif()) == {}
        assert not {"exif", "icc_profile", "xmp", "comment"} & set(again.info)


@pytest.mark.parametrize("image_type", list(PHOTOS))
def test_the_photo_is_turned_upright(image_type: ImageType) -> None:
    """Stored on its side (Orientation 6), with a red band down its left
    edge: upright, that band is along the top, and the photo is portrait."""
    out = reencode(_photo(image_type), image_type)

    assert (out.width, out.height) == (360, 480)
    with Image.open(io.BytesIO(out.data)) as again:
        top = again.getpixel((180, 15))
        bottom = again.getpixel((180, 465))
    assert isinstance(top, tuple) and isinstance(bottom, tuple)
    assert top[0] > 180 and top[2] < 80  # red
    assert bottom[2] > 120 and bottom[0] < 80  # blue


def _encoded(size: tuple[int, int], fmt: str = "JPEG", mode: str = "RGB") -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, (10, 120, 200) if mode == "RGB" else None).save(out, fmt)
    return out.getvalue()


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((4000, 3000), (1600, 1200)),
        ((1200, 5000), (384, 1600)),
        ((480, 360), (480, 360)),
    ],
)
def test_the_longest_side_is_at_most_1600_and_nothing_is_enlarged(
    size: tuple[int, int], expected: tuple[int, int]
) -> None:
    out = reencode(_encoded(size), "image/jpeg")

    assert (out.width, out.height) == expected
    assert max(expected) <= LONGEST_SIDE


def test_transparency_lands_on_white() -> None:
    out = io.BytesIO()
    Image.new("RGBA", (40, 40), (255, 0, 0, 0)).save(out, "PNG")

    clean = reencode(out.getvalue(), "image/png")

    with Image.open(io.BytesIO(clean.data)) as again:
        pixel = again.getpixel((20, 20))
    assert isinstance(pixel, tuple) and min(pixel) > 245


def test_only_the_judged_format_is_parsed() -> None:
    """A PNG's bytes, judged JPEG, aren't read as a PNG: one parser only."""
    with pytest.raises(UnreadableImage):
        reencode(_encoded((40, 40), "PNG"), "image/jpeg")


@pytest.mark.parametrize(
    "data",
    [b"", b"\xff\xd8\xff" + b"\x00" * 64, _encoded((400, 300))[:200]],
    ids=["empty", "a JPEG's first bytes only", "a JPEG cut short"],
)
def test_what_isnt_a_whole_image_is_unreadable(data: bytes) -> None:
    with pytest.raises(UnreadableImage):
        reencode(data, "image/jpeg")


# --- D-092's second condition: actual bombs ---------------------------------------


def _png_bomb(width: int, height: int) -> bytes:
    """A real PNG, one bit a pixel and every pixel black, written chunk by
    chunk with no image ever in memory: rows of zeros compress about a
    thousand to one."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(kind + body)
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)
    row = b"\x00" * (1 + (width + 7) // 8)  # filter byte, then the pixels
    squeeze = zlib.compressobj(9)
    data = b"".join(squeeze.compress(row) for _ in range(height)) + squeeze.flush()
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", data)
        + chunk(b"IEND", b"")
    )


def _jpeg_claiming(width: int, height: int) -> bytes:
    """A small real JPEG whose frame header says it is `width` x `height`."""
    jpeg = bytearray(_encoded((16, 16)))
    sof = jpeg.index(b"\xff\xc0")
    jpeg[sof + 5 : sof + 9] = struct.pack(">HH", height, width)
    return bytes(jpeg)


@pytest.fixture
def decodes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """How many times any image was decoded: a refusal must come first."""
    calls: list[int] = []
    real = ImageFile.ImageFile.load

    def counting(self: ImageFile.ImageFile) -> object:
        calls.append(1)
        return real(self)

    monkeypatch.setattr(ImageFile.ImageFile, "load", counting)
    return calls


def test_a_bomb_under_pillows_default_is_refused_by_our_limit(
    decodes: list[int],
) -> None:
    """8,000 x 8,000: 64 megapixels in a file of a few kilobytes. Above our
    40, under Pillow's default 89: only the limit set here refuses it."""
    bomb = _png_bomb(8_000, 8_000)
    assert len(bomb) < 20_000
    assert MAX_PIXELS < 8_000 * 8_000 < 89_478_485

    with pytest.raises(TooManyPixels):
        reencode(bomb, "image/png")
    assert decodes == []


@pytest.mark.parametrize(
    ("bomb", "image_type"),
    [
        (_png_bomb(50_000, 50_000), "image/png"),
        (_jpeg_claiming(60_000, 60_000), "image/jpeg"),
    ],
    ids=["png, 2.5 gigapixels", "jpeg, 3.6 gigapixels"],
)
def test_a_bomb_that_would_take_the_worker_down_is_refused_unread(
    bomb: bytes, image_type: ImageType, decodes: list[int]
) -> None:
    """Gigapixels, gigabytes decoded, in files under 400 KB."""
    assert len(bomb) < 400_000

    with pytest.raises(TooManyPixels):
        reencode(bomb, image_type)
    assert decodes == []


def test_the_limit_is_set_here_never_left_to_pillows_default() -> None:
    assert Image.MAX_IMAGE_PIXELS == MAX_PIXELS == images.MAX_PIXELS
    assert MAX_PIXELS < 89_478_485  # Pillow 12's own default


# --- D-092's third condition ---------------------------------------------------------


def test_pillow_is_pinned_exactly_and_the_pin_is_what_runs() -> None:
    pyproject = tomllib.loads((API / "pyproject.toml").read_text())
    [pin] = [d for d in pyproject["project"]["dependencies"] if d.startswith("pillow")]

    assert pin.startswith("pillow==")
    assert pin.removeprefix("pillow==") == PIL.__version__
