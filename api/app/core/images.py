"""What an uploaded file is, by its bytes (D-089, T-4.2), and its re-encoding
(D-092, T-4.4).

The type a browser declares is the client's to choose and can say anything, so
it never decides: the first bytes do. JPEG, PNG and WebP are accepted; HEIC is
not (it would need pillow-heif, D-089). `sniff` decides, before anything is
queued, whether the upload is one of the three at all; `reencode`, on the
worker, is the full check.

`reencode` is D-092's: Pillow is an image parser reading hostile input, the
most dangerous code we run, so
1. it decodes to pixels and encodes a new JPEG from those pixels alone, never
   strips metadata from the original: EXIF (a location among it), XMP, ICC
   data, text chunks and anything appended after the image don't survive,
   because nothing but pixels is carried over;
2. it refuses an image of more than `MAX_PIXELS` before decoding it, a limit
   set here explicitly, never Pillow's default;
3. it opens only the format the bytes were judged to be, so no other of
   Pillow's parsers is ever reached.

It is synchronous: an event loop runs it, so one worker process decodes one
image at a time, which bounds the worker's memory (D-088's 1 GB machine).
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from typing import Final, Literal

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

ImageType = Literal["image/jpeg", "image/png", "image/webp"]
ACCEPTED_TYPES: tuple[ImageType, ...] = ("image/jpeg", "image/png", "image/webp")
# Enough for every signature below: WebP's is the longest, 12 bytes.
SNIFF_BYTES = 16
# What to tell someone whose file isn't one of them: what to do, not only no.
ACCEPTED_NAMES = "JPEG, PNG or WebP"

# D-092's pixel limit. 40 megapixels is above any phone's default photo (12 to
# 24 MP) and under Pillow's own default (about 89 MP); decoded, 4 bytes a pixel
# at most, it is 160 MB, which the 1 GB worker holds beside everything else.
MAX_PIXELS: Final = 40_000_000
# Pillow's own check, at open, set to the same number. It warns above it and
# raises above twice it; `reencode` turns the warning into a refusal too, and
# checks the size itself, so neither Pillow's default nor a warning filter
# elsewhere decides.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

LONGEST_SIDE = 1600
JPEG_QUALITY = 85
# Transparent pixels land on white, not on whatever colour they happen to hold.
_BACKGROUND = (255, 255, 255)
_PILLOW_FORMAT: dict[ImageType, str] = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class UnreadableImage(Exception):
    """Not an image of the type its bytes were judged to be, or one Pillow
    can't decode. Never says why in detail: the bytes are a stranger's."""


class TooManyPixels(UnreadableImage):
    """More than `MAX_PIXELS`: refused before a pixel is decoded."""


@dataclass(frozen=True)
class Reencoded:
    data: bytes  # a JPEG, nothing in it but pixels
    width: int
    height: int


def sniff(prefix: bytes) -> ImageType | None:
    """The accepted type these first bytes start, or None."""
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        return "image/webp"
    return None


def reencode(data: bytes, image_type: ImageType) -> Reencoded:
    """`data` decoded as `image_type` only, turned upright, its longest side
    at most `LONGEST_SIDE`, and encoded afresh as a JPEG at quality 85 from its
    pixels alone. Raises `TooManyPixels` or `UnreadableImage`."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(
                io.BytesIO(data), formats=[_PILLOW_FORMAT[image_type]]
            ) as image:
                width, height = image.size
                if width * height > MAX_PIXELS:
                    raise TooManyPixels
                if image.format == "JPEG":
                    # Decode at the smallest scale still at least this big:
                    # a full decode, of fewer pixels.
                    image.draft("RGB", (LONGEST_SIDE, LONGEST_SIDE))
                image.load()
                image.thumbnail((LONGEST_SIDE, LONGEST_SIDE))
                # After the resize, so the turn moves fewer pixels; the bound is
                # square, so turning keeps the longest side within it.
                upright = ImageOps.exif_transpose(image)
                pixels = _rgb(upright)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise TooManyPixels from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError):
        raise UnreadableImage from None
    # A new image holding only the pixels: nothing of the original's `info`
    # (EXIF, XMP, ICC, comments) can reach the encoder from here.
    clean = Image.new("RGB", pixels.size)
    clean.paste(pixels)
    out = io.BytesIO()
    clean.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return Reencoded(data=out.getvalue(), width=clean.width, height=clean.height)


def _rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA", "PA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, _BACKGROUND)
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return image.convert("RGB")


# --- The blurred copy (T-6.7, D-543) -------------------------------------------------

# The blur keeps no more than this many pixels along the longest side: a face
# in a 24-pixel image is a few pixels across, too few for anyone, or a face
# detector, to find it (the tests run YuNet on one).
BLUR_SOURCE_SIDE: Final = 24
# Softens the 24 pixels' edges, so the copy reads as a blur, not a mosaic.
BLUR_RADIUS: Final = 1.5
# What the web is sent: the 24 pixels spread across a tile's width.
BLUR_SIDE: Final = 240
BLUR_QUALITY: Final = 70


def blur(data: bytes) -> bytes:
    """A blurred JPEG of `data`, an approved public copy this server wrote
    (`reencode`'s JPEG): shrunk to `BLUR_SOURCE_SIDE` on its longest side,
    softened, and spread back to `BLUR_SIDE`. Nothing of it but those few
    pixels reaches the result. Raises `UnreadableImage`."""
    try:
        with Image.open(io.BytesIO(data), formats=["JPEG"]) as image:
            image.draft("RGB", (BLUR_SOURCE_SIDE * 4, BLUR_SOURCE_SIDE * 4))
            image.load()
            small = _rgb(image)
            small.thumbnail((BLUR_SOURCE_SIDE, BLUR_SOURCE_SIDE), Image.Resampling.BOX)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError):
        raise UnreadableImage from None
    width, height = small.size
    scale = BLUR_SIDE / max(width, height)
    spread = small.filter(ImageFilter.GaussianBlur(BLUR_RADIUS)).resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.BICUBIC,
    )
    out = io.BytesIO()
    spread.save(out, "JPEG", quality=BLUR_QUALITY)
    return out.getvalue()
