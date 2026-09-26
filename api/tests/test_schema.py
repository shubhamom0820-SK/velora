"""Database-level guarantees from 03-SCHEMA.md.

T-1.8: extensions and the set_updated_at() trigger function.
T-1.9: the identity and profile tables — the immutable gender/dob trigger, the
username format, the updated_at triggers, partial unique photo slots, and the
one cascading foreign key.
T-1.10: discovery and conversations — ordered pairs, one thread per pair, the
two CHECKs that keep a knotted thread permanent and an active one expiring,
message dedupe.
T-1.11: album, kudos, gifts and safety — one live album request per pair, no
acting on yourself, never-negative charges, report and fraud-score bounds.
T-1.16 adds the remaining constraint tests.
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
        # T-1.9
        "users",
        "sessions",
        "profiles",
        "photos",
        "verifications",
        # T-1.10 (profile_views and thread_clears carry their own timestamp)
        "matches",
        "threads",
        "messages",
        # T-1.11 (gifts is catalogue seed data, like areas and interests)
        "album_requests",
        "reports",
        "fraud_scores",
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


# --- T-1.10 -------------------------------------------------------------------


async def _pair(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Two users, returned as (low, high) — pairs are stored ordered."""
    a, b = await _user(db), await _user(db)
    low, high = sorted((a.id, b.id))
    return low, high


async def _thread(
    db: AsyncSession, low: uuid.UUID, high: uuid.UUID, **overrides: object
) -> uuid.UUID:
    values: dict[str, object] = {
        "low": low,
        "high": high,
        "status": "active",
        "expires": "now() + interval '24 hours'",
    }
    values.update(overrides)
    expires = values.pop("expires")
    thread_id = await db.scalar(
        text(
            "insert into threads (user_low, user_high, origin, opened_by, status, "
            f"expires_at) values (:low, :high, 'match', :low, :status, {expires}) "
            "returning id"
        ),
        values,
    )
    assert isinstance(thread_id, uuid.UUID)
    return thread_id


# Ordered pairs: user_low < user_high (T-1.16's item, covered here).


@pytest.mark.parametrize("table", ["threads", "matches"])
async def test_pair_must_be_ordered(db: AsyncSession, table: str) -> None:
    low, high = await _pair(db)
    extra = (
        ", origin, opened_by, expires_at) values (:a, :b, 'match', :a, now() + interval '1 day')"
        if table == "threads"
        else ") values (:a, :b)"
    )

    reversed_state = await _rejected(
        db, f"insert into {table} (user_low, user_high{extra}", {"a": high, "b": low}
    )
    equal_state = await _rejected(
        db, f"insert into {table} (user_low, user_high{extra}", {"a": low, "b": low}
    )

    assert reversed_state == CHECK_VIOLATION
    assert equal_state == CHECK_VIOLATION


async def test_one_thread_per_pair(db: AsyncSession) -> None:
    low, high = await _pair(db)
    await _thread(db, low, high)

    state = await _rejected(
        db,
        "insert into threads (user_low, user_high, origin, opened_by, expires_at) "
        "values (:low, :high, 'dm', :high, now() + interval '1 day')",
        {"low": low, "high": high},
    )

    assert state == UNIQUE_VIOLATION


async def test_one_match_per_pair(db: AsyncSession) -> None:
    low, high = await _pair(db)
    await db.execute(
        text("insert into matches (user_low, user_high) values (:l, :h)"),
        {"l": low, "h": high},
    )

    state = await _rejected(
        db,
        "insert into matches (user_low, user_high) values (:l, :h)",
        {"l": low, "h": high},
    )

    assert state == UNIQUE_VIOLATION


# The Velora promise, guarded from both sides (D-003).


async def test_a_knotted_thread_cannot_carry_an_expiry(db: AsyncSession) -> None:
    """Otherwise the expiry cron would kill a conversation both people were
    told is permanent."""
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)

    state = await _rejected(
        db,
        "update threads set status = 'knotted', knotted_at = now() where id = :t",
        {"t": thread_id},
    )

    assert state == CHECK_VIOLATION


async def test_a_knotted_thread_needs_knotted_at(db: AsyncSession) -> None:
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)

    state = await _rejected(
        db,
        "update threads set status = 'knotted', expires_at = null where id = :t",
        {"t": thread_id},
    )

    assert state == CHECK_VIOLATION


async def test_knotting_properly_is_allowed(db: AsyncSession) -> None:
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)

    await db.execute(
        text(
            "update threads set status = 'knotted', knotted_at = now(), "
            "expires_at = null where id = :t"
        ),
        {"t": thread_id},
    )


async def test_an_active_thread_must_expire(db: AsyncSession) -> None:
    """Otherwise it would sit active forever and break the 24-hour promise."""
    low, high = await _pair(db)

    state = await _rejected(
        db,
        "insert into threads (user_low, user_high, origin, opened_by) "
        "values (:low, :high, 'match', :low)",
        {"low": low, "high": high},
    )

    assert state == CHECK_VIOLATION


async def test_untying_back_to_active_needs_a_fresh_expiry(db: AsyncSession) -> None:
    """Untie (04-API: DELETE /threads/{id}/knot) returns a Velora to active."""
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)
    await db.execute(
        text(
            "update threads set status = 'knotted', knotted_at = now(), "
            "expires_at = null where id = :t"
        ),
        {"t": thread_id},
    )

    no_expiry = await _rejected(
        db, "update threads set status = 'active' where id = :t", {"t": thread_id}
    )
    await db.execute(
        text(
            "update threads set status = 'active', "
            "expires_at = now() + interval '24 hours' where id = :t"
        ),
        {"t": thread_id},
    )

    assert no_expiry == CHECK_VIOLATION


# Messages.


async def _message(
    db: AsyncSession,
    thread_id: uuid.UUID,
    sender_id: uuid.UUID,
    client_msg_id: uuid.UUID,
    body: str = "hi",
) -> None:
    await db.execute(
        text(
            "insert into messages (thread_id, sender_id, kind, body, client_msg_id) "
            "values (:t, :s, 'text', :b, :c)"
        ),
        {"t": thread_id, "s": sender_id, "b": body, "c": client_msg_id},
    )


async def test_a_retried_send_is_stored_once(db: AsyncSession) -> None:
    """(sender_id, client_msg_id) is unique — T-1.16's item, covered here."""
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)
    client_msg_id = uuid.uuid4()
    await _message(db, thread_id, low, client_msg_id)

    state = await _rejected(
        db,
        "insert into messages (thread_id, sender_id, kind, body, client_msg_id) "
        "values (:t, :s, 'text', 'hi again', :c)",
        {"t": thread_id, "s": low, "c": client_msg_id},
    )

    assert state == UNIQUE_VIOLATION


async def test_two_senders_may_reuse_a_client_msg_id(db: AsyncSession) -> None:
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)
    shared = uuid.uuid4()

    await _message(db, thread_id, low, shared)
    await _message(db, thread_id, high, shared)


async def test_message_body_is_at_most_2000_characters(db: AsyncSession) -> None:
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)
    await _message(db, thread_id, low, uuid.uuid4(), body="x" * 2000)

    state = await _rejected(
        db,
        "insert into messages (thread_id, sender_id, kind, body, client_msg_id) "
        "values (:t, :s, 'text', :b, :c)",
        {"t": thread_id, "s": low, "b": "x" * 2001, "c": uuid.uuid4()},
    )

    assert state == CHECK_VIOLATION


# Swipes, and the FKs added to the doc's shorthand tables (T-1.10 Q2).


async def test_one_swipe_per_pair(db: AsyncSession) -> None:
    low, high = await _pair(db)
    await db.execute(
        text("insert into swipes (swiper_id, target_id, dir) values (:a, :b, 'like')"),
        {"a": low, "b": high},
    )

    state = await _rejected(
        db,
        "insert into swipes (swiper_id, target_id, dir) values (:a, :b, 'pass')",
        {"a": low, "b": high},
    )

    assert state == UNIQUE_VIOLATION


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        (
            "profile_views",
            "(viewer_id, viewed_id, last_viewed_at) values (:u, :x, now())",
        ),
        ("liked_you_reveals", "(viewer_id, liker_id) values (:u, :x)"),
        ("thread_clears", "(user_id, thread_id, cleared_at) values (:u, :x, now())"),
        ("message_unlocks", "(user_id, message_id) values (:u, :x)"),
    ],
)
async def test_shorthand_tables_reject_dangling_references(
    db: AsyncSession, table: str, columns: str
) -> None:
    user = await _user(db)

    state = await _rejected(
        db, f"insert into {table} {columns}", {"u": user.id, "x": uuid.uuid4()}
    )

    assert state == FOREIGN_KEY_VIOLATION


# --- T-1.11 -------------------------------------------------------------------


async def _gift(db: AsyncSession, gift_id: str = "test-rose", credits: int = 2) -> str:
    """The catalogue is empty until T-1.14 seeds it; add one inside the test."""
    await db.execute(
        text(
            "insert into gifts (id, label, asset, credits) "
            "values (:id, 'Rose', 'rose', :c)"
        ),
        {"id": gift_id, "c": credits},
    )
    return gift_id


async def _album_request(
    db: AsyncSession, requester: uuid.UUID, owner: uuid.UUID, status: str = "pending"
) -> None:
    await db.execute(
        text(
            "insert into album_requests (requester_id, owner_id, status) "
            "values (:r, :o, :s)"
        ),
        {"r": requester, "o": owner, "s": status},
    )


# Album requests.


@pytest.mark.parametrize("live", ["pending", "granted"])
async def test_one_live_album_request_per_pair(db: AsyncSession, live: str) -> None:
    low, high = await _pair(db)
    await _album_request(db, low, high, status=live)

    state = await _rejected(
        db,
        "insert into album_requests (requester_id, owner_id) values (:r, :o)",
        {"r": low, "o": high},
    )

    assert state == UNIQUE_VIOLATION


@pytest.mark.parametrize("finished", ["declined", "revoked"])
async def test_a_finished_album_request_frees_the_pair(
    db: AsyncSession, finished: str
) -> None:
    low, high = await _pair(db)
    await _album_request(db, low, high, status=finished)

    await _album_request(db, low, high)


# No acting on yourself (T-1.11 Q4).


@pytest.mark.parametrize(
    ("table", "sql"),
    [
        ("album_requests", "(requester_id, owner_id) values (:u, :u)"),
        (
            "kudos",
            "(from_id, to_id, kind, thread_id) values (:u, :u, 'genuinely_funny', :t)",
        ),
        ("gift_sends", "(sender_id, recipient_id, gift_id) values (:u, :u, :g)"),
        ("blocks", "(blocker_id, blocked_id) values (:u, :u)"),
        ("reports", "(reporter_id, reported_id, reason) values (:u, :u, 'fake')"),
    ],
)
async def test_nobody_can_act_on_themselves(
    db: AsyncSession, table: str, sql: str
) -> None:
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)
    gift_id = await _gift(db)

    state = await _rejected(
        db, f"insert into {table} {sql}", {"u": low, "t": thread_id, "g": gift_id}
    )

    assert state == CHECK_VIOLATION


# Charges are never negative (T-1.11 Q4).


async def test_album_request_charge_is_never_negative(db: AsyncSession) -> None:
    low, high = await _pair(db)

    state = await _rejected(
        db,
        "insert into album_requests (requester_id, owner_id, credits_charged) "
        "values (:r, :o, -1)",
        {"r": low, "o": high},
    )

    assert state == CHECK_VIOLATION


async def test_gift_send_charge_is_never_negative(db: AsyncSession) -> None:
    low, high = await _pair(db)
    gift_id = await _gift(db)

    state = await _rejected(
        db,
        "insert into gift_sends (sender_id, recipient_id, gift_id, credits_charged) "
        "values (:s, :r, :g, -2)",
        {"s": low, "r": high, "g": gift_id},
    )

    assert state == CHECK_VIOLATION


# Kudos.


async def test_one_kudos_per_pair(db: AsyncSession) -> None:
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)
    sql = "insert into kudos (from_id, to_id, kind, thread_id) values (:f, :t, :k, :th)"
    await db.execute(
        text(sql), {"f": low, "t": high, "k": "genuinely_funny", "th": thread_id}
    )

    state = await _rejected(
        db, sql, {"f": low, "t": high, "k": "really_thoughtful", "th": thread_id}
    )

    assert state == UNIQUE_VIOLATION


# Gifts: prices are data (D-016), so only "never negative" is enforced.


async def test_gift_price_is_never_negative(db: AsyncSession) -> None:
    state = await _rejected(
        db,
        "insert into gifts (id, label, asset, credits) values ('bad', 'Bad', 'x', -1)",
    )

    assert state == CHECK_VIOLATION


async def test_a_gift_needs_a_label_and_an_asset(db: AsyncSession) -> None:
    """A gift with no label can't be rendered (T-1.11 Q6)."""
    no_label = await _rejected(
        db, "insert into gifts (id, asset, credits) values ('no-label', 'x', 0)"
    )
    no_asset = await _rejected(
        db, "insert into gifts (id, label, credits) values ('no-asset', 'X', 0)"
    )

    assert no_label == "23502"  # not_null_violation
    assert no_asset == "23502"


async def test_catalogue_defaults(db: AsyncSession) -> None:
    await db.execute(
        text("insert into gifts (id, label, asset, credits) values ('d', 'D', 'd', 0)")
    )

    sort, active = (
        await db.execute(text("select sort, active from gifts where id = 'd'"))
    ).one()

    assert (sort, active) == (0, True)


async def test_a_gift_send_needs_a_real_gift(db: AsyncSession) -> None:
    low, high = await _pair(db)

    state = await _rejected(
        db,
        "insert into gift_sends (sender_id, recipient_id, gift_id) "
        "values (:s, :r, 'no-such-gift')",
        {"s": low, "r": high},
    )

    assert state == FOREIGN_KEY_VIOLATION


# Reports.


async def test_report_details_at_most_500(db: AsyncSession) -> None:
    low, high = await _pair(db)

    state = await _rejected(
        db,
        "insert into reports (reporter_id, reported_id, reason, details) "
        "values (:a, :b, 'scam', :d)",
        {"a": low, "b": high, "d": "x" * 501},
    )

    assert state == CHECK_VIOLATION


async def test_report_action_is_one_of_four(db: AsyncSession) -> None:
    low, high = await _pair(db)
    sql = (
        "insert into reports (reporter_id, reported_id, reason, action) "
        "values (:a, :b, 'scam', :act)"
    )

    for action in ("freeze", "ban", "warn", "none"):
        async with db.begin_nested():
            await db.execute(text(sql), {"a": low, "b": high, "act": action})
    state = await _rejected(db, sql, {"a": low, "b": high, "act": "delete"})

    assert state == CHECK_VIOLATION


# Fraud (D-031): the score is 0-100; bands are policy, not a CHECK.


@pytest.mark.parametrize("score", [-1, 101])
async def test_fraud_score_is_0_to_100(db: AsyncSession, score: int) -> None:
    user = await _user(db)

    state = await _rejected(
        db,
        "insert into fraud_scores (user_id, score) values (:u, :s)",
        {"u": user.id, "s": score},
    )

    assert state == CHECK_VIOLATION


# FKs spelled out on the shorthand tables (T-1.10's ruling, applied again).


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("blocks", "(blocker_id, blocked_id) values (:u, :x)"),
        ("fraud_scores", "(user_id) values (:x)"),
        ("fraud_events", "(user_id, signal, weight) values (:x, 'burst', 10)"),
        (
            "reports",
            "(reporter_id, reported_id, reason, thread_id) values (:u, :u2, 'other', :x)",
        ),
    ],
)
async def test_shorthand_references_are_real(
    db: AsyncSession, table: str, columns: str
) -> None:
    low, high = await _pair(db)

    state = await _rejected(
        db, f"insert into {table} {columns}", {"u": low, "u2": high, "x": uuid.uuid4()}
    )

    assert state == FOREIGN_KEY_VIOLATION
