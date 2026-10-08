"""`ed3028467a15` (T-4.12, D-391): `photo_kind_t` rebuilt with `verification`.
The CHECK and the indexes on `photos` that read `kind` stand after exactly as
they stood before, and the downgrade refuses while any face photo exists."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.enums import PhotoKind
from tests.conftest import MakeUser
from tests.modules.onboarding.test_guard import _alembic

FACE_PHOTO = "ed3028467a15"
BEFORE = "15a9b138750b"

# Everything on `photos` that names `kind`: the CHECK, the key index and the
# partial unique index whose predicate reads it.
DEFINITIONS = text(
    """
    select conname as name, pg_get_constraintdef(oid) as definition
    from pg_constraint
    where conrelid = to_regclass('photos') and contype = 'c'
    union all
    select indexname, indexdef from pg_indexes where tablename = 'photos'
    order by name
    """
)
LABELS = text(
    "select e.enumlabel from pg_enum e join pg_type t on t.oid = e.enumtypid "
    "where t.typname = 'photo_kind_t' order by e.enumsortorder"
)


async def _definitions(db: AsyncSession) -> dict[str, str]:
    return {name: definition for name, definition in (await db.execute(DEFINITIONS))}


async def _labels(db: AsyncSession) -> list[str]:
    return list(await db.scalars(LABELS))


async def test_the_rebuild_keeps_the_check_and_the_indexes(db: AsyncSession) -> None:
    """Down to before the kind and up again: the three definitions that read
    `kind` are the same text after as before, and the type has the value."""
    at_head = await _definitions(db)
    assert {
        "ck_photos_public_position_range",
        "ix_photos_user_id_kind_position",
        "uq_photos_public_position",
    } <= set(at_head)
    assert "kind = 'public'" in at_head["uq_photos_public_position"]

    async with db.begin_nested():
        await _alembic(db, command.downgrade, BEFORE)
        before = await _definitions(db)
        assert await _labels(db) == ["public", "private", "selfie"]
        await _alembic(db, command.upgrade, FACE_PHOTO)
        after = await _definitions(db)

    assert before == at_head
    assert after == at_head
    assert await _labels(db) == [kind.value for kind in PhotoKind]
    assert await _labels(db) == ["public", "private", "selfie", "verification"]


async def test_the_downgrade_refuses_while_a_face_photo_exists(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    await db.execute(
        text(
            "insert into photos (id, user_id, kind, raw_key) "
            "values (:id, :user_id, 'verification', 'raw/x')"
        ),
        {"id": uuid.uuid4(), "user_id": user.id},
    )

    with pytest.raises(RuntimeError, match=r"1 photos are face photos") as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert "D-391" in str(refused.value)
    assert "verification" in await _labels(db)
