"""What a voice note is and how long it lasts, by its bytes (T-7.9, D-620):
the three containers a browser records, the longest stated length winning,
and everything else refused, never let through unmeasured."""

from __future__ import annotations

import struct
from fractions import Fraction

import pytest

from app.core import audio
from app.core.audio import UnreadableAudio, duration, sniff, whole_seconds
from tests import audio_samples as s


def test_each_container_is_known_by_its_first_bytes() -> None:
    assert sniff(s.ogg(3)[: audio.SNIFF_BYTES]) == "audio/ogg"
    assert sniff(s.webm(3000)[: audio.SNIFF_BYTES]) == "audio/webm"
    assert sniff(s.mp4(3)[: audio.SNIFF_BYTES]) == "audio/mp4"


@pytest.mark.parametrize(
    "prefix",
    [
        b"",
        b"ID3\x04" + b"\x00" * 60,  # an MP3
        b"RIFF\x00\x00\x00\x00WAVE",
        b"\xff\xd8\xff\xe0" + b"\x00" * 60,  # a JPEG
        s.webm(3000, doctype=b"matroska")[:64],  # EBML, but not WebM
    ],
)
def test_anything_else_is_none(prefix: bytes) -> None:
    assert sniff(prefix) is None


def test_ogg_opus_lasts_to_its_last_granule_less_the_pre_skip() -> None:
    assert duration(s.ogg(12.5), "audio/ogg") == Fraction(25, 2)


def test_webm_as_chrome_writes_it_lasts_to_its_last_block() -> None:
    """Chrome states no duration and leaves its Segment and Clusters' sizes
    unknown: the blocks' timestamps are all there is."""
    assert duration(s.webm(42_340), "audio/webm") == Fraction(42_340, 1000)


def test_mp4_lasts_what_its_headers_say() -> None:
    assert duration(s.mp4(7.25), "audio/mp4") == Fraction(29, 4)


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({}, Fraction(9)),  # each sample's own duration, after each tfdt
        ({"tfdt": False}, Fraction(9)),  # fragments one after another
        # trex's default, 1024 ticks: 47 of them a fragment, a little over a second
        ({"per_sample": False}, Fraction(8 * 48_000 + 47 * 1024, 48_000)),
    ],
)
def test_fragmented_mp4_lasts_to_where_its_fragments_end(
    kw: dict[str, bool], expected: Fraction
) -> None:
    assert duration(s.fragmented_mp4(9, **kw), "audio/mp4") == expected


@pytest.mark.parametrize(
    ("data", "kind", "expected"),
    [
        # A header saying 5 seconds can't hide 70 of blocks or fragments ...
        (s.webm(70_000, stated_ms=5_000), "audio/webm", Fraction(70)),
        (s.fragmented_mp4(70, stated_ms=5_000), "audio/mp4", Fraction(70)),
        # ... and a header saying 70 is believed over 5 of them.
        (s.webm(5_000, stated_ms=70_000), "audio/webm", Fraction(70)),
        (s.fragmented_mp4(5, stated_ms=70_000), "audio/mp4", Fraction(70)),
        (s.fragmented_mp4(5, mehd_ms=70_000), "audio/mp4", Fraction(70)),
    ],
)
def test_the_longest_length_stated_wins(
    data: bytes, kind: audio.AudioType, expected: Fraction
) -> None:
    assert duration(data, kind) == expected


def _vorbis_head() -> bytes:
    return b"\x01vorbis" + b"\x00" * 22


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b"", "audio/ogg"),
        (b"OggS", "audio/ogg"),
        (s.ogg(3)[:-10], "audio/ogg"),  # truncated
        (s.ogg(3, head=_vorbis_head()), "audio/ogg"),  # not Opus
        (s.ogg(3, second_stream=True), "audio/ogg"),
        (s.ogg_page(0, s.opus_head()), "audio/ogg"),  # no audio
        (s.webm(3000)[:-5], "audio/webm"),  # truncated
        (s.webm(3000, track_type=1), "audio/webm"),  # a video track
        (s.webm(3000, blocks=False), "audio/webm"),  # no audio
        (s.webm(3000, stated_ms=float("nan")), "audio/webm"),
        (s.webm(3000, stated_ms=float("inf")), "audio/webm"),
        (s.mp4(3)[:-5], "audio/mp4"),  # a box past the file
        (s.mp4(3, handler=b"vide"), "audio/mp4"),  # a video track
        (s.FTYP + s.box(b"mdat", b"\x00" * 8), "audio/mp4"),  # no moov
        (s.FTYP + s.box(b"moov", s.mvhd(3000)), "audio/mp4"),  # no track
        (s.FTYP + s.box(b"moov", s.mvhd(3000) + s.trak(3, scale=0)), "audio/mp4"),
        (s.FTYP + s.box(b"moov", s.mvhd(0) + s.trak(0)), "audio/mp4"),  # 0 long
        (s.ogg(3), "audio/webm"),  # judged as another container
        (s.webm(3000), "audio/mp4"),
    ],
)
def test_a_file_whose_length_cant_be_told_is_refused(
    data: bytes, kind: audio.AudioType
) -> None:
    with pytest.raises(UnreadableAudio):
        duration(data, kind)


def test_a_box_claiming_more_than_its_parent_is_refused() -> None:
    lying = struct.pack(">I", 10_000) + b"moov" + s.mvhd(3000)
    with pytest.raises(UnreadableAudio):
        duration(s.FTYP + lying, "audio/mp4")


@pytest.mark.parametrize(
    ("seconds", "whole"),
    [
        (Fraction(1, 5), 1),  # never 0
        (Fraction(59, 1), 59),
        (Fraction(119, 2), 60),
        (Fraction(604, 10), 60),  # the web's 60-second cap, a frame over
        (Fraction(121, 2), 61),
    ],
)
def test_lengths_are_kept_to_the_nearest_second(seconds: Fraction, whole: int) -> None:
    assert whole_seconds(seconds) == whole
