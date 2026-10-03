"""`Me`: the signed-in user as the web sees them (04-API.md); and the dob and
gender steps' bodies (T-3.6)."""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator

from app.core.enums import Gender, OnboardingStep, Role, Seeking, UserStatus

_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _iso_date_only(value: object) -> object:
    """A date typed as `YYYY-MM-DD`, nothing else. Pydantic alone would also
    take a number as a Unix timestamp, read in UTC: in India, at the wrong end
    of a day, that is the wrong date of birth."""
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        raise ValueError("must be a date written YYYY-MM-DD")
    return value


IsoDate = Annotated[date, BeforeValidator(_iso_date_only)]


class MeProfile(BaseModel):
    first_name: str | None
    username: str | None
    about: str | None
    hometown: str | None
    city: str | None
    seeking: Seeking | None
    intent_ids: list[int]
    interest_ids: list[int]
    is_hidden: bool
    hide_age: bool
    hide_distance: bool
    show_kudos: bool
    show_gifts: bool


class Me(BaseModel):
    """The age, never the date of birth, and no phone number: no screen shows
    either, so neither leaves the server (D-067's discipline)."""

    id: UUID
    role: Role
    status: UserStatus
    onboarding_step: OnboardingStep
    gender: Gender | None
    age: int | None
    is_verified: bool
    has_pin: bool
    referral_code: str
    balance: int
    profile: MeProfile


class DobSet(BaseModel):
    dob: IsoDate


class GenderSet(BaseModel):
    gender: Gender
