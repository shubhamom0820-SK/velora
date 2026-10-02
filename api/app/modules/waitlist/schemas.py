"""`POST /v1/waitlist` — request and response (04-API.md)."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

# The longest address SMTP can carry (RFC 5321).
EMAIL_MAX = 254
# The same bound as a profile's city (T-3.7).
CITY_MAX = 40

# A shape, not RFC 5322: something@something.something, no spaces, one @. A
# junk address that passes just never gets the email; a stricter check would
# need a new dependency to turn away almost nothing more (T-2.3).
_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistJoin(BaseModel):
    email: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=EMAIL_MAX),
    ]
    # Optional. Where people want Velora outside the launch city is the input
    # to choosing a second one (the founder, 2 October 2026), and the copy
    # promises to write "when Velora opens near you".
    city: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=CITY_MAX)]
        | None
    ) = None

    @field_validator("email")
    @classmethod
    def _looks_like_an_email(cls, v: str) -> str:
        if not _EMAIL_SHAPE.fullmatch(v):
            raise ValueError("isn't an email address")
        return v

    @field_validator("city")
    @classmethod
    def _blank_city_is_none(cls, v: str | None) -> str | None:
        return v or None


class WaitlistJoined(BaseModel):
    """Empty, and the same for a new email and one already on the list (D-057).

    A different answer for a repeat would make this endpoint an email checker:
    anyone could find out whether an address is on our list.
    """
