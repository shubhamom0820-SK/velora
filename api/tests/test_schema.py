"""Database-level guarantees from 03-SCHEMA.md.

T-1.8: extensions and the set_updated_at() trigger function.
T-1.9: the identity and profile tables — the immutable gender/dob trigger, the
username format, the updated_at triggers, partial unique photo slots, and the
one cascading foreign key. T-1.16 adds the remaining constraint tests.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.modules.users.models import User

EXTENSIONS = {"postgis", "pg_trgm", "pgcrypto", "citext"}


async def test_extensions_are_installed(db: AsyncSession) -> None:
    installed = set(
        (await db.execute(text("select extname from pg_extension"))).scalars()
    )

    assert installed >= EXTENSIONS


async def _table_with_the_trigger(db: AsyncSession) -> None:
    """A throwaway table wired up the way every mutable table will be (T-1.9+).
    Created inside the test's transaction, so it is rolled back with it."""
    await db.execute(
        text(
            """
            create table trigger_probe (
                id int primary key,
                note text,
                updated_at timestamptz not null default now()
            )
            """
        )
    )
    await db.execute(
        text(
            "create trigger trg_trigger_probe_updated_at before update on trigger_probe "
            "for each row execute function set_updated_at()"
        )
    )


async def test_set_updated_at_refreshes_the_column_on_update(db: AsyncSession) -> None:
    await _table_with_the_trigger(db)
    await db.execute(
        text("insert into trigger_probe values (1, 'first', '2000-01-01T00:00:00Z')")
    )

    await db.execute(text("update trigger_probe set note = 'second' where id = 1"))

    updated_at, now = (
        await db.execute(
            text("select updated_at, now() from trigger_probe where id = 1")
        )
    ).one()
    # now() is the transaction's start time, so the trigger's value equals it.
    assert updated_at == now


async def test_set_updated_at_leaves_inserts_alone(db: AsyncSession) -> None:
    """The trigger fires on UPDATE only; an explicit insert value is kept."""
    await _table_with_the_trigger(db)
    await db.execute(
        text("insert into trigger_probe values (1, 'first', '2000-01-01T00:00:00Z')")
    )

    updated_at = await db.scalar(
        text("select updated_at from trigger_probe where id = 1")
    )

    assert updated_at is not None
    assert updated_at.year == 2000


# --- T-1.9 --------------------------------------------------------------------

CHECK_VIOLATION = "23514"
FOREIGN_KEY_VIOLATION = "23503"
UNIQUE_VIOLATION = "23505"


def _sqlstate(error: IntegrityError) -> str | None:
    orig = error.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def _rejected(
    db: AsyncSession, sql: str, params: dict[str, object] | None = None
) -> str | None:
    """Run `sql` in its own savepoint, expect the database to refuse it, and
    return the SQLSTATE. The savepoint keeps the rest of the test usable."""
    with pytest.raises(IntegrityError) as excinfo:
        async with db.begin_nested():
            await db.execute(text(sql), params or {})
    return _sqlstate(excinfo.value)


async def _user(db: AsyncSession, **fields: object) -> User:
    tag = uuid.uuid4().hex[:12]
    user = User(
        phone_hash=f"hash-{tag}",
        phone_enc=b"enc",
        referral_code=f"ref{tag}",
        **fields,
    )
    db.add(user)
    await db.flush()
    return user


# gender and dob are immutable once set (T-1.16's item, covered here).


async def test_gender_and_dob_can_be_set_once(db: AsyncSession) -> None:
    user = await _user(db)

    await db.execute(
        text("update users set gender = 'male', dob = '2000-01-01' where id = :id"),
        {"id": user.id},
    )

    row = (
        await db.execute(
            text("select gender, dob from users where id = :id"), {"id": user.id}
        )
    ).one()
    assert row == ("male", date(2000, 1, 1))


@pytest.mark.parametrize(
    ("column", "first", "second"),
    [
        ("gender", "male", "female"),
        # asyncpg needs real dates; a string is refused before the trigger runs.
        ("dob", date(2000, 1, 1), date(1999, 1, 1)),
    ],
)
async def test_identity_cannot_change_once_set(
    db: AsyncSession, column: str, first: object, second: object
) -> None:
    user = await _user(db)
    await db.execute(
        text(f"update users set {column} = :v where id = :id"),
        {"v": first, "id": user.id},
    )

    state = await _rejected(
        db,
        f"update users set {column} = :v where id = :id",
        {"v": second, "id": user.id},
    )

    # check_violation -> IntegrityError, which T-3.6 maps to IMMUTABLE_FIELD.
    assert state == CHECK_VIOLATION


@pytest.mark.parametrize("column", ["gender", "dob"])
async def test_identity_cannot_be_cleared_once_set(
    db: AsyncSession, column: str
) -> None:
    user = await _user(db, gender=Gender.MALE, dob=date(2000, 1, 1))

    state = await _rejected(
        db, f"update users set {column} = null where id = :id", {"id": user.id}
    )

    assert state == CHECK_VIOLATION


async def test_saving_the_same_values_is_allowed(db: AsyncSession) -> None:
    user = await _user(db, gender=Gender.FEMALE, dob=date(2001, 5, 5))

    await db.execute(
        text(
            "update users set gender = 'female', dob = '2001-05-05', pin_failed = 1 where id = :id"
        ),
        {"id": user.id},
    )


async def test_enum_columns_store_values_not_member_names(db: AsyncSession) -> None:
    """SQLAlchemy would write 'FEMALE' by default; the database needs 'female'."""
    user = await _user(db, gender=Gender.FEMALE)

    raw = await db.scalar(
        text("select gender::text from users where id = :id"), {"id": user.id}
    )
    loaded = await db.scalar(select(User.gender).where(User.id == user.id))

    assert raw == "female"
    assert loaded is Gender.FEMALE


# username format (T-1.16's item, covered here).


@pytest.mark.parametrize(
    "username", ["abc", "a" * 21, "Priya", "priya-k", "priya k", "priya!"]
)
async def test_bad_usernames_are_rejected(db: AsyncSession, username: str) -> None:
    user = await _user(db)

    state = await _rejected(
        db,
        "insert into profiles (user_id, username) values (:id, :u)",
        {"id": user.id, "u": username},
    )

    assert state == CHECK_VIOLATION


@pytest.mark.parametrize("username", ["priya", "priya_k.99", "a" * 20, "abcd"])
async def test_good_usernames_are_accepted(db: AsyncSession, username: str) -> None:
    user = await _user(db)

    await db.execute(
        text("insert into profiles (user_id, username) values (:id, :u)"),
        {"id": user.id, "u": username},
    )


# updated_at triggers: exactly the five mutable tables, nothing else.


async def test_updated_at_triggers_are_on_exactly_the_mutable_tables(
    db: AsyncSession,
) -> None:
    rows = await db.execute(
        text(
            """
            select c.relname from pg_trigger t
            join pg_class c on c.oid = t.tgrelid
            join pg_proc p on p.oid = t.tgfoid
            where not t.tgisinternal and p.proname = 'set_updated_at'
            """
        )
    )

    assert set(rows.scalars()) == {
        "users",
        "sessions",
        "profiles",
        "photos",
        "verifications",
    }


# photos: one live public photo per slot.


async def _photo(
    db: AsyncSession, user_id: uuid.UUID, position: int, status: str = "pending"
) -> None:
    await db.execute(
        text(
            "insert into photos (user_id, kind, position, raw_key, status) "
            "values (:u, 'public', :p, :k, :s)"
        ),
        {"u": user_id, "p": position, "k": uuid.uuid4().hex, "s": status},
    )


async def test_two_live_public_photos_cannot_share_a_slot(db: AsyncSession) -> None:
    user = await _user(db)
    await _photo(db, user.id, 0)

    state = await _rejected(
        db,
        "insert into photos (user_id, kind, position, raw_key) values (:u, 'public', 0, 'k2')",
        {"u": user.id},
    )

    assert state == UNIQUE_VIOLATION


async def test_a_rejected_photo_frees_its_slot(db: AsyncSession) -> None:
    user = await _user(db)
    await _photo(db, user.id, 0, status="rejected")

    await _photo(db, user.id, 0)


async def test_public_photo_position_is_0_to_5(db: AsyncSession) -> None:
    user = await _user(db)

    state = await _rejected(
        db,
        "insert into photos (user_id, kind, position, raw_key) values (:u, 'public', 6, 'k')",
        {"u": user.id},
    )

    assert state == CHECK_VIOLATION


async def test_a_public_photo_must_have_a_position(db: AsyncSession) -> None:
    """P-13: NULL passed the old `position BETWEEN 0 AND 5` check (unknown)."""
    user = await _user(db)

    state = await _rejected(
        db,
        "insert into photos (user_id, kind, position, raw_key) "
        "values (:u, 'public', null, 'k')",
        {"u": user.id},
    )

    assert state == CHECK_VIOLATION


async def test_other_photo_kinds_need_no_position(db: AsyncSession) -> None:
    user = await _user(db)

    await db.execute(
        text(
            "insert into photos (user_id, kind, position, raw_key) "
            "values (:u, 'selfie', null, 'k')"
        ),
        {"u": user.id},
    )


# foreign keys: sessions cascade with their user; everything else restricts.


async def test_sessions_are_deleted_with_their_user(db: AsyncSession) -> None:
    user = await _user(db)
    await db.execute(
        text(
            "insert into sessions (user_id, family_id, token_hash, expires_at) "
            "values (:u, gen_random_uuid(), 'tok', now() + interval '1 day')"
        ),
        {"u": user.id},
    )

    await db.execute(text("delete from users where id = :u"), {"u": user.id})

    remaining = await db.scalar(
        text("select count(*) from sessions where user_id = :u"), {"u": user.id}
    )
    assert remaining == 0


async def test_a_user_with_a_profile_cannot_be_deleted(db: AsyncSession) -> None:
    """We don't hard-delete users (03-SCHEMA.md): the profile FK restricts."""
    user = await _user(db)
    await db.execute(text("insert into profiles (user_id) values (:u)"), {"u": user.id})

    state = await _rejected(db, "delete from users where id = :u", {"u": user.id})

    assert state == FOREIGN_KEY_VIOLATION
