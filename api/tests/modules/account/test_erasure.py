"""Erasing a deleted account (T-9.6, D-500, D-503): exactly what D-051 erases,
exactly what it keeps, and the database's own guards on the anonymised row."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.clock import IST
from app.core.enums import Gender, UserStatus
from app.core.providers.storage import FakeStorage
from app.modules.account import erasure
from app.modules.account import service as account_service
from app.modules.users.models import User
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.onboarding.test_guard import _alembic
from tests.modules.photos.test_moderate import Sessions

SETTINGS = make_test_settings()
PRIVATE, PUBLIC = SETTINGS.R2_BUCKET_PRIVATE, SETTINGS.R2_BUCKET_PUBLIC
NOW = datetime(2026, 10, 8, 6, 30, tzinfo=IST)
DAY = timedelta(days=1)


# --- The two lists, held to the database -------------------------------------------


async def _keyed_columns(db: AsyncSession) -> dict[tuple[str, str], str]:
    """Every (table, column) holding a key to `users`, with its ON DELETE rule."""
    rows = await db.execute(
        text(
            """
            select c.conrelid::regclass::text, a.attname, c.confdeltype::text
            from pg_constraint c
            join pg_attribute a
              on a.attrelid = c.conrelid and a.attnum = any(c.conkey)
            where c.contype = 'f' and c.confrelid = 'users'::regclass
            """
        )
    )
    return {(str(t), str(c)): str(rule) for t, c, rule in rows}


def _erased() -> set[tuple[str, str]]:
    return {(e.model.__tablename__, c) for e in erasure.ERASED for c in e.columns}


async def _problems(db: AsyncSession) -> list[str]:
    keyed = await _keyed_columns(db)
    erased, kept = _erased(), set(erasure.KEPT)
    problems = []
    if unclassified := sorted(set(keyed) - erased - kept):
        problems.append(
            f"D-503: {unclassified} hold a key to users. Add each to ERASED (the "
            "erasure deletes its rows) or KEPT (with why), in "
            "api/app/modules/account/erasure.py."
        )
    if both := sorted(erased & kept):
        problems.append(f"D-503: {both} are both erased and kept")
    if stale := sorted((erased | kept) - set(keyed)):
        problems.append(f"D-503: {stale} are listed but hold no key to users")
    if loose := sorted(k for k in kept if keyed.get(k) not in {"r", "a", None}):
        problems.append(f"D-503: kept {loose} must be RESTRICT (rule 12)")
    tables = set(await db.scalars(text("select tablename from pg_tables")))
    if built := sorted(set(erasure.KEPT_WHEN_BUILT) & tables):
        problems.append(
            f"D-503: {built} exist now: move each from KEPT_WHEN_BUILT to KEPT, "
            "by its columns keyed to users (or say why it has none)"
        )
    return problems


async def test_every_column_keyed_to_users_is_erased_or_kept(db: AsyncSession) -> None:
    """Every column naming a user is in exactly one list, so a table added
    later fails here, naming D-503, until someone decides what an erasure does
    to its rows."""
    assert await _problems(db) == []


async def test_a_new_table_keyed_to_users_fails_until_it_is_listed(
    db: AsyncSession,
) -> None:
    await db.execute(
        text("create table d503_probe (user_id uuid not null references users (id))")
    )

    problems = await _problems(db)

    assert len(problems) == 1
    assert problems[0].startswith("D-503: [('d503_probe', 'user_id')] hold a key")


async def test_the_welcome_hash_is_kept(db: AsyncSession) -> None:
    """P-371, D-470: T-8.11's hash of every number that received welcome Velas
    survives the erasure, so a later account on the number gets none. Named in
    KEPT before it existed (T-9.6), and moved there when T-8.11 built it."""
    assert erasure.KEPT_WHEN_BUILT == {}
    assert ("welcome_grants", "user_id") in erasure.KEPT
    erased_tables = {e.model.__tablename__ for e in erasure.ERASED}
    assert "welcome_grants" not in erased_tables
    assert "banned_identities" not in erased_tables
    assert await _problems(db) == []


async def test_a_table_built_while_named_for_later_must_move_to_kept(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check T-9.6 left for planned tables still fires for the next one."""
    monkeypatch.setattr(erasure, "KEPT_WHEN_BUILT", {"d503_later": "a probe"})
    await db.execute(text("create table d503_later (id int primary key)"))

    assert await _problems(db) == [
        (
            "D-503: ['d503_later'] exist now: move each from KEPT_WHEN_BUILT to "
            "KEPT, by its columns keyed to users (or say why it has none)"
        )
    ]


async def test_rule_12s_tables_are_kept(db: AsyncSession) -> None:
    """Whatever else changes, the erasure never reaches what rule 12 keeps,
    nor anything the app role can't delete from (T-1.22)."""
    erased_tables = {e.model.__tablename__ for e in erasure.ERASED}
    rows = await db.execute(
        text(
            "select t, has_table_privilege('velora_app', t, 'DELETE') "
            "from unnest(cast(:tables as text[])) as t"
        ),
        {"tables": sorted(erased_tables)},
    )
    assert all(can for _, can in rows)
    assert not erased_tables & {
        "messages",
        "ledger_entries",
        "payments",
        "reports",
        "audit_log",
        "wallets",
        "threads",
        "fraud_events",
        "fraud_scores",
        "banned_identities",
    }


def test_every_storage_key_on_an_erased_table_is_in_the_file_list() -> None:
    listed = {(model.__tablename__, column) for model, column, _ in erasure.FILES}
    on_erased = {
        (e.model.__tablename__, column.name)
        for e in erasure.ERASED
        for column in e.model.__table__.columns
        if column.name.endswith("_key")
    }

    assert (
        listed
        == on_erased
        == {
            ("photos", "raw_key"),
            ("photos", "public_key"),
            ("data_exports", "file_key"),
        }
    )


# --- The erasure, end to end ----------------------------------------------------------


async def _everywhere(
    db: AsyncSession, storage: FakeStorage, me: uuid.UUID, other: uuid.UUID
) -> None:
    """A row in every table naming `me` in every column that can, kept or
    erased, and files behind each erased row that has one."""
    low, high = sorted((me, other))
    v: dict[str, Any] = {"m": me, "o": other, "low": low, "high": high}
    v["t"] = await db.scalar(
        text(
            "insert into threads (user_low, user_high, origin, opened_by, expires_at) "
            "values (:low, :high, 'match', :m, now() + interval '1 day') returning id"
        ),
        v,
    )
    for sender in ("m", "o"):
        v[f"msg_{sender}"] = await db.scalar(
            text(
                "insert into messages (thread_id, sender_id, kind, body, client_msg_id) "
                "values (:t, :s, 'text', 'hello', gen_random_uuid()) returning id"
            ),
            {**v, "s": v[sender]},
        )
    raw, public = f"raw/{me}/a", f"p/{me}.jpg"
    v["photo"] = await db.scalar(
        text(
            "insert into photos (user_id, kind, position, raw_key, public_key, status) "
            "values (:m, 'public', 0, :raw, :pub, 'approved') returning id"
        ),
        {**v, "raw": raw, "pub": public},
    )
    export = f"exports/{me}/b.json"
    statements = [
        "insert into message_unlocks (user_id, message_id) values (:m, :msg_o)",
        (
            "insert into verifications (user_id, challenge, selfie_photo_id) "
            "values (:m, 'none', :photo)"
        ),
        (
            "insert into data_exports (user_id, status, file_key, ready_at, expires_at) "
            "values (:m, 'ready', :export, now(), now() + interval '1 day')"
        ),
        "insert into thread_clears (user_id, thread_id, cleared_at) values (:m, :t, now())",
        "insert into thread_clears (user_id, thread_id, cleared_at) values (:o, :t, now())",
        "insert into matches (user_low, user_high, thread_id) values (:low, :high, :t)",
        "insert into notifications (user_id, kind) values (:m, 'probe')",
        (
            "insert into push_subscriptions (user_id, endpoint, p256dh, auth) "
            "values (:m, 'https://push.invalid/probe', 'p', 'a')"
        ),
        "insert into fraud_events (user_id, signal, weight) values (:m, 'probe', 1)",
        "insert into fraud_scores (user_id) values (:m)",
        "insert into profile_intents (user_id, intent_id) values (:m, 1)",
        "insert into profile_interests (user_id, interest_id) values (:m, 1)",
        (
            "insert into sessions (user_id, family_id, token_hash, expires_at, "
            "auth_time) values (:m, gen_random_uuid(), 'probe', now(), now())"
        ),
        "insert into audit_log (actor_id, action) values (:m, 'probe')",
        (
            "insert into reports (reporter_id, reported_id, reason, resolved_by) "
            "values (:m, :o, 'other', :m)"
        ),
        "insert into reports (reporter_id, reported_id, reason) values (:o, :m, 'other')",
        (
            "insert into payments (id, user_id, pack_id, amount_paise, credits, "
            "provider_order_id, idempotency_key) "
            "values (:pay, :m, 'pack-30', 150000, 30, :order, :order)"
        ),
        (
            "insert into refund_requests (user_id, payment_id, reason) "
            "values (:m, :pay, 'missing_velas')"
        ),
        (
            "insert into welcome_grants (phone_hash, user_id) "
            "select phone_hash, id from users where id = :m"
        ),
    ]
    v.update(export=export, pay=uuid.uuid4(), order=f"order_{uuid.uuid4().hex}")
    for statement in statements:
        await db.execute(text(statement), v)
    both_ways = [
        (
            "insert into kudos (from_id, to_id, kind, thread_id) "
            "values (:a, :b, 'great_conversation', :t)"
        ),
        "insert into gift_sends (sender_id, recipient_id, gift_id) values (:a, :b, 'coffee')",
        "insert into liked_you_reveals (viewer_id, liker_id) values (:a, :b)",
        "insert into swipes (swiper_id, target_id, dir) values (:a, :b, 'like')",
        (
            "insert into profile_views (viewer_id, viewed_id, last_viewed_at) "
            "values (:a, :b, now())"
        ),
        "insert into blocks (blocker_id, blocked_id) values (:a, :b)",
        "insert into album_requests (requester_id, owner_id) values (:a, :b)",
        "insert into referrals (referee_id, referrer_id) values (:a, :b)",
    ]
    for statement in both_ways:
        for a, b in ((me, other), (other, me)):
            await db.execute(text(statement), {**v, "a": a, "b": b})
    for bucket, key in ((PRIVATE, raw), (PUBLIC, public), (PRIVATE, export)):
        await storage.put_bytes(bucket, key, b"data", "application/octet-stream")
    await db.flush()


async def _by_column(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[tuple[str, str], int]:
    counts = {}
    for table, column in sorted(await _keyed_columns(db)):
        found = await db.scalar(
            text(f"select count(*) from {table} where {column} = :u"), {"u": user_id}
        )
        counts[(table, column)] = int(found or 0)
    return counts


async def _deleted_days_ago(db: AsyncSession, user: User, days: float) -> None:
    user.status = UserStatus.DELETED
    user.deleted_requested_at = NOW - timedelta(days=days)
    await db.flush()


async def _erase(db: AsyncSession, storage: FakeStorage) -> int:
    return await account_service.erase_due_accounts(
        Sessions(db),  # type: ignore[arg-type]
        storage=storage,
        settings=SETTINGS,
    )


@pytest.mark.critical
async def test_an_account_deleted_29_days_ago_is_erased_and_kept_exactly_as_d051_says(
    db: AsyncSession,
    make_user: MakeUser,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    clock.freeze(NOW)
    storage = FakeStorage()
    me, _ = await make_user(credits=7)
    other, _ = await make_user(Gender.FEMALE)
    await storage.put_bytes(PRIVATE, f"raw/{other.id}/theirs", b"x", "image/jpeg")
    await _everywhere(db, storage, me.id, other.id)
    me.pin_hash = "a-pin-hash"
    phone_hash, gender, code = me.phone_hash, me.gender, me.referral_code
    before = await _by_column(db, me.id)
    others_before = await _by_column(db, other.id)
    # Every column was filled, so "erased" and "kept" below mean something; of
    # a pair's `user_low` and `user_high`, the one the ids' order gives.
    pair = {"user_low": "user_high", "user_high": "user_low"}
    empty = [
        (t, c)
        for (t, c), n in before.items()
        if not n and not before[(t, pair.get(c, c))]
    ]
    assert empty == []
    await _deleted_days_ago(db, me, 29)

    assert await _erase(db, storage) == 1

    after = await _by_column(db, me.id)
    # Everything not kept is gone: read from the database's keys, never from
    # ERASED itself, so a table dropped from that list fails here too.
    assert {k: n for k, n in after.items() if k not in erasure.KEPT} == {
        k: 0 for k in after if k not in erasure.KEPT
    }
    assert {k: n for k, n in after.items() if k in erasure.KEPT} == {
        k: n for k, n in before.items() if k in erasure.KEPT
    }
    # The other person loses only rows that named the erased one too.
    others_after = await _by_column(db, other.id)
    assert others_after[("thread_clears", "user_id")] == 1
    assert others_after[("messages", "sender_id")] == 1
    assert others_after[("blocks", "blocker_id")] == 1
    assert others_after[("kudos", "from_id")] == 0  # their kudos to me: on my profile
    assert others_after[("kudos", "to_id")] == others_before[("kudos", "to_id")]
    # Files: every one behind an erased row gone, read back; anyone else's kept.
    assert set(storage.objects) == {(PRIVATE, f"raw/{other.id}/theirs")}
    await db.refresh(me)
    assert me.anonymised_at == NOW
    assert me.status is UserStatus.DELETED
    assert me.phone_enc is None and me.dob is None
    assert me.pin_hash is None and me.last_active_at is None
    assert me.referral_code != code
    assert (me.phone_hash, me.gender) == (phone_hash, gender)
    balance = await db.scalar(
        text("select balance from wallets where user_id = :u"), {"u": me.id}
    )
    assert balance == 7  # lost, not refunded (D-504), and still the ledger's sum
    assert str(me.id) in captured_logs.text
    assert phone_hash not in captured_logs.text
    captured_logs.assert_listening()


async def test_not_yet_29_days_is_left_alone(
    db: AsyncSession, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOW)
    me, _ = await make_user()
    await _deleted_days_ago(db, me, 29 - 1 / 24 / 60)

    assert await _erase(db, FakeStorage()) == 0

    await db.refresh(me)
    assert me.anonymised_at is None and me.phone_enc is not None


@pytest.mark.parametrize("status", [UserStatus.ACTIVE, UserStatus.PAUSED])
async def test_a_restored_account_is_never_erased(
    db: AsyncSession, make_user: MakeUser, clock: ModuleType, status: UserStatus
) -> None:
    """Restored by a sign-in, its status is no longer `deleted`: whatever its
    old request says, it isn't due."""
    clock.freeze(NOW)
    me, _ = await make_user()
    await _deleted_days_ago(db, me, 40)
    me.status = status
    await db.flush()

    assert await _erase(db, FakeStorage()) == 0

    await db.refresh(me)
    assert me.anonymised_at is None


async def test_a_file_that_wont_go_stops_that_account_and_the_next_run_finishes(
    db: AsyncSession,
    make_user: MakeUser,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    clock.freeze(NOW)
    storage = FakeStorage()
    me, _ = await make_user()
    stuck, fine = await make_user(), await make_user()
    for user in (me, stuck[0], fine[0]):
        await _deleted_days_ago(db, user, 29)
    await db.execute(
        text("insert into photos (user_id, kind, raw_key) values (:u, 'private', :k)"),
        {"u": stuck[0].id, "k": f"raw/{stuck[0].id}/a"},
    )
    await storage.put_bytes(PRIVATE, f"raw/{stuck[0].id}/a", b"x", "image/jpeg")
    real_delete = storage.delete

    async def refuse(bucket: str, key: str) -> None:
        if key.startswith(f"raw/{stuck[0].id}"):
            raise OSError("storage is down")
        await real_delete(bucket, key)

    storage.delete = refuse  # type: ignore[method-assign]

    assert await _erase(db, storage) == 2

    await db.refresh(stuck[0])
    assert stuck[0].anonymised_at is None and stuck[0].phone_enc is not None
    photos = await db.scalar(
        text("select count(*) from photos where user_id = :u"), {"u": stuck[0].id}
    )
    assert photos == 1
    assert "account.erase_failed" in captured_logs.text
    captured_logs.assert_listening()

    storage.delete = real_delete  # type: ignore[method-assign]
    assert await _erase(db, storage) == 1
    await db.refresh(stuck[0])
    assert stuck[0].anonymised_at is not None
    assert storage.objects == {}


async def test_erasing_twice_is_once(
    db: AsyncSession, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOW)
    me, _ = await make_user()
    await _deleted_days_ago(db, me, 30)

    assert await _erase(db, FakeStorage()) == 1
    assert await _erase(db, FakeStorage()) == 0


# --- The database's own guards (D-500, D-501) -------------------------------------------


async def _update(db: AsyncSession, user_id: uuid.UUID, assignments: str) -> None:
    async with db.begin_nested():
        await db.execute(
            text(f"update users set {assignments} where id = :u"), {"u": user_id}
        )


async def _deleted(db: AsyncSession, make_user: MakeUser) -> User:
    user, _ = await make_user()
    await _update(db, user.id, "status = 'deleted', deleted_requested_at = now()")
    return user


async def test_dob_can_be_cleared_only_by_the_anonymising_update(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user = await _deleted(db, make_user)

    with pytest.raises(IntegrityError, match="users.dob is immutable once set"):
        await _update(db, user.id, "dob = null")
    with pytest.raises(IntegrityError, match="users.dob is immutable once set"):
        await _update(
            db, user.id, "dob = '1990-01-01', anonymised_at = now(), phone_enc = null"
        )

    await _update(db, user.id, "dob = null, anonymised_at = now(), phone_enc = null")


async def test_an_anonymised_row_can_never_take_a_dob_or_come_back(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """The loophole the dob exception could open: anonymise, then set a new
    date, or step back out of `deleted`. Each is refused."""
    user = await _deleted(db, make_user)
    await _update(db, user.id, "dob = null, anonymised_at = now(), phone_enc = null")

    refused = [
        ("anonymised_at = null", "anonymised_at never changes"),
        ("anonymised_at = now() + interval '1 day'", "anonymised_at never changes"),
        ("status = 'active'", "ck_users_anonymised_is_deleted"),
        ("phone_enc = 'x'", "ck_users_phone_enc_until_anonymised"),
        # The trigger lets a null dob be set once; the row's check doesn't.
        ("dob = '1990-01-01'", "ck_users_anonymised_is_empty"),
        ("pin_hash = 'a-pin-hash'", "ck_users_anonymised_is_empty"),
    ]
    for assignments, why in refused:
        with pytest.raises(IntegrityError, match=why):
            await _update(db, user.id, assignments)


async def test_only_an_anonymised_row_has_no_number(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user = await _deleted(db, make_user)

    with pytest.raises(IntegrityError, match="ck_users_phone_enc_until_anonymised"):
        await _update(db, user.id, "phone_enc = null")
    with pytest.raises(IntegrityError, match="ck_users_anonymised_is_deleted"):
        await _update(
            db, user.id, "status = 'active', anonymised_at = now(), phone_enc = null"
        )


async def test_a_number_holds_one_live_account_and_any_number_of_erased_ones(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user = await _deleted(db, make_user)
    values = {"h": user.phone_hash}
    insert = text(
        "insert into users (phone_hash, phone_enc, referral_code) "
        "values (:h, 'enc', :code)"
    )

    with pytest.raises(IntegrityError, match="uq_users_phone_hash_live"):
        async with db.begin_nested():
            await db.execute(insert, {**values, "code": "LIVE0001"})

    await _update(db, user.id, "dob = null, anonymised_at = now(), phone_enc = null")
    await db.execute(insert, {**values, "code": "LIVE0002"})
    with pytest.raises(IntegrityError, match="uq_users_phone_hash_live"):
        async with db.begin_nested():
            await db.execute(insert, {**values, "code": "LIVE0003"})


ANONYMISED = "a3c12afe34d5"
BEFORE = "9b4e0d2c7a15"


async def test_the_downgrade_refuses_while_an_account_is_erased(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user = await _deleted(db, make_user)
    await _update(db, user.id, "dob = null, anonymised_at = now(), phone_enc = null")

    with pytest.raises(RuntimeError, match="1 accounts are anonymised"):
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)
