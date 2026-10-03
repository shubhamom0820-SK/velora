"""Sign-in requests and responses (04-API.md, Auth & session)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.modules.users.schemas import Me

# Room for any way a person types an Indian number ("0091 (98765) 43210"), and
# short enough that nothing long reaches the parser.
PHONE_INPUT_MAX = 32


class OtpSend(BaseModel):
    phone: Annotated[str, StringConstraints(max_length=PHONE_INPUT_MAX)]


class OtpSent(BaseModel):
    """The same for every number, banned or unknown included (D-066): a
    different answer would make this endpoint a ban checker."""

    resend_after_s: int


class OtpVerify(BaseModel):
    phone: Annotated[str, StringConstraints(max_length=PHONE_INPUT_MAX)]
    # Exactly six digits (D-066). Anything else is refused before it can count
    # as a wrong try.
    otp: Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]


class SignedIn(BaseModel):
    """A sign-in's body. The refresh token and CSRF value go in cookies, never
    here: the refresh token is HttpOnly, out of the page's reach (D-024)."""

    access_token: str
    user: Me


class AccessToken(BaseModel):
    """A refresh's body: the new access token. The rotated refresh token and
    CSRF value arrive as cookies."""

    access_token: str


# Four digits (D-012). Anything else is refused before it can count as a try.
PinDigits = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")]


class PinSet(BaseModel):
    pin: PinDigits
    # Needed to change a PIN, except within 10 minutes of a fresh sign-in
    # (D-069).
    current_pin: PinDigits | None = None


class PinVerify(BaseModel):
    pin: PinDigits
