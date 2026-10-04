"""Writes the four portraits T-4.5's face-match tests read. Run once, from
`api/`: `uv run python -m tests.fixtures.faces.make`.

Made by Claude on 5 October 2026. Each is a NASA photograph, a work of the
United States government and so in the public domain, as Wikimedia Commons
records it (its licence field read that day for each file, below). Each is
fetched from Commons, checked against the SHA-1 Commons publishes for it, and
saved here at 600 pixels on its longest side, re-encoded as our pipeline would
(`core.images.reencode`). The files are committed, not fetched at test time.

**They prove the mechanism, never accuracy:** three people, a few photos. That
SFace tells these two people apart says nothing about how often it confuses
two others; no measurement of that exists (D-260).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx
from PIL import Image

from app.core.images import reencode

HERE = Path(__file__).resolve().parent
LONGEST_SIDE: Final = 600
_USER_AGENT = "velora-tests/0.1 (test fixtures, fetched once)"


@dataclass(frozen=True)
class Source:
    name: str  # the file written here
    page: str  # the Commons page, whose licence field says "Public domain"
    url: str
    sha1: str  # as Commons publishes it
    credit: str


SOURCES: Final = (
    Source(
        name="chari_2017.jpg",
        page="https://commons.wikimedia.org/wiki/File:Raja_Chari_official_portrait.jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/2/2d/Raja_Chari_official_portrait.jpg",
        sha1="75efd8515ffa8e6c8ddf4e106db5916671476250",
        credit="NASA astronaut candidate Raja Chari, 22 August 2017; NASA, Bill Stafford",
    ),
    Source(
        name="chari_2021.jpg",
        page="https://commons.wikimedia.org/wiki/File:Raja_Chari,_official_portrait_(2021).jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/d/db/Raja_Chari%2C_official_portrait_%282021%29.jpg",
        sha1="3cfbbc5b7cb32e86bd73dcb03cffad30a193e8ff",
        credit="NASA astronaut Raja Chari, 15 April 2021; NASA, Robert Markowitz",
    ),
    Source(
        name="williams_2004.jpg",
        page="https://commons.wikimedia.org/wiki/File:Sunita_Williams.jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/c/cb/Sunita_Williams.jpg",
        sha1="3102aa92a3bc3f2a7821d6f636637b028c38306e",
        credit="NASA astronaut Sunita Williams, 2004; NASA",
    ),
    Source(
        name="three_people.jpg",
        page=(
            "https://commons.wikimedia.org/wiki/File:ISS-66_Astronauts_Thomas_"
            "Marshburn,_Raja_Chari_and_Mark_Vande_Hei.jpg"
        ),
        url=(
            "https://upload.wikimedia.org/wikipedia/commons/6/61/ISS-66_Astronauts_"
            "Thomas_Marshburn%2C_Raja_Chari_and_Mark_Vande_Hei.jpg"
        ),
        sha1="423d7531fa3ae2b46b1489e02a86d0e716915a05",
        credit=(
            "Thomas Marshburn, Raja Chari and Mark Vande Hei on the International "
            "Space Station, 9 February 2022; NASA"
        ),
    ),
)


def smaller(original: bytes) -> bytes:
    with Image.open(io.BytesIO(original), formats=["JPEG"]) as image:
        image.thumbnail((LONGEST_SIDE, LONGEST_SIDE))
        out = io.BytesIO()
        image.convert("RGB").save(out, "JPEG", quality=95)
    return reencode(out.getvalue(), "image/jpeg").data


async def main() -> None:
    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT}, follow_redirects=True, timeout=60
    ) as client:
        for source in SOURCES:
            response = await client.get(source.url)
            response.raise_for_status()
            if hashlib.sha1(response.content).hexdigest() != source.sha1:
                raise SystemExit(f"{source.name}: not the file Commons describes")
            (HERE / source.name).write_bytes(smaller(response.content))


if __name__ == "__main__":
    asyncio.run(main())
