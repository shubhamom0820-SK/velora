"""Request and response bodies for referrals (04-API, T-8.6)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Bounded, never a format: the seed's three test accounts carry readable codes
# outside the generated alphabet, and apply only looks a code up (T-3.3).
Code = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
]


class ApplyReferral(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Code


class ReferralsMe(BaseModel):
    """The user's own code, how many applied it, and how many of those were
    rewarded: counted for a woman too, who is never paid (D-690)."""

    code: str
    invited: int
    rewarded: int
