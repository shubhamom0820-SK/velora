"""Cursor pagination, for every list the API returns (02-ARCHITECTURE §3, D-270).

A list takes `?cursor=&limit=` through `page_params` and answers with a page,
`{items, next_cursor}`, `next_cursor` null on the last page. Each list's page is
a named subclass of `Page[T]`, `<Item>Page`. The first list was the wallet's
ledger (T-5.3); every later one uses these.

- **The cursor is the last item's sort key**, as JSON, then base64url without
  padding: opaque to the client, which only ever sends back what it was given.
  `Cursor(shape)` encodes and decodes one list's key, e.g.
  `Cursor(tuple[AwareDatetime, UUID])` for `(created_at, id)`. A cursor is
  accepted only if it is exactly what this API would write for the position it
  names; anything else is `VALIDATION_ERROR` on `cursor`.
- **It is not signed.** A cursor is a position, never a permission: every list
  filters by who is asking as well, so an edited cursor only moves within the
  caller's own list. Signing would need a secret to guard nothing.
- **`limit` is 1 to 50, 20 when absent; outside that, `VALIDATION_ERROR`.**
  Never clamped: a caller asking for 500 would get 50 and believe it had all.
- **Each list fetches `limit + 1` rows** (`PageParams.fetch`): the extra row
  only says another page follows, so a last page that is exactly full still
  ends with a null cursor.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Self

from fastapi import Query
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.core.errors import invalid_field

DEFAULT_LIMIT = 20
MAX_LIMIT = 50
# Longer than any cursor this API writes; the exact check in `decode` does the rest.
CURSOR_MAX_LENGTH = 256


class Page[ItemT](BaseModel):
    """One page of a list, in the order the list defines.

    Each list names its own: `class LedgerEntryPage(Page[LedgerEntry])`, so the
    OpenAPI schema and the web's types call it `LedgerEntryPage`, never
    Pydantic's `Page_LedgerEntry_` (D-270).
    """

    items: list[ItemT]
    # Send it back as `?cursor=` for the next page; null on the last.
    next_cursor: str | None

    @classmethod
    def of(
        cls,
        rows: Sequence[ItemT],
        params: PageParams,
        cursor_for: Callable[[ItemT], str],
    ) -> Self:
        """The page from `rows`, fetched with `params.fetch`: the first
        `params.limit`, and the cursor after the last of them only if a row
        beyond it came back."""
        items = list(rows[: params.limit])
        more = len(rows) > params.limit
        return cls(items=items, next_cursor=cursor_for(items[-1]) if more else None)


@dataclass(frozen=True)
class PageParams:
    cursor: str | None
    limit: int

    @property
    def fetch(self) -> int:
        """Rows to ask the database for: one more than the page."""
        return self.limit + 1


def page_params(
    cursor: Annotated[
        str | None, Query(min_length=1, max_length=CURSOR_MAX_LENGTH)
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PageParams:
    """A list's `?cursor=&limit=`, as a dependency. A limit outside 1 to 50 is
    the schema's own `VALIDATION_ERROR`, never clamped (D-270)."""
    return PageParams(cursor=cursor, limit=limit)


class Cursor[KeyT]:
    """One list's cursor: its sort key, as `shape` describes it."""

    def __init__(self, shape: type[KeyT]) -> None:
        self._adapter: TypeAdapter[KeyT] = TypeAdapter(shape)

    def encode(self, key: KeyT) -> str:
        raw = self._adapter.dump_json(key)
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    def decode(self, cursor: str) -> KeyT:
        """The key `cursor` names, or `VALIDATION_ERROR` on `cursor`: only
        exactly what `encode` writes is accepted."""
        try:
            raw = base64.b64decode(
                cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
            )
            key = self._adapter.validate_json(raw, strict=True)
        except (ValueError, binascii.Error, ValidationError):
            raise _not_a_cursor() from None
        if self.encode(key) != cursor:
            raise _not_a_cursor()
        return key


def _not_a_cursor() -> Exception:
    return invalid_field("cursor", "isn't a cursor this list gave")
