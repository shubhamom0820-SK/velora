"""`GET /v1/prices` — the response (04-API.md)."""

from __future__ import annotations

from pydantic import RootModel


class Prices(RootModel[dict[str, int]]):
    """`{action: credits}`: what each active action costs a man, in Velas.
    A woman pays nothing for any of them (D-098)."""
