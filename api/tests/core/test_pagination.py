"""Cursor pagination (D-270): the cursor, the page and the limit every list uses.

No database here. The ledger's endpoint tests (tests/modules/wallet/test_router.py)
drive the same pieces through a real list: limits, a cursor in a query string,
and pages over entries that share a `created_at`.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import AwareDatetime

from app.core.errors import AppError
from app.core.pagination import Cursor, Page, PageParams

CURSOR = Cursor(tuple[AwareDatetime, UUID])
AT = datetime(2026, 10, 5, 9, 30, 15, 123456, tzinfo=UTC)
ID = UUID("6f1c2a4e-8b3d-4c5e-9f7a-0b1c2d3e4f50")


def _b64(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def _not_a_cursor(cursor: str) -> AppError:
    with pytest.raises(AppError) as refused:
        CURSOR.decode(cursor)
    return refused.value


# --- The cursor --------------------------------------------------------------------


def test_a_cursor_gives_back_exactly_the_key_it_was_made_from() -> None:
    at, id_ = CURSOR.decode(CURSOR.encode((AT, ID)))

    assert (at, id_) == (AT, ID)
    assert at.microsecond == 123456
    assert at.utcoffset() == timedelta(0)


def test_a_cursor_from_another_zone_names_the_same_instant() -> None:
    """Postgres hands back UTC; a key in another zone is still the same moment."""
    ist = AT.astimezone(timezone(timedelta(hours=5, minutes=30)))

    at, _ = CURSOR.decode(CURSOR.encode((ist, ID)))

    assert at == AT


def test_a_cursor_goes_in_a_query_string_as_it_is() -> None:
    """base64url with no padding: nothing a URL would need to escape."""
    cursor = CURSOR.encode((AT, ID))

    assert re.fullmatch(r"[A-Za-z0-9_-]+", cursor)


ISO = AT.isoformat().replace("+00:00", "Z")

REFUSED = {
    "empty": "",
    "not base64": "not a cursor!",
    "base64 of not JSON": _b64("not json"),
    "a key of the wrong length": _b64(json.dumps([ISO, str(ID), 1])),
    "a time with no zone": _b64(json.dumps([ISO.removesuffix("Z"), str(ID)])),
    "a number for the time": _b64(json.dumps([0, str(ID)])),
    "not a uuid": _b64(json.dumps([ISO, "not-a-uuid"])),
    # The right position, written as this API never writes it.
    "spaced JSON": _b64(json.dumps([ISO, str(ID)], separators=(", ", ": "))),
    "an offset for Z": _b64(json.dumps([AT.isoformat(), str(ID)]).replace(" ", "")),
    "padded": CURSOR.encode((AT, ID)) + "==",
}


@pytest.mark.parametrize("cursor", REFUSED.values(), ids=REFUSED.keys())
def test_anything_but_what_the_api_wrote_is_refused(cursor: str) -> None:
    refused = _not_a_cursor(cursor)

    assert refused.code == "VALIDATION_ERROR"
    assert refused.status == 400
    assert refused.details == {
        "fields": [{"field": "cursor", "problem": "isn't a cursor this list gave"}]
    }


def test_the_refused_spellings_name_a_real_position() -> None:
    """The spaced and offset spellings are refused for their spelling alone:
    read leniently, they'd name the very key the API writes."""
    for name in ("spaced JSON", "an offset for Z"):
        cursor = REFUSED[name]
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, id_ = json.loads(raw)
        assert (datetime.fromisoformat(at), UUID(id_)) == (AT, ID), name


# --- The page ----------------------------------------------------------------------


class IntPage(Page[int]):
    """A list of numbers, for these tests."""


def _cursor_for(item: int) -> str:
    return f"after-{item}"


def test_a_row_past_the_limit_means_another_page_follows() -> None:
    page = IntPage.of([5, 4, 3], PageParams(cursor=None, limit=2), _cursor_for)

    assert page.items == [5, 4]
    assert page.next_cursor == "after-4"


def test_a_last_page_that_is_exactly_full_has_no_cursor() -> None:
    page = IntPage.of([5, 4], PageParams(cursor=None, limit=2), _cursor_for)

    assert page.items == [5, 4]
    assert page.next_cursor is None


def test_an_empty_page_has_no_cursor() -> None:
    page = IntPage.of([], PageParams(cursor=None, limit=2), _cursor_for)

    assert page.items == []
    assert page.next_cursor is None


def test_a_list_fetches_one_row_more_than_its_page() -> None:
    assert PageParams(cursor=None, limit=20).fetch == 21


def test_a_page_is_exactly_items_and_next_cursor_under_its_own_name() -> None:
    schema = IntPage.model_json_schema()

    assert schema["title"] == "IntPage"
    assert set(schema["properties"]) == {"items", "next_cursor"}
    assert set(schema["required"]) == {"items", "next_cursor"}
