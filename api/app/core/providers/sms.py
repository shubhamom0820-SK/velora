"""SMS: the one-time sign-in code, Path B (D-035, T-3.2).

Launch sign-in is Firebase (T-3.14), which sends its own SMS from the browser.
This provider is for MSG91, once DLT registration is approved (P-46).
"""

from __future__ import annotations

import sys
from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol

from app.core.config import REAL_SMS_TO_ANYONE_IN, Settings


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
    """MSG91 over httpx. Not built until P-46, after DLT (P-0.4) and the account
    (P-0.5).

    Until then it raises when called, never pretends to send: a stub reporting
    success would mean "code sent" with no SMS, found only when a real person
    waits at an empty inbox (D-066). A test holds it to raising.
    """

    async def send_otp(self, phone: str, code: str) -> None:
        raise NotImplementedError("MSG91 SMS arrives with P-46.")


class SmsRecipientNotAllowed(Exception):
    """Locally, a real provider was asked to text a number nobody listed in
    `SMS_LOCAL_ALLOWED_TO`. The message names the setting, never the number."""

    def __init__(self) -> None:
        super().__init__(
            "Locally, a real SMS provider texts only the numbers in "
            "SMS_LOCAL_ALLOWED_TO (D-064)."
        )


class LocallyAllowedSms:
    """A real provider that, locally, texts only the numbers a developer listed.

    India reserves no fictional range, so the seed's `+91 90000 00xxx` numbers
    may belong to real people (D-064). Any number not in `allowed` is refused
    before the provider is called.
    """

    def __init__(self, real: SmsProvider, allowed: Collection[str]) -> None:
        self.real = real
        self.allowed = frozenset(allowed)

    async def send_otp(self, phone: str, code: str) -> None:
        if phone not in self.allowed:
            raise SmsRecipientNotAllowed()
        await self.real.send_otp(phone, code)


def guard_real_sms(real: SmsProvider, settings: Settings) -> SmsProvider:
    """`real` as the environment may use it: as it is where a real provider may
    text anyone (`REAL_SMS_TO_ANYONE_IN`), and limited to `SMS_LOCAL_ALLOWED_TO`
    everywhere else, local included. An allowlist (rule 16): an environment
    named later is limited until someone decides otherwise."""
    if settings.ENV in REAL_SMS_TO_ANYONE_IN:
        return real
    return LocallyAllowedSms(real, settings.SMS_LOCAL_ALLOWED_TO)
