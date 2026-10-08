"""`GET /v1/prices` — the response (04-API.md); and `shown_price`, the field
every paid action's request carries (P-56, D-600)."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, RootModel

# The price the screen showed for this action, in Velas: compared with the
# price now, never charged (`pricing.service.charge`). Absent means 0, "no
# price was shown", so a man's paid action sent without it is refused.
ShownPrice = Annotated[int, Field(ge=0, le=1_000_000)]


class Prices(RootModel[dict[str, int]]):
    """`{action: credits}`: what each active action costs a man, in Velas.
    A woman pays nothing for any of them (D-098)."""
