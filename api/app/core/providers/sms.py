"""SMS: the one-time sign-in code, Path B (D-035, T-3.2).

Launch sign-in is Firebase (T-3.14), which sends its own SMS from the browser.
This provider is for MSG91, once DLT registration is approved.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol


class SmsProvider(Protocol):
    async def send_otp(self, phone: str, code: str) -> None:
        """Send `code` to `phone`, an E.164 number such as `+919812345678`."""
        ...


@dataclass(frozen=True)
class SentOtp:
    phone: str
    code: str


def mask_phone(phone: str) -> str:
    """`+919812345678` → `+91******5678`: enough to tell test numbers apart."""
    return phone[:3] + "*" * max(len(phone) - 7, 0) + phone[-4:]


class FakeSms:
    """Records every code instead of sending it.

    With `echo` (only `build_providers` sets it, and fakes only run locally),
    it also prints the code to the developer's terminal, so local sign-in works
    without a phone. Straight to stderr, never through the logger: OTPs must
    not reach any log (CLAUDE.md rule 15), and a terminal isn't one.
    """

    def __init__(self, *, echo: bool = False) -> None:
        self.echo = echo
        self.sent: list[SentOtp] = []

    async def send_otp(self, phone: str, code: str) -> None:
        self.sent.append(SentOtp(phone, code))
        if self.echo:
            sys.stderr.write(f"[fake sms] code for {mask_phone(phone)}: {code}\n")

    def last_code(self, phone: str) -> str | None:
        """The last code sent to `phone`, or None if none was."""
        for otp in reversed(self.sent):
            if otp.phone == phone:
                return otp.code
        return None


class Msg91Sms:
    """MSG91 over httpx. Not built yet."""

    async def send_otp(self, phone: str, code: str) -> None:
        raise NotImplementedError("MSG91 SMS arrives with T-3.2.")
