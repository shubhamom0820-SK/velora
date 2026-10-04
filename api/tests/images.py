"""The first bytes of each kind of file the upload tests send (D-089)."""

from __future__ import annotations

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 64
# What an iPhone saves by default: an ISO box naming HEIC, which we refuse.
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00" + b"\x00" * 64
GIF = b"GIF89a\x01\x00\x01\x00" + b"\x00" * 64
HTML = b"<!doctype html><script>alert(1)</script>"
