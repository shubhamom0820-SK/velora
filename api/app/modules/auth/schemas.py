"""Sign-in requests and responses (04-API.md, Auth & session)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

# Room for any way a person types an Indian number ("0091 (98765) 43210"), and
# short enough that nothing long reaches the parser.
PHONE_INPUT_MAX = 32


class OtpSend(BaseModel):
    phone: Annotated[str, StringConstraints(max_length=PHONE_INPUT_MAX)]


class OtpSent(BaseModel):
    """The same for every number, banned or unknown included (D-066): a
    different answer would make this endpoint a ban checker."""

    resend_after_s: int
