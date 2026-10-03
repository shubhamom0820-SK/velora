"""What a PIN may be (D-012, D-069): a pure rule, shared by the service and
the dev seed, so the seeded test woman's PIN is held to it (T-1.15)."""

from __future__ import annotations

import re
from itertools import pairwise

PIN = re.compile(r"[0-9]{4}")

# The 20 most common in DataGenetics' study of 3.4 million four-digit passwords
# from leaked databases, in its order: 26.83% of them between them. Read from
# datagenetics.com/blog/september32012 on 3 October 2026 (T-3.9). Most are
# refused by the shapes below as well; 1004, 2000, 1122 and 2001 only here.
COMMON_PINS = (
    "1234", "1111", "0000", "1212", "7777", "1004", "2000", "4444", "2222", "6969",
    "9999", "3333", "5555", "6666", "1122", "1313", "8888", "4321", "2001", "1010",
)  # fmt: skip


def pin_problem(pin: str) -> str | None:
    """None for a PIN D-069 allows, or why it doesn't, in words with no digit
    in them: an error never repeats a PIN, even one refused (rule 15)."""
    if not PIN.fullmatch(pin):
        return "must be four digits"
    if len(set(pin)) == 1:
        return "is one digit four times"
    steps = {int(b) - int(a) for a, b in pairwise(pin)}
    if steps in ({1}, {-1}):
        return "is a straight run of digits"
    if pin[0] == pin[2] and pin[1] == pin[3]:
        return "is a pair of digits, repeated"
    if pin in COMMON_PINS:
        return "is one of the most common PINs"
    return None
