"""What an uploaded voice note is, and how long it lasts, by its bytes (T-7.9,
D-620).

The type and the length a browser declares are the client's to choose and can
say anything, so neither decides: the bytes do. A 2 MB Opus file holds about
ten minutes, so the 60-second cap means something only if the length is
measured here. Three containers are accepted, the three a browser's
MediaRecorder writes: WebM (Chrome), Ogg Opus (Firefox) and MP4 (Safari).

`sniff` says which of the three the first bytes start; `duration` reads the
whole file, as the container it was declared and sniffed as, and returns its
length. It reads only container structure, never decodes audio, and each
reader is an allowlist: what it doesn't recognise as audio it refuses
(`UnreadableAudio`), so a file whose length can't be told is never let through.
Where a container states its length in more than one place (WebM's header and
its blocks' timestamps, MP4's movie header and its fragments), the longest
wins, so a header can't hide a long recording.

Pure Python, no dependency (CLAUDE.md rule 4). The fixtures in
`tests/core/test_audio.py` are built by hand; real browser recordings are
P-520's, on T-7.11's Needs line.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from fractions import Fraction
from typing import Final, Literal

AudioType = Literal["audio/webm", "audio/ogg", "audio/mp4"]
ACCEPTED_TYPES: tuple[AudioType, ...] = ("audio/webm", "audio/ogg", "audio/mp4")
# The extension each is stored under (`storage_keys.voice_key`).
EXTENSION: Final[dict[AudioType, str]] = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
}
# What to tell someone whose file isn't one of them.
ACCEPTED_NAMES = "WebM, Ogg or MP4"
# Enough for every signature below: WebM's DocType sits inside its header.
SNIFF_BYTES = 64


class UnreadableAudio(Exception):
    """Not audio of the type its bytes were judged to be, or a file whose
    length can't be told. Never says why in detail: the bytes are a
    stranger's."""


def sniff(prefix: bytes) -> AudioType | None:
    """The accepted type these first bytes start, or None."""
    if prefix.startswith(b"OggS"):
        return "audio/ogg"
    if prefix[4:8] == b"ftyp":
        return "audio/mp4"
    if prefix.startswith(_EBML) and _webm_doctype(prefix):
        return "audio/webm"
    return None


def duration(data: bytes, kind: AudioType) -> Fraction:
    """How long the recording lasts, in seconds, above 0; else
    `UnreadableAudio`."""
    try:
        if kind == "audio/ogg":
            seconds = _ogg_duration(data)
        elif kind == "audio/webm":
            seconds = _webm_duration(data)
        else:
            seconds = _mp4_duration(data)
    except (
        IndexError,
        OverflowError,
        StopIteration,
        struct.error,
        ValueError,
        ZeroDivisionError,
    ):
        raise UnreadableAudio(kind) from None
    if seconds <= 0:
        raise UnreadableAudio(kind)
    return seconds


def whole_seconds(seconds: Fraction) -> int:
    """To the nearest second, and at least 1: a recording the web stopped at
    60 seconds, a frame's overrun with it, is 60."""
    return max(1, int(seconds + Fraction(1, 2)))


# --- Ogg Opus (RFC 7845) --------------------------------------------------------

_OPUS_RATE = 48_000  # an Opus stream's granule position always counts 48 kHz
_NO_GRANULE = 0xFFFF_FFFF_FFFF_FFFF


def _ogg_pages(data: bytes) -> Iterator[tuple[int, int, bytes]]:
    """Each page's (granule position, serial number, body), in order."""
    at = 0
    while at < len(data):
        if data[at : at + 4] != b"OggS" or data[at + 4] != 0:
            raise ValueError("not an Ogg page")
        granule, serial = struct.unpack_from("<QI", data, at + 6)
        segments = data[at + 26]
        table = data[at + 27 : at + 27 + segments]
        if len(table) != segments:
            raise ValueError("truncated page")
        start = at + 27 + segments
        end = start + sum(table)
        if end > len(data):
            raise ValueError("truncated page")
        yield granule, serial, data[start:end]
        at = end


def _ogg_duration(data: bytes) -> Fraction:
    pages = _ogg_pages(data)
    _, serial, head = next(pages)
    if not head.startswith(b"OpusHead") or len(head) < 19:
        raise ValueError("not Opus")
    if any(other != serial for _, other, _ in _ogg_pages(data)):
        raise ValueError("more than one stream")
    pre_skip = struct.unpack_from("<H", head, 10)[0]
    last = max(
        (g for g, _, _ in _ogg_pages(data) if g != _NO_GRANULE),
        default=0,
    )
    return Fraction(last - pre_skip, _OPUS_RATE)


# --- WebM (Matroska's EBML) -----------------------------------------------------

_EBML = b"\x1a\x45\xdf\xa3"
_DOCTYPE = 0x4282
_SEGMENT = 0x18538067
_INFO = 0x1549A966
_TIMECODE_SCALE = 0x2AD7B1
_DURATION = 0x4489
_TRACKS = 0x1654AE6B
_TRACK_ENTRY = 0xAE
_TRACK_TYPE = 0x83
_AUDIO_TRACK = 2
_CLUSTER = 0x1F43B675
_TIMECODE = 0xE7
_BLOCK_GROUP = 0xA0
_SIMPLE_BLOCK = 0xA3
_BLOCK = 0xA1
_EBML_HEADER = 0x1A45DFA3
# Masters whose children are read in place; Chrome writes a Segment and its
# Clusters with an unknown size, so their ends are never relied on.
_ENTERED = frozenset({_SEGMENT, _INFO, _TRACKS, _TRACK_ENTRY, _CLUSTER, _BLOCK_GROUP})
_UNKNOWN = -1


def _vint(data: bytes, at: int, *, keep_marker: bool) -> tuple[int, int]:
    """An EBML variable-length integer at `at`: (value, length). An element
    size of all ones is `_UNKNOWN`."""
    first = data[at]
    length = 1
    while length <= 8 and not first & (0x80 >> (length - 1)):
        length += 1
    if length > 8 or at + length > len(data):
        raise ValueError("bad vint")
    value = first if keep_marker else first & (0xFF >> length)
    for byte in data[at + 1 : at + length]:
        value = (value << 8) | byte
    if not keep_marker and value == (1 << (7 * length)) - 1:
        return _UNKNOWN, length
    return value, length


def _ebml_elements(data: bytes, at: int = 0) -> Iterator[tuple[int, int, int]]:
    """Every element from `at` on, depth first: (id, body start, body size).
    The masters in `_ENTERED` are yielded and then read into; every other
    element is skipped by its size, which must be known and in the file."""
    while at < len(data):
        element, id_len = _vint(data, at, keep_marker=True)
        size, size_len = _vint(data, at + id_len, keep_marker=False)
        start = at + id_len + size_len
        yield element, start, size
        if element in _ENTERED:
            at = start
            continue
        if size == _UNKNOWN or start + size > len(data):
            raise ValueError("an element runs past the file")
        at = start + size


def _uint(data: bytes, start: int, size: int) -> int:
    if not 1 <= size <= 8:
        raise ValueError("bad unsigned integer")
    return int.from_bytes(data[start : start + size], "big")


def _webm_doctype(prefix: bytes) -> bool:
    """Whether this EBML header names the document `webm`."""
    try:
        _, id_len = _vint(prefix, 0, keep_marker=True)
        size, size_len = _vint(prefix, id_len, keep_marker=False)
        start = id_len + size_len
        header = prefix[start : start + size]
        at = 0
        while at < len(header):
            element, id_len = _vint(header, at, keep_marker=True)
            size, size_len = _vint(header, at + id_len, keep_marker=False)
            body = at + id_len + size_len
            if element == _DOCTYPE:
                return header[body : body + size] == b"webm"
            at = body + size
    except (IndexError, ValueError):
        return False
    return False


def _webm_duration(data: bytes) -> Fraction:
    scale = 1_000_000  # nanoseconds a tick, Matroska's default
    stated = Fraction(0)
    cluster: int | None = None
    last_tick: int | None = None
    tracks = audio = 0
    elements = _ebml_elements(data)
    first = next(elements)
    if first[0] != _EBML_HEADER:
        raise ValueError("no EBML header")
    for element, start, size in elements:
        if element == _TIMECODE_SCALE:
            scale = _uint(data, start, size)
        elif element == _DURATION:
            if size not in (4, 8):
                raise ValueError("bad duration")
            (ticks,) = struct.unpack_from(">f" if size == 4 else ">d", data, start)
            stated = Fraction(ticks)
        elif element == _TRACK_ENTRY:
            tracks += 1
        elif element == _TRACK_TYPE:
            if _uint(data, start, size) != _AUDIO_TRACK:
                raise ValueError("not an audio track")
            audio += 1
        elif element == _TIMECODE:
            cluster = _uint(data, start, size)
        elif element in (_SIMPLE_BLOCK, _BLOCK):
            if cluster is None:
                raise ValueError("a block outside a cluster")
            _, track_len = _vint(data, start, keep_marker=False)
            (relative,) = struct.unpack_from(">h", data, start + track_len)
            tick = cluster + relative
            last_tick = tick if last_tick is None else max(last_tick, tick)
    if tracks == 0 or audio != tracks or last_tick is None:
        raise ValueError("no audio")
    return max(stated, Fraction(last_tick)) * scale / 1_000_000_000


# --- MP4 (ISO BMFF) -------------------------------------------------------------

# A header's length of all ones is "not stated" (ISO/IEC 14496-12): a muxer
# writing fragments may not know it, and the fragments then say.
_UNSTATED = frozenset({0xFFFF_FFFF, 0xFFFF_FFFF_FFFF_FFFF})


def _boxes(data: bytes, start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
    """The boxes between `start` and `end`: (type, body start, body end)."""
    at = start
    while at < end:
        size, kind = struct.unpack_from(">I4s", data, at)
        header = 8
        if size == 1:
            (size,) = struct.unpack_from(">Q", data, at + 8)
            header = 16
        elif size == 0:
            size = end - at
        if size < header or at + size > end:
            raise ValueError("a box runs past its parent")
        yield kind, at + header, at + size
        at += size


def _child(data: bytes, start: int, end: int, kind: bytes) -> tuple[int, int] | None:
    for found, body, stop in _boxes(data, start, end):
        if found == kind:
            return body, stop
    return None


def _versioned(data: bytes, at: int, short: str, long: str) -> tuple[int, ...]:
    """A full box's fields after its version and flags, by its version."""
    version = data[at]
    return struct.unpack_from(">" + (long if version == 1 else short), data, at + 4)


def _mp4_duration(data: bytes) -> Fraction:
    top = list(_boxes(data, 0, len(data)))
    if not top or top[0][0] != b"ftyp":
        raise ValueError("no ftyp")
    moov = [(body, end) for kind, body, end in top if kind == b"moov"]
    if len(moov) != 1:
        raise ValueError("not one moov")
    lengths: list[Fraction] = []
    movie_scale = 0
    scales: dict[int, int] = {}  # track id -> its timescale
    defaults: dict[int, int] = {}  # track id -> trex's default sample duration
    for kind, body, end in _boxes(data, *moov[0]):
        if kind == b"mvhd":
            # creation, modification (4 or 8 each), timescale, duration
            _, _, movie_scale, length = _versioned(data, body, "IIII", "QQIQ")
            if length not in _UNSTATED:
                lengths.append(Fraction(length, movie_scale))
        elif kind == b"trak":
            track_id, scale, length = _track(data, body, end)
            scales[track_id] = scale
            if length not in _UNSTATED:
                lengths.append(Fraction(length, scale))
        elif kind == b"mvex":
            for inner, ibody, _ in _boxes(data, body, end):
                if inner == b"mehd":
                    (fragments,) = _versioned(data, ibody, "I", "Q")
                    lengths.append(Fraction(fragments, movie_scale))
                elif inner == b"trex":
                    track_id, _, sample = struct.unpack_from(">III", data, ibody + 4)
                    defaults[track_id] = sample
    if not scales:
        raise ValueError("no tracks")
    ends: dict[int, int] = {}
    for kind, body, end in top:
        if kind != b"moof":
            continue
        for traf, tbody, tend in _boxes(data, body, end):
            if traf == b"traf":
                track_id, finish = _fragment(data, tbody, tend, ends, defaults)
                if track_id not in scales:
                    raise ValueError("a fragment of no track")
                ends[track_id] = finish
    for track_id, finish in ends.items():
        lengths.append(Fraction(finish, scales[track_id]))
    return max(lengths)


def _track(data: bytes, start: int, end: int) -> tuple[int, int, int]:
    """A `trak`'s id, timescale and stated length; refused unless it is sound."""
    tkhd = _child(data, start, end, b"tkhd")
    mdia = _child(data, start, end, b"mdia")
    if tkhd is None or mdia is None:
        raise ValueError("a track without its header")
    _, _, track_id = _versioned(data, tkhd[0], "III", "QQI")
    mdhd = _child(data, *mdia, b"mdhd")
    hdlr = _child(data, *mdia, b"hdlr")
    if mdhd is None or hdlr is None:
        raise ValueError("a track without its media header")
    if data[hdlr[0] + 8 : hdlr[0] + 12] != b"soun":
        raise ValueError("not an audio track")
    _, _, scale, length = _versioned(data, mdhd[0], "IIII", "QQIQ")
    if scale == 0:
        raise ValueError("no timescale")
    return track_id, scale, length


def _fragment(
    data: bytes,
    start: int,
    end: int,
    ends: dict[int, int],
    defaults: dict[int, int],
) -> tuple[int, int]:
    """A `traf`'s track id and where its samples end, in the track's ticks:
    from its `tfdt`, or from where the track's last fragment ended."""
    tfhd = _child(data, start, end, b"tfhd")
    if tfhd is None:
        raise ValueError("a fragment without its header")
    flags = int.from_bytes(data[tfhd[0] + 1 : tfhd[0] + 4], "big")
    (track_id,) = struct.unpack_from(">I", data, tfhd[0] + 4)
    at = tfhd[0] + 8
    at += 8 if flags & 0x01 else 0  # base data offset
    at += 4 if flags & 0x02 else 0  # sample description index
    default = defaults.get(track_id, 0)
    if flags & 0x08:
        (default,) = struct.unpack_from(">I", data, at)
    tfdt = _child(data, start, end, b"tfdt")
    finish = ends.get(track_id, 0)
    if tfdt is not None:
        (finish,) = _versioned(data, tfdt[0], "I", "Q")
    for kind, body, stop in _boxes(data, start, end):
        if kind == b"trun":
            finish += _run_length(data, body, stop, default)
    return track_id, finish


def _run_length(data: bytes, start: int, end: int, default: int) -> int:
    """The sum of a `trun`'s sample durations, each its own or the default."""
    flags = int.from_bytes(data[start + 1 : start + 4], "big")
    count: int = struct.unpack_from(">I", data, start + 4)[0]
    at = start + 8
    at += 4 if flags & 0x001 else 0  # data offset
    at += 4 if flags & 0x004 else 0  # first sample flags
    fields = [0x100, 0x200, 0x400, 0x800]
    per_sample = 4 * sum(1 for f in fields if flags & f)
    if at + count * per_sample > end:
        raise ValueError("a run past its box")
    if not flags & 0x100:
        return count * default
    total = 0
    for n in range(count):
        (sample,) = struct.unpack_from(">I", data, at + n * per_sample)
        total += sample
    return total
