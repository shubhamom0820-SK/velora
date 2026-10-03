"""`Me`: the signed-in user as the web sees them (04-API.md)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.core.enums import Gender, OnboardingStep, Role, Seeking, UserStatus


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
