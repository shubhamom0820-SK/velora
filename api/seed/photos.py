"""The seed's placeholder photos (T-4.4): the prototype's card gradient.

The prototype paints each profile as `aBg(c1, c2)`: both colours "dusted" 16%
towards a warm grey, the second as the background, the first glowing from 28%
across and 22% down out to 60% of the way to the farthest corner, and a 16%
white highlight at 62% and 8% out to 44%. Drawn here with Pillow, then
re-encoded like any upload (D-092), so a seeded photo is what an approved one
is: a clean JPEG at most 1600 pixels on its longest side.
"""

from __future__ import annotations

import io
import math

from PIL import Image

from app.core.images import Reencoded, reencode

SIZE = (900, 1200)  # portrait, 3:4, as the prototype's cards are
_DUST_TOWARDS = (0x8A, 0x70, 0x72)
_DUST = 0.16


def dust(colour: str, share: float = _DUST) -> tuple[int, int, int]:
    """The prototype's `dust`: `#RRGGBB` moved `share` of the way to a warm grey."""
    value = int(colour.removeprefix("#"), 16)
    channels = ((value >> 16) & 255, (value >> 8) & 255, value & 255)
    red, green, blue = (
        round(channel * (1 - share) + towards * share)
        for channel, towards in zip(channels, _DUST_TOWARDS, strict=True)
    )
    return red, green, blue


def _glow(
    size: tuple[int, int], centre: tuple[float, float], reach: float, strength: int
) -> Image.Image:
    """A mask: `strength` at `centre` (as shares of the size), fading to 0 at
    `reach` of the distance to the farthest corner, as CSS's `circle` does."""
    width, height = size
    cx, cy = centre[0] * width, centre[1] * height
    corner = max(math.hypot(x - cx, y - cy) for x in (0, width) for y in (0, height))
    radius = max(1, round(reach * corner))
    # Pillow's radial gradient: 0 at the centre of 256 px, 255 at 128 px out.
    fade = Image.radial_gradient("L").resize((4 * radius, 4 * radius))
    mask = fade.point(lambda v: max(0, strength - strength * min(255, 2 * v) // 255))
    canvas = Image.new("L", size, 0)
    canvas.paste(mask, (round(cx) - 2 * radius, round(cy) - 2 * radius))
    return canvas


def placeholder(c1: str, c2: str) -> Reencoded:
    """A seeded profile's photo, re-encoded like any upload."""
    first, second = dust(c1), dust(c2)
    image = Image.new("RGB", SIZE, second)
    image.paste(
        Image.new("RGB", SIZE, first), mask=_glow(SIZE, (0.28, 0.22), 0.60, 255)
    )
    image.paste(
        Image.new("RGB", SIZE, (255, 255, 255)),
        mask=_glow(SIZE, (0.62, 0.08), 0.44, round(0.16 * 255)),
    )
    out = io.BytesIO()
    image.save(out, "PNG")
    return reencode(out.getvalue(), "image/png")
