"""Voice-note files built by hand, byte by byte, for `core.audio`'s tests and
the send's (T-7.9). Each is the container's structure and no real audio: what
`core.audio` reads, and nothing it doesn't. They are shaped as each browser's
MediaRecorder writes them, as far as the specs say; real recordings are P-520's.
"""

from __future__ import annotations

import struct

# --- Ogg Opus (Firefox) ---------------------------------------------------------

PRE_SKIP = 312


def ogg_page(granule: int, body: bytes, *, serial: int = 7, seq: int = 0) -> bytes:
    assert len(body) < 255
    return (
        b"OggS\x00\x00"
        + struct.pack("<QIII", granule, serial, seq, 0)
        + bytes([1, len(body)])
        + body
    )


def opus_head(pre_skip: int = PRE_SKIP) -> bytes:
    return b"OpusHead" + struct.pack("<BBHIhB", 1, 1, pre_skip, 48_000, 0, 0)


def ogg(
    seconds: float, *, head: bytes | None = None, second_stream: bool = False
) -> bytes:
    """Opus at 48 kHz: a page a second, the last at `seconds`."""
    pages = [
        ogg_page(0, head or opus_head()),
        ogg_page(0, b"OpusTags" + b"\x00" * 8, seq=1),
    ]
    whole = int(seconds)
    granules = [PRE_SKIP + s * 48_000 for s in range(1, whole + 1)]
    if seconds != whole or not granules:
        granules.append(PRE_SKIP + round(seconds * 48_000))
    for n, granule in enumerate(granules):
        pages.append(ogg_page(granule, b"\xfc" * 40, seq=n + 2))
    if second_stream:
        pages.append(ogg_page(48_000, b"\xfc" * 40, serial=8))
    return b"".join(pages)


# --- WebM (Chrome) --------------------------------------------------------------

UNKNOWN = b"\x01\xff\xff\xff\xff\xff\xff\xff"


def _id(element: int) -> bytes:
    return element.to_bytes((element.bit_length() + 7) // 8, "big")


def el(element: int, body: bytes) -> bytes:
    """An element with an 8-byte size."""
    return _id(element) + b"\x01" + len(body).to_bytes(7, "big") + body


def uint(value: int) -> bytes:
    return value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")


def block(relative_ms: int) -> bytes:
    return el(0xA3, b"\x81" + struct.pack(">hB", relative_ms, 0x80) + b"\xfc" * 20)


def webm(
    last_ms: int,
    *,
    stated_ms: float | None = None,
    track_type: int = 2,
    doctype: bytes = b"webm",
    blocks: bool = True,
) -> bytes:
    """As Chrome writes it: a Segment and Clusters of unknown size, no stated
    duration unless `stated_ms`. Blocks at 0 and at `last_ms`."""
    info = el(0x2AD7B1, uint(1_000_000))
    if stated_ms is not None:
        info += el(0x4489, struct.pack(">d", stated_ms))
    tracks = el(0x1654AE6B, el(0xAE, el(0xD7, uint(1)) + el(0x83, uint(track_type))))
    clusters = b""
    if blocks:
        clusters += b"\x1f\x43\xb6\x75" + UNKNOWN + el(0xE7, uint(0)) + block(0)
        start = max(0, last_ms - 1000)
        clusters += (
            b"\x1f\x43\xb6\x75"
            + UNKNOWN
            + el(0xE7, uint(start))
            + block(0)
            + block(last_ms - start)
        )
    return (
        el(0x1A45DFA3, el(0x4286, uint(1)) + el(0x4282, doctype))
        + b"\x18\x53\x80\x67"
        + UNKNOWN
        + el(0x1549A966, info)
        + tracks
        + clusters
    )


# --- MP4 (Safari) ---------------------------------------------------------------


def box(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", 8 + len(body)) + kind + body


def full(kind: bytes, body: bytes, *, version: int = 0, flags: int = 0) -> bytes:
    return box(kind, bytes([version]) + flags.to_bytes(3, "big") + body)


FTYP = box(b"ftyp", b"M4A \x00\x00\x00\x00isomiso2mp41")
TRACK_SCALE = 48_000


def mvhd(duration: int, scale: int = 1000) -> bytes:
    return full(b"mvhd", struct.pack(">IIII", 0, 0, scale, duration) + b"\x00" * 80)


def trak(duration: int, *, handler: bytes = b"soun", scale: int = TRACK_SCALE) -> bytes:
    tkhd = full(b"tkhd", struct.pack(">III", 0, 0, 1) + b"\x00" * 68, flags=3)
    mdhd = full(b"mdhd", struct.pack(">IIII", 0, 0, scale, duration) + b"\x00" * 4)
    hdlr = full(b"hdlr", b"\x00" * 4 + handler + b"\x00" * 12 + b"\x00")
    return box(b"trak", tkhd + box(b"mdia", mdhd + hdlr))


def mp4(seconds: float, *, handler: bytes = b"soun") -> bytes:
    """Not fragmented: the length in the movie and track headers."""
    moov = box(
        b"moov",
        mvhd(round(seconds * 1000))
        + trak(round(seconds * TRACK_SCALE), handler=handler),
    )
    return FTYP + moov + box(b"mdat", b"\xfc" * 64)


def fragmented_mp4(
    seconds: int,
    *,
    tfdt: bool = True,
    per_sample: bool = True,
    stated_ms: int = 0,
    mehd_ms: int | None = None,
) -> bytes:
    """As Safari writes it, as far as we know: the headers state 0, and each
    second is a fragment of 1024-tick AAC frames (47 a second at 48 kHz, the
    last frame's shortfall made up in its own duration)."""
    mvex = full(b"trex", struct.pack(">IIIII", 1, 1, 1024, 0, 0))
    if mehd_ms is not None:
        mvex = full(b"mehd", struct.pack(">I", mehd_ms)) + mvex
    moov = box(b"moov", mvhd(stated_ms) + trak(0) + box(b"mvex", mvex))
    fragments = b""
    for n in range(seconds):
        frames = [1024] * 46 + [TRACK_SCALE - 1024 * 46]
        if per_sample:
            trun = full(
                b"trun",
                struct.pack(">I", len(frames))
                + b"".join(struct.pack(">I", f) for f in frames),
                flags=0x100,
            )
        else:
            # Every sample the default: 1024 ticks, so a second is 47 of them
            # and a little over.
            trun = full(b"trun", struct.pack(">I", 47))
        traf = full(b"tfhd", struct.pack(">I", 1), flags=0x020000)
        if tfdt:
            traf += full(b"tfdt", struct.pack(">Q", n * TRACK_SCALE), version=1)
        traf += trun
        fragments += box(
            b"moof", full(b"mfhd", struct.pack(">I", n + 1)) + box(b"traf", traf)
        )
        fragments += box(b"mdat", b"\xfc" * 16)
    return FTYP + moov + fragments
