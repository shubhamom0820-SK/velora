"""Real recordings, read by T-7.9's measuring (P-520, D-620).

Made by the founder on 9 October 2026 with T-7.11's recorder (`/dev/voice`,
`web/src/lib/voice-recorder.ts`), on an iPhone in Safari, and AirDropped to the
Mac: the file's AirDrop mark (`sharingd`) and its WebM header's writer
(`WebKit`) say so. Saved under the page's default name, `chrome-mac-…`, and
renamed here for what they are; the bytes are unchanged (SHA-256 below).
Recent iOS Safari records WebM Opus, which the recorder asks for first, so
Safari's MP4 is still read only from files built by hand (P-774). The Mac's
browsers are P-773.

Each name is `<browser>-<device>-<target>s-<ms>ms.<ext>`, `<ms>` the recorder's
own length, `start` to `stop`. The server's length must be within a second of
it, and every file one the send would take: under 2 MB, its type by its first
bytes, a minute at most.
"""

from __future__ import annotations

import hashlib
import re
from fractions import Fraction
from pathlib import Path

import pytest

from app.core import audio
from app.modules.messages.service import MAX_VOICE_BYTES, MAX_VOICE_SECONDS

VOICE = Path(__file__).resolve().parents[1] / "fixtures" / "voice"

# Exactly these, each by its bytes: a file added, lost or changed fails here.
RECORDINGS = {
    "safari-iphone-5s-5693ms.webm": (
        "b9e7e79aca207956d5a40e86af494119ae16c8d497863fb879201aaecd8f4190"
    ),
    "safari-iphone-59s-59919ms.webm": (
        "cd1e23a27433304c8ed2a66be4b17af2a9c7eb8d06c61c2da6e8f243bc64dfac"
    ),
}
NAME = re.compile(r"^[a-z]+-[a-z]+-(?:5|59)s-(?P<ms>\d+)ms\.(?P<ext>webm|ogg|m4a)$")
TYPE_OF = {"webm": "audio/webm", "ogg": "audio/ogg", "m4a": "audio/mp4"}


def test_the_recordings_are_exactly_these() -> None:
    found = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in VOICE.iterdir()
    }
    assert found == RECORDINGS


@pytest.mark.parametrize("name", sorted(RECORDINGS))
def test_a_real_recording_is_measured_within_a_second_of_the_recorder(
    name: str,
) -> None:
    match = NAME.match(name)
    assert match is not None, name
    data = (VOICE / name).read_bytes()
    recorder = Fraction(int(match["ms"]), 1000)

    kind = audio.sniff(data[: audio.SNIFF_BYTES])
    measured = audio.duration(data, kind) if kind is not None else None

    assert kind == TYPE_OF[match["ext"]]
    assert measured is not None
    assert abs(measured - recorder) <= 1, (float(measured), float(recorder))
    assert len(data) <= MAX_VOICE_BYTES
    assert 1 <= audio.whole_seconds(measured) <= MAX_VOICE_SECONDS
