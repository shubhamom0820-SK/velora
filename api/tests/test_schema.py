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
T-1.12: money — a balance never below zero, an append-only ledger (UPDATE,
DELETE and TRUNCATE refused), payments never hard-deleted, and a paid payment
always carrying its idempotency anchor. With this, every constraint T-1.16 lists
is tested where it was built.
T-1.13: notifications and ops — an append-only audit log with a real actor, the
`like` preference stored as column `likes`, one subscription per push endpoint,
and a case-insensitive waitlist.
P-25: intent as a catalogue (D-041) — each intent picked once, picks reference a
real user and intent, catalogue rows need a unique slug and a label.
T-5.1: every CHECK test names the constraint that refused, never only 23514,
since the gender guard (D-076) refuses with that code too; the ledger's tests
are a man's, with refs. The ledger's new shape is tested in
tests/modules/wallet/test_guards.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.modules.notifications.models import NotificationPrefs
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


@dataclass(frozen=True)
class CheckRefusal:
    constraint: str | None
    message: str


async def _check_refused(
    db: AsyncSession, sql: str, params: dict[str, object] | None = None
) -> CheckRefusal:
    """Run `sql` in its own savepoint, expect a CHECK refusal (23514), and say
    which constraint refused it.

    The code alone proves nothing: from T-5.1 the gender guard refuses with
    23514 too, and a test asserting only the code passes whichever guard said
    no. Three of T-1.12's did, the day the guard arrived (P-48's lesson)."""
    with pytest.raises(IntegrityError) as excinfo:
        async with db.begin_nested():
            await db.execute(text(sql), params or {})
    return _check_refusal(excinfo.value)


def _check_refusal(error: IntegrityError) -> CheckRefusal:
    assert _sqlstate(error) == CHECK_VIOLATION, str(error.orig)
    return CheckRefusal(_constraint(error), str(error.orig))


def _constraint(error: IntegrityError) -> str | None:
    """The constraint that refused, from asyncpg's own exception, behind
    SQLAlchemy's."""
    cause = error.orig.__cause__ if error.orig is not None else None
    name = getattr(cause, "constraint_name", None)
    return name if isinstance(name, str) else None


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


@pytest.mark.critical  # 06-TESTING.md #8: gender immutable — DB trigger also blocks
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

    refusal = await _check_refused(
        db,
        f"update users set {column} = :v where id = :id",
        {"v": second, "id": user.id},
    )

    # check_violation -> IntegrityError, which T-3.6 maps to IMMUTABLE_FIELD.
    # T-1.9's trigger names no constraint, so its message says which (P-62).
    assert refusal.constraint is None
    assert f"users.{column} is immutable once set" in refusal.message


@pytest.mark.critical  # 06-TESTING.md #8
@pytest.mark.parametrize("column", ["gender", "dob"])
async def test_identity_cannot_be_cleared_once_set(
    db: AsyncSession, column: str
) -> None:
    user = await _user(db, gender=Gender.MALE, dob=date(2000, 1, 1))

    refusal = await _check_refused(
        db, f"update users set {column} = null where id = :id", {"id": user.id}
    )

    assert refusal.constraint is None
    assert f"users.{column} is immutable once set" in refusal.message


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

    refusal = await _check_refused(
        db,
        "insert into profiles (user_id, username) values (:id, :u)",
        {"id": user.id, "u": username},
    )

    assert refusal.constraint == "ck_profiles_username_format"


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
        # T-1.12 (ledger is append-only; credit_packs is catalogue seed data)
        "wallets",
        "action_prices",
        "payments",
        "refund_requests",
        # T-1.13 (audit_log is append-only; waitlist is written once;
        # notifications and push_subscriptions carry their own timestamps)
        "notification_prefs",
        "app_config",
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

    refusal = await _check_refused(
        db,
        "insert into photos (user_id, kind, position, raw_key) values (:u, 'public', 6, 'k')",
        {"u": user.id},
    )

    assert refusal.constraint == "ck_photos_public_position_range"


async def test_a_public_photo_must_have_a_position(db: AsyncSession) -> None:
    """P-13: NULL passed the old `position BETWEEN 0 AND 5` check (unknown)."""
    user = await _user(db)

    refusal = await _check_refused(
        db,
        "insert into photos (user_id, kind, position, raw_key) "
        "values (:u, 'public', null, 'k')",
        {"u": user.id},
    )

    assert refusal.constraint == "ck_photos_public_position_range"


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
            "insert into sessions (user_id, family_id, token_hash, expires_at, "
            "auth_time) values (:u, gen_random_uuid(), 'tok', "
            "now() + interval '1 day', now())"
        ),
        {"u": user.id},
    )

    await db.execute(text("delete from users where id = :u"), {"u": user.id})

    remaining = await db.scalar(
        text("select count(*) from sessions where user_id = :u"), {"u": user.id}
    )
    assert remaining == 0


async def test_a_session_without_its_sign_in_time_is_refused(db: AsyncSession) -> None:
    """Every access token carries `auth_time` from its session (D-071)."""
    user = await _user(db)

    state = await _rejected(
        db,
        "insert into sessions (user_id, family_id, token_hash, expires_at) "
        "values (:u, gen_random_uuid(), 'tok', now() + interval '1 day')",
        {"u": user.id},
    )

    assert state == NOT_NULL_VIOLATION


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

    reversed_order = await _check_refused(
        db, f"insert into {table} (user_low, user_high{extra}", {"a": high, "b": low}
    )
    equal = await _check_refused(
        db, f"insert into {table} (user_low, user_high{extra}", {"a": low, "b": low}
    )

    assert reversed_order.constraint == f"ck_{table}_pair_ordered"
    assert equal.constraint == f"ck_{table}_pair_ordered"


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


# The Knot promise, guarded from both sides (D-003).


async def test_a_knotted_thread_cannot_carry_an_expiry(db: AsyncSession) -> None:
    """Otherwise the expiry cron would kill a conversation both people were
    told is permanent."""
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)

    refusal = await _check_refused(
        db,
        "update threads set status = 'knotted', knotted_at = now() where id = :t",
        {"t": thread_id},
    )

    assert refusal.constraint == "ck_threads_knotted_is_permanent"


async def test_a_knotted_thread_needs_knotted_at(db: AsyncSession) -> None:
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)

    refusal = await _check_refused(
        db,
        "update threads set status = 'knotted', expires_at = null where id = :t",
        {"t": thread_id},
    )

    assert refusal.constraint == "ck_threads_knotted_is_permanent"


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

    refusal = await _check_refused(
        db,
        "insert into threads (user_low, user_high, origin, opened_by) "
        "values (:low, :high, 'match', :low)",
        {"low": low, "high": high},
    )

    assert refusal.constraint == "ck_threads_active_expires"


async def test_untying_back_to_active_needs_a_fresh_expiry(db: AsyncSession) -> None:
    """Untie (04-API: DELETE /threads/{id}/knot) returns a Knot to active."""
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)
    await db.execute(
        text(
            "update threads set status = 'knotted', knotted_at = now(), "
            "expires_at = null where id = :t"
        ),
        {"t": thread_id},
    )

    no_expiry = await _check_refused(
        db, "update threads set status = 'active' where id = :t", {"t": thread_id}
    )
    await db.execute(
        text(
            "update threads set status = 'active', "
            "expires_at = now() + interval '24 hours' where id = :t"
        ),
        {"t": thread_id},
    )

    assert no_expiry.constraint == "ck_threads_active_expires"


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

    refusal = await _check_refused(
        db,
        "insert into messages (thread_id, sender_id, kind, body, client_msg_id) "
        "values (:t, :s, 'text', :b, :c)",
        {"t": thread_id, "s": low, "b": "x" * 2001, "c": uuid.uuid4()},
    )

    assert refusal.constraint == "ck_messages_body_length"


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
        # A self-referral would farm credits on both sides of one account.
        ("referrals", "(referee_id, referrer_id) values (:u, :u)"),
    ],
)
async def test_nobody_can_act_on_themselves(
    db: AsyncSession, table: str, sql: str
) -> None:
    low, high = await _pair(db)
    thread_id = await _thread(db, low, high)
    gift_id = await _gift(db)

    refusal = await _check_refused(
        db, f"insert into {table} {sql}", {"u": low, "t": thread_id, "g": gift_id}
    )

    assert refusal.constraint == f"ck_{table}_not_self"


# Charges are never negative (T-1.11 Q4).


async def test_album_request_charge_is_never_negative(db: AsyncSession) -> None:
    low, high = await _pair(db)

    refusal = await _check_refused(
        db,
        "insert into album_requests (requester_id, owner_id, credits_charged) "
        "values (:r, :o, -1)",
        {"r": low, "o": high},
    )

    assert refusal.constraint == "ck_album_requests_credits_charged_non_negative"


async def test_gift_send_charge_is_never_negative(db: AsyncSession) -> None:
    low, high = await _pair(db)
    gift_id = await _gift(db)

    refusal = await _check_refused(
        db,
        "insert into gift_sends (sender_id, recipient_id, gift_id, credits_charged) "
        "values (:s, :r, :g, -2)",
        {"s": low, "r": high, "g": gift_id},
    )

    assert refusal.constraint == "ck_gift_sends_credits_charged_non_negative"


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
    refusal = await _check_refused(
        db,
        "insert into gifts (id, label, asset, credits) values ('bad', 'Bad', 'x', -1)",
    )

    assert refusal.constraint == "ck_gifts_credits_non_negative"


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

    refusal = await _check_refused(
        db,
        "insert into reports (reporter_id, reported_id, reason, details) "
        "values (:a, :b, 'scam', :d)",
        {"a": low, "b": high, "d": "x" * 501},
    )

    assert refusal.constraint == "ck_reports_details_length"


async def test_report_action_is_one_of_four(db: AsyncSession) -> None:
    low, high = await _pair(db)
    sql = (
        "insert into reports (reporter_id, reported_id, reason, action) "
        "values (:a, :b, 'scam', :act)"
    )

    for action in ("freeze", "ban", "warn", "none"):
        async with db.begin_nested():
            await db.execute(text(sql), {"a": low, "b": high, "act": action})
    refusal = await _check_refused(db, sql, {"a": low, "b": high, "act": "delete"})

    assert refusal.constraint == "ck_reports_action_values"


# Fraud (D-031): the score is 0-100; bands are policy, not a CHECK.


@pytest.mark.parametrize("score", [-1, 101])
async def test_fraud_score_is_0_to_100(db: AsyncSession, score: int) -> None:
    user = await _user(db)

    refusal = await _check_refused(
        db,
        "insert into fraud_scores (user_id, score) values (:u, :s)",
        {"u": user.id, "s": score},
    )

    assert refusal.constraint == "ck_fraud_scores_score_range"


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


# --- T-1.12 -------------------------------------------------------------------

RESTRICT_VIOLATION = "23001"


async def _man(db: AsyncSession) -> User:
    """From T-5.1 only a man may hold credits (D-076), so every ledger row and
    non-zero balance here is a man's: the test then fails on its own guard."""
    return await _user(db, gender=Gender.MALE)


async def _ledger_entry(
    db: AsyncSession, user_id: uuid.UUID, **fields: object
) -> uuid.UUID:
    """A purchase as D-077 shapes one: a credit, naming its payment. The
    payment needn't exist: `ref_id` is polymorphic, so it has no foreign key."""
    values: dict[str, object] = {
        "u": user_id,
        "delta": 5,
        "after": 5,
        "ref": uuid.uuid4(),
        "key": f"test-{uuid.uuid4()}",
    }
    values.update(fields)
    entry_id = await db.scalar(
        text(
            "insert into ledger_entries (user_id, delta, balance_after, reason, "
            "ref_type, ref_id, idempotency_key) "
            "values (:u, :delta, :after, 'purchase', 'payment', :ref, :key) "
            "returning id"
        ),
        values,
    )
    assert isinstance(entry_id, uuid.UUID)
    return entry_id


async def _pack(db: AsyncSession, pack_id: str = "test-pack") -> str:
    await db.execute(
        text(
            "insert into credit_packs (id, credits, price_paise) "
            "values (:id, 25, 150000)"
        ),
        {"id": pack_id},
    )
    return pack_id


async def _payment(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    pack_id = await _pack(db, f"pack-{uuid.uuid4().hex[:8]}")
    payment_id = await db.scalar(
        text(
            "insert into payments (user_id, pack_id, amount_paise, credits, "
            "provider_order_id, idempotency_key) "
            "values (:u, :p, 150000, 25, :o, :k) returning id"
        ),
        {
            "u": user_id,
            "p": pack_id,
            "o": f"order_{uuid.uuid4().hex}",
            "k": str(uuid.uuid4()),
        },
    )
    assert isinstance(payment_id, uuid.UUID)
    return payment_id


# Wallets: the balance never goes below zero (T-1.16's item, covered here).


async def test_wallet_balance_cannot_go_negative(db: AsyncSession) -> None:
    user = await _man(db)
    await db.execute(text("insert into wallets (user_id) values (:u)"), {"u": user.id})

    refusal = await _check_refused(
        db, "update wallets set balance = -1 where user_id = :u", {"u": user.id}
    )

    assert refusal.constraint == "ck_wallets_balance_non_negative"


# Ledger: append-only, enforced (T-1.16's item, covered here).


async def test_ledger_accepts_inserts(db: AsyncSession) -> None:
    """Append-only is not read-only."""
    user = await _man(db)

    await _ledger_entry(db, user.id)


@pytest.mark.parametrize(
    "statement",
    [
        "update ledger_entries set delta = 500 where id = :id",
        "update ledger_entries set reason = 'refund' where id = :id",
        "delete from ledger_entries where id = :id",
    ],
)
async def test_ledger_rows_cannot_change_or_disappear(
    db: AsyncSession, statement: str
) -> None:
    user = await _man(db)
    entry_id = await _ledger_entry(db, user.id)

    state = await _rejected(db, statement, {"id": entry_id})

    assert state == RESTRICT_VIOLATION


async def test_ledger_cannot_be_truncated(db: AsyncSession) -> None:
    """TRUNCATE skips row triggers; the statement-level guard catches it."""
    user = await _man(db)
    await _ledger_entry(db, user.id)

    state = await _rejected(db, "truncate ledger_entries")

    assert state == RESTRICT_VIOLATION


@pytest.mark.parametrize(
    ("fields", "refused_by"),
    [
        # A zero delta records nothing. It breaks D-077's direction too, which
        # needs a sign, so either refusal is the right reason.
        (
            {"delta": 0, "after": 0},
            {"ck_ledger_entries_delta_non_zero", "ck_ledger_entries_reason_direction"},
        ),
        ({"delta": 5, "after": -5}, {"ck_ledger_entries_balance_after_non_negative"}),
    ],
    ids=["zero delta", "negative balance_after"],
)
async def test_ledger_entry_values(
    db: AsyncSession, fields: dict[str, object], refused_by: set[str]
) -> None:
    user = await _man(db)

    with pytest.raises(IntegrityError) as excinfo:
        async with db.begin_nested():
            await _ledger_entry(db, user.id, **fields)

    assert _check_refusal(excinfo.value).constraint in refused_by


@pytest.mark.parametrize(
    "half",
    [
        "ref_type) values (:u, 5, 5, 'admin_grant', 'k1', 'audit_log')",
        "ref_id) values (:u, 5, 5, 'admin_grant', 'k1', gen_random_uuid())",
    ],
    ids=["type without id", "id without type"],
)
async def test_ledger_reference_is_complete_or_absent(
    db: AsyncSession, half: str
) -> None:
    """On `admin_grant`, the one reason whose ref is optional (D-077), so the
    half-written ref is the only thing wrong."""
    user = await _man(db)

    refusal = await _check_refused(
        db,
        "insert into ledger_entries (user_id, delta, balance_after, reason, "
        f"idempotency_key, {half}",
        {"u": user.id},
    )

    assert refusal.constraint == "ck_ledger_entries_ref_complete"


async def test_idempotency_key_applies_once(db: AsyncSession) -> None:
    """Two payments, one key: only the key is shared, so only its constraint
    can refuse (D-077's per-event index would refuse one payment twice)."""
    user = await _man(db)
    await _ledger_entry(db, user.id, key="same-key")

    with pytest.raises(IntegrityError) as excinfo:
        async with db.begin_nested():
            await _ledger_entry(db, user.id, key="same-key")

    assert _sqlstate(excinfo.value) == UNIQUE_VIOLATION
    assert _constraint(excinfo.value) == "uq_ledger_entries_idempotency_key"


# Payments: never hard-deleted (rule 12), anchored once paid (D-026).


async def test_a_payment_cannot_be_deleted(db: AsyncSession) -> None:
    user = await _user(db)
    payment_id = await _payment(db, user.id)

    state = await _rejected(db, "delete from payments where id = :p", {"p": payment_id})

    assert state == RESTRICT_VIOLATION


async def test_payments_cannot_be_truncated(db: AsyncSession) -> None:
    """Plain TRUNCATE is already refused by the refund_requests foreign key, before
    the trigger runs. CASCADE passes that check — the guard must catch it."""
    user = await _user(db)
    await _payment(db, user.id)

    state = await _rejected(db, "truncate payments cascade")

    assert state == RESTRICT_VIOLATION


async def test_a_payment_status_can_be_updated(db: AsyncSession) -> None:
    user = await _user(db)
    payment_id = await _payment(db, user.id)

    await db.execute(
        text(
            "update payments set status = 'paid', provider_payment_id = 'pay_1', "
            "paid_at = now() where id = :p"
        ),
        {"p": payment_id},
    )


@pytest.mark.parametrize("status", ["paid", "refunded"])
async def test_money_moved_means_an_anchor_exists(
    db: AsyncSession, status: str
) -> None:
    """A paid row without provider_payment_id would break webhook idempotency."""
    user = await _user(db)
    payment_id = await _payment(db, user.id)

    no_anchor = await _check_refused(
        db,
        f"update payments set status = '{status}', paid_at = now() where id = :p",
        {"p": payment_id},
    )
    no_paid_at = await _check_refused(
        db,
        f"update payments set status = '{status}', provider_payment_id = 'pay_x' "
        "where id = :p",
        {"p": payment_id},
    )

    assert no_anchor.constraint == "ck_payments_paid_has_anchor"
    assert no_paid_at.constraint == "ck_payments_paid_has_anchor"


@pytest.mark.parametrize("column", ["provider_order_id", "provider_payment_id"])
async def test_provider_ids_are_unique(db: AsyncSession, column: str) -> None:
    user = await _user(db)
    first, second = await _payment(db, user.id), await _payment(db, user.id)
    await db.execute(
        text(f"update payments set {column} = 'dup' where id = :p"), {"p": first}
    )

    state = await _rejected(
        db, f"update payments set {column} = 'dup' where id = :p", {"p": second}
    )

    assert state == UNIQUE_VIOLATION


@pytest.mark.parametrize(
    ("assignment", "constraint"),
    [
        ("amount_paise = 0", "ck_payments_amount_positive"),
        ("credits = 0", "ck_payments_credits_positive"),
        ("bonus_credits = -1", "ck_payments_bonus_non_negative"),
    ],
)
async def test_payment_amounts_are_sane(
    db: AsyncSession, assignment: str, constraint: str
) -> None:
    user = await _user(db)
    payment_id = await _payment(db, user.id)

    refusal = await _check_refused(
        db, f"update payments set {assignment} where id = :p", {"p": payment_id}
    )

    assert refusal.constraint == constraint


# Catalogues: invariants, not policy.


@pytest.mark.parametrize(
    ("values", "constraint"),
    [
        ("('p0', 0, 150000, 20)", "ck_credit_packs_credits_positive"),
        ("('p1', 25, 0, 20)", "ck_credit_packs_price_positive"),
        ("('p2', 25, 150000, 101)", "ck_credit_packs_bonus_first_pct_range"),
        ("('p3', 25, 150000, -1)", "ck_credit_packs_bonus_first_pct_range"),
    ],
)
async def test_credit_pack_invariants(
    db: AsyncSession, values: str, constraint: str
) -> None:
    refusal = await _check_refused(
        db,
        f"insert into credit_packs (id, credits, price_paise, bonus_first_pct) values {values}",
    )

    assert refusal.constraint == constraint


async def test_credit_pack_defaults(db: AsyncSession) -> None:
    await _pack(db, "defaults")

    row = (
        await db.execute(
            text(
                "select bonus_first_pct, active, sort, variant "
                "from credit_packs where id = 'defaults'"
            )
        )
    ).one()

    assert tuple(row) == (20, True, 0, "A")


async def test_action_price_never_negative(db: AsyncSession) -> None:
    refusal = await _check_refused(
        db, "insert into action_prices (action, credits) values ('thread_open', -5)"
    )

    assert refusal.constraint == "ck_action_prices_credits_non_negative"


# Foreign keys on the shorthand tables (the T-1.10 ruling, applied again).


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("wallets", "(user_id) values (:x)"),
        ("refund_requests", "(user_id, payment_id) values (:u, :x)"),
        ("referrals", "(referee_id, referrer_id) values (:u, :x)"),
    ],
)
async def test_money_references_are_real(
    db: AsyncSession, table: str, columns: str
) -> None:
    user = await _user(db)

    state = await _rejected(
        db, f"insert into {table} {columns}", {"u": user.id, "x": uuid.uuid4()}
    )

    assert state == FOREIGN_KEY_VIOLATION


async def test_refund_request_starts_open(db: AsyncSession) -> None:
    user = await _user(db)
    payment_id = await _payment(db, user.id)

    status = await db.scalar(
        text(
            "insert into refund_requests (user_id, payment_id) values (:u, :p) "
            "returning status"
        ),
        {"u": user.id, "p": payment_id},
    )

    assert status == "open"


# --- T-1.13 -------------------------------------------------------------------

NOT_NULL_VIOLATION = "23502"


# Notifications.


async def test_a_push_endpoint_belongs_to_one_subscription(db: AsyncSession) -> None:
    """Unique across accounts: one browser endpoint is one subscription."""
    first, second = await _user(db), await _user(db)
    insert = (
        "insert into push_subscriptions (user_id, endpoint, p256dh, auth) "
        "values (:u, 'https://push.example/abc', 'key', 'secret')"
    )
    await db.execute(text(insert), {"u": first.id})

    state = await _rejected(db, insert, {"u": second.id})

    assert state == UNIQUE_VIOLATION


async def test_notification_prefs_default_on_except_generic_text(
    db: AsyncSession,
) -> None:
    user = await _user(db)

    row = (
        await db.execute(
            text(
                "insert into notification_prefs (user_id) values (:u) returning "
                "match, message, likes, knot, expiry, balance, generic_text"
            ),
            {"u": user.id},
        )
    ).one()

    assert tuple(row) == (True, True, True, True, True, True, False)


async def test_the_like_preference_round_trips(db: AsyncSession) -> None:
    """The attribute is `like`, the column `likes` (a reserved word): a value
    written through either name reads back through the other."""
    user = await _user(db)
    prefs = NotificationPrefs(user_id=user.id, like=False)
    db.add(prefs)
    await db.flush()

    stored = await db.scalar(
        text("select likes from notification_prefs where user_id = :u"),
        {"u": user.id},
    )
    await db.execute(
        text("update notification_prefs set likes = true where user_id = :u"),
        {"u": user.id},
    )
    await db.refresh(prefs)
    selected = await db.scalar(
        select(NotificationPrefs.like).where(NotificationPrefs.user_id == user.id)
    )

    assert stored is False
    assert prefs.like is True
    assert selected is True


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        (
            "push_subscriptions",
            "(user_id, endpoint, p256dh, auth) values (:x, 'https://push.example/x', 'k', 's')",
        ),
        ("notification_prefs", "(user_id) values (:x)"),
        ("notifications", "(user_id, kind) values (:x, 'match')"),
    ],
)
async def test_notification_references_are_real(
    db: AsyncSession, table: str, columns: str
) -> None:
    state = await _rejected(db, f"insert into {table} {columns}", {"x": uuid.uuid4()})

    assert state == FOREIGN_KEY_VIOLATION


# Audit log: append-only, enforced — the trace outlives whoever wants it gone.


async def _audit_entry(db: AsyncSession, actor_id: uuid.UUID) -> uuid.UUID:
    entry_id = await db.scalar(
        text(
            "insert into audit_log (actor_id, action, target_type, target_id) "
            "values (:a, 'user.freeze', 'user', :t) returning id"
        ),
        {"a": actor_id, "t": uuid.uuid4()},
    )
    assert isinstance(entry_id, uuid.UUID)
    return entry_id


async def test_audit_log_accepts_inserts(db: AsyncSession) -> None:
    """Append-only is not read-only; an action with no target is allowed."""
    user = await _user(db)

    await _audit_entry(db, user.id)
    await db.execute(
        text("insert into audit_log (actor_id, action) values (:a, 'config.update')"),
        {"a": user.id},
    )


@pytest.mark.parametrize(
    "statement",
    [
        "update audit_log set action = 'nothing.happened' where id = :id",
        "update audit_log set meta = '{}' where id = :id",
        "delete from audit_log where id = :id",
    ],
)
async def test_audit_entries_cannot_change_or_disappear(
    db: AsyncSession, statement: str
) -> None:
    user = await _user(db)
    entry_id = await _audit_entry(db, user.id)

    state = await _rejected(db, statement, {"id": entry_id})

    assert state == RESTRICT_VIOLATION


async def test_audit_log_cannot_be_truncated(db: AsyncSession) -> None:
    """TRUNCATE skips row triggers; the statement-level guard catches it."""
    user = await _user(db)
    await _audit_entry(db, user.id)

    state = await _rejected(db, "truncate audit_log")

    assert state == RESTRICT_VIOLATION


@pytest.mark.parametrize("target", ["'user', null", "null, gen_random_uuid()"])
async def test_audit_target_is_complete_or_absent(
    db: AsyncSession, target: str
) -> None:
    user = await _user(db)

    refusal = await _check_refused(
        db,
        "insert into audit_log (actor_id, action, target_type, target_id) "
        f"values (:a, 'user.freeze', {target})",
        {"a": user.id},
    )

    assert refusal.constraint == "ck_audit_log_target_complete"


async def test_every_audit_entry_has_a_real_actor(db: AsyncSession) -> None:
    """NULL could not tell "the system did it" from "a bug forgot to set it"."""
    missing = await _rejected(
        db, "insert into audit_log (action) values ('user.freeze')"
    )
    unknown = await _rejected(
        db,
        "insert into audit_log (actor_id, action) values (:a, 'user.freeze')",
        {"a": uuid.uuid4()},
    )

    assert missing == NOT_NULL_VIOLATION
    assert unknown == FOREIGN_KEY_VIOLATION


# app_config and waitlist.


async def test_app_config_needs_a_value(db: AsyncSession) -> None:
    state = await _rejected(db, "insert into app_config (key) values ('test-key')")

    assert state == NOT_NULL_VIOLATION


async def test_waitlist_email_is_unique_ignoring_case(db: AsyncSession) -> None:
    await db.execute(text("insert into waitlist (email) values ('Priya@Example.com')"))

    state = await _rejected(
        db, "insert into waitlist (email) values ('priya@example.COM')"
    )

    assert state == UNIQUE_VIOLATION


# --- P-25 ---------------------------------------------------------------------

# Intent is a 1-3 pick from a catalogue (D-041); the count is the service's job.


async def _intent(db: AsyncSession, intent_id: int = 900, slug: str = "test") -> int:
    await db.execute(
        text("insert into intents (id, slug, label) values (:i, :s, 'Test')"),
        {"i": intent_id, "s": slug},
    )
    return intent_id


async def test_an_intent_is_picked_once(db: AsyncSession) -> None:
    user = await _user(db)
    intent_id = await _intent(db)
    insert = "insert into profile_intents (user_id, intent_id) values (:u, :i)"
    await db.execute(text(insert), {"u": user.id, "i": intent_id})

    state = await _rejected(db, insert, {"u": user.id, "i": intent_id})

    assert state == UNIQUE_VIOLATION


async def test_picks_reference_a_real_user_and_intent(db: AsyncSession) -> None:
    user = await _user(db)
    intent_id = await _intent(db)
    insert = "insert into profile_intents (user_id, intent_id) values (:u, :i)"

    no_intent = await _rejected(db, insert, {"u": user.id, "i": 901})
    no_user = await _rejected(db, insert, {"u": uuid.uuid4(), "i": intent_id})

    assert no_intent == FOREIGN_KEY_VIOLATION
    assert no_user == FOREIGN_KEY_VIOLATION


async def test_an_intent_needs_a_slug_and_a_label(db: AsyncSession) -> None:
    """NOT NULL from the start — the gap P-24 fixes on interests and areas."""
    no_slug = await _rejected(db, "insert into intents (id, label) values (901, 'X')")
    no_label = await _rejected(db, "insert into intents (id, slug) values (902, 'x')")

    assert no_slug == NOT_NULL_VIOLATION
    assert no_label == NOT_NULL_VIOLATION


async def test_intent_slugs_are_unique(db: AsyncSession) -> None:
    await _intent(db, 900, "dup")

    state = await _rejected(
        db, "insert into intents (id, slug, label) values (901, 'dup', 'Dup')"
    )

    assert state == UNIQUE_VIOLATION
