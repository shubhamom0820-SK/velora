"""Writes `photo-1600.jpg`, the photo T-9.10's first-load bench serves on every
card. Run once, from `api/` (it uses the API's own re-encode), with the
original downloaded first:

    curl -fsS -o /tmp/original.jpg "https://upload.wikimedia.org/wikipedia/\
commons/d/db/Raja_Chari%2C_official_portrait_%282021%29.jpg"
    uv run python ../web/bench/fixtures/make_photo.py /tmp/original.jpg

(curl, not httpx: on 19 October 2026 Wikimedia answered httpx's requests with
429 Too Many Requests twice and curl's at once.)

Made by Claude on 19 October 2026. A NASA photograph, a work of the United
States government and so in the public domain, as Wikimedia Commons records
it: the same file `api/tests/fixtures/faces/make.py` reads ("NASA astronaut
Raja Chari, 15 April 2021; NASA, Robert Markowitz"), checked here against the
SHA-1 Commons publishes for it. Put through `core.images.reencode` as an
approved photo is (longest side 1600, a JPEG at quality 85, D-092), so its
size in bytes is what a card's photo costs on the wire, not a guess.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Final

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "api"))

from app.core.images import reencode

SHA1: Final = "3cfbbc5b7cb32e86bd73dcb03cffad30a193e8ff"


def main(original: Path) -> None:
    data = original.read_bytes()
    if hashlib.sha1(data).hexdigest() != SHA1:
        raise SystemExit("not the file Commons describes")
    out = reencode(data, "image/jpeg")
    (HERE / "photo-1600.jpg").write_bytes(out.data)
    sys.stdout.write(
        f"photo-1600.jpg: {out.width} x {out.height}, {len(out.data)} bytes\n"
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
