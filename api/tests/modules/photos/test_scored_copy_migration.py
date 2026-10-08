"""`8243172d0af6` (P-79, D-700): `photos.scored_key`, an approved private
photo's scored copy. Down and up again; the downgrade refuses while any photo
has one, since without the column no deletion would find its file."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from tests.conftest import MakeUser
from tests.modules.onboarding.test_guard import _alembic

SCORED_COPY = "8243172d0af6"
BEFORE = "d4f1d16b2191"

COLUMN = text(
    "select data_type, is_nullable from information_schema.columns "
    "where table_name = 'photos' and column_name = 'scored_key'"
)


async def _column(db: AsyncSession) -> list[tuple[str, str]]:
    return [(row.data_type, row.is_nullable) for row in await db.execute(COLUMN)]


async def test_the_column_goes_and_comes_back(db: AsyncSession) -> None:
    assert await _column(db) == [("text", "YES")]

    async with db.begin_nested():
        await _alembic(db, command.downgrade, BEFORE)
        assert await _column(db) == []
        await _alembic(db, command.upgrade, SCORED_COPY)

    assert await _column(db) == [("text", "YES")]


async def test_the_downgrade_refuses_while_a_scored_copy_exists(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    await db.execute(
        text(
            "insert into photos (id, user_id, kind, raw_key, scored_key, status) "
            "values (:id, :user_id, 'private', 'raw/x', 'scored/x.jpg', 'approved')"
        ),
        {"id": uuid.uuid4(), "user_id": user.id},
    )

    with pytest.raises(RuntimeError, match=r"1 photos have a scored copy") as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert "D-700" in str(refused.value)
    assert await _column(db) == [("text", "YES")]
