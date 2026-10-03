"""Reference data (T-1.14): the catalogues match D-004, D-005, D-016 and
03-SCHEMA.md §8, and seeding twice changes nothing. P-25 adds the intents
catalogue (D-041), and T-3.2 the OTP daily cap (D-066), tested the same way.

Expected values are written out here, not read from the migration, so a wrong
value in the migration fails a test instead of agreeing with itself.
"""

from __future__ import annotations

import importlib.util
from itertools import pairwise
from types import ModuleType

import pytest
from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic import command
from app.core.enums import LedgerReason
from tests.infra import API_DIR, run_alembic

COUNTS = {
    "action_prices": 7,
    "credit_packs": 5,
    "gifts": 6,
    "app_config": 8,
    "interests": 24,
    "areas": 40,
}


def _revision(revision_id: str) -> ModuleType:
    """A migration itself, so the re-run tests execute its exact inserts."""
    [path] = (API_DIR / "alembic" / "versions").glob(f"*_{revision_id}_*.py")
    spec = importlib.util.spec_from_file_location(f"revision_{revision_id}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REVISION = _revision("fa16c0908c2c")


async def _counts(db: AsyncSession) -> dict[str, int]:
    return {
        table: await db.scalar(text(f"select count(*) from {table}"))
        for table in COUNTS
    }


@pytest.mark.parametrize(("table", "expected"), COUNTS.items())
async def test_counts_match(db: AsyncSession, table: str, expected: int) -> None:
    assert await db.scalar(text(f"select count(*) from {table}")) == expected


# Prices (D-004).


async def test_action_prices_are_d004(db: AsyncSession) -> None:
    rows = await db.execute(text("select action, credits from action_prices"))

    assert dict(rows.tuples().all()) == {
        "thread_open": 5,
        "dm_open": 5,
        "thread_reopen": 3,
        "voice_unlock": 5,
        "album_request": 5,
        "super_like": 5,
        "liked_you_reveal": 20,
    }


async def test_every_priced_action_is_a_ledger_reason(db: AsyncSession) -> None:
    """A price's key is the reason its debit is written with."""
    actions = set(
        (await db.execute(text("select action from action_prices"))).scalars()
    )

    assert actions <= {reason.value for reason in LedgerReason}


async def test_the_knot_has_no_price(db: AsyncSession) -> None:
    """Permanence is granted by the other person, never bought (D-003)."""
    priced = await db.scalar(
        text("select count(*) from action_prices where action like '%knot%'")
    )

    assert priced == 0


# Packs (D-005).


async def test_variant_a_is_the_d005_ladder(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            text(
                "select id, credits, price_paise from credit_packs "
                "where variant = 'A' order by sort"
            )
        )
    ).all()

    assert [tuple(row) for row in rows] == [
        ("pack-25", 25, 150_000),
        ("pack-50", 50, 250_000),
        ("pack-75", 75, 337_500),
        ("pack-100", 100, 400_000),
    ]
    # Each larger pack is cheaper per credit — compared in integers (D-029).
    assert all(
        price * next_credits > next_price * credits
        for (_, credits, price), (_, next_credits, next_price) in pairwise(rows)
    )


async def test_variant_b_is_the_entry_pack(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            text(
                "select id, credits, price_paise from credit_packs where variant = 'B'"
            )
        )
    ).all()

    assert [tuple(row) for row in rows] == [("entry-25", 25, 99_900)]


async def test_every_pack_is_active_with_the_first_purchase_bonus(
    db: AsyncSession,
) -> None:
    rows = await db.execute(
        text("select distinct bonus_first_pct, active from credit_packs")
    )

    assert [tuple(row) for row in rows] == [(20, True)]


# Gifts (D-016).


async def test_gifts_are_d016(db: AsyncSession) -> None:
    rows = await db.execute(text("select id, credits from gifts order by sort"))

    assert [tuple(row) for row in rows] == [
        ("smile", 0),
        ("wave", 0),
        ("rose", 2),
        ("coffee", 2),
        ("chocolate", 4),
        ("teddy", 4),
    ]


# app_config (03-SCHEMA.md §8).


async def test_app_config_seeds(db: AsyncSession) -> None:
    rows = await db.execute(
        text("select key, value from app_config").columns(key=Text, value=JSONB)
    )

    assert dict(rows.tuples().all()) == {
        "swipe_daily_limit_men": 50,
        "discovery_radius_km": 25,
        # Promised in copy, in web/src/i18n/en.ts: the landing page ("Threads last
        # a day", "24-hour", T-2.1) and /terms ("lasts a day", T-2.2). A migration
        # changing it changes that copy too.
        "thread_hours": 24,
        # Promised on /terms and /privacy ("first 20 messages", T-2.2): a migration
        # changing it changes that copy too.
        "mask_first_n_messages": 20,
        "kudos_min_messages": 6,
        "gift_free_daily_limit": 3,
        "gift_same_recipient_cooldown_h": 24,
        # T-3.2, D-066: at most ₹100 a day of Path B SMS at ₹0.20 each.
        "otp_sms_daily_cap": 500,
    }


# Interests: fixed ids, because the API takes them.


async def test_interests_have_fixed_ids_in_order(db: AsyncSession) -> None:
    rows = (
        await db.execute(text("select id, slug, label from interests order by id"))
    ).all()

    assert [row.id for row in rows] == list(range(1, 25))
    assert [row.label for row in rows] == [
        "Filter coffee",
        "Trekking",
        "Indie music",
        "Pottery",
        "Dogs",
        "Cats",
        "Old Hindi cinema",
        "Badminton",
        "Street food",
        "Sketching",
        "Reading",
        "Yoga",
        "Baking",
        "Gaming",
        "Anime",
        "Running",
        "Photography",
        "Cricket",
        "Travel",
        "Startups",
        "Cooking",
        "Hopeless romantic",
        "Yapper",
        "Yearner",
    ]
    assert (rows[0].slug, rows[6].slug) == ("filter-coffee", "old-hindi-cinema")


# Areas: the launch city's location fallback (D-034).

MG_ROAD = "SRID=4326;POINT(77.5946 12.9716)"


async def test_areas_are_in_the_launch_city(db: AsyncSession) -> None:
    """Swapped latitude and longitude would land thousands of km away."""
    cities, farthest_km, distinct_points = (
        await db.execute(
            text(
                "select array_agg(distinct city), "
                "max(ST_Distance(centroid, ST_GeogFromText(:centre))) / 1000, "
                "count(distinct ST_AsText(centroid)) from areas"
            ),
            {"centre": MG_ROAD},
        )
    ).one()

    assert cities == ["Bengaluru"]
    assert farthest_km < 30
    assert distinct_points == COUNTS["areas"]


# Running it again.


async def test_seeding_again_changes_nothing(db: AsyncSession) -> None:
    before = await _counts(db)

    for statement in REVISION.reference_data():
        await db.execute(statement)

    assert await _counts(db) == before


async def test_seeding_again_keeps_tuned_values(db: AsyncSession) -> None:
    """Prices and settings are tuned as data; a re-run must never reset them."""
    await db.execute(text("update gifts set credits = 3 where id = 'rose'"))
    await db.execute(
        text("update action_prices set credits = 6 where action = 'thread_open'")
    )
    await db.execute(
        text("update app_config set value = '40' where key = 'swipe_daily_limit_men'")
    )

    for statement in REVISION.reference_data():
        await db.execute(statement)

    tuned = (
        await db.execute(
            text(
                "select (select credits from gifts where id = 'rose'), "
                "(select credits from action_prices where action = 'thread_open'), "
                "(select value::int from app_config where key = 'swipe_daily_limit_men')"
            )
        )
    ).one()
    assert tuple(tuned) == (3, 6, 40)


async def test_downgrade_removes_the_seeds(test_engine: AsyncEngine) -> None:
    """The round trip can't see an incomplete downgrade: its upgrade inserts with
    DO NOTHING, so leftover rows pass silently. Check the tables are empty."""
    try:
        await run_alembic(test_engine, command.downgrade, REVISION.down_revision)
        async with test_engine.connect() as connection:
            left = {
                table: await connection.scalar(text(f"select count(*) from {table}"))
                for table in COUNTS
            }
    finally:
        await run_alembic(test_engine, command.upgrade, "head")

    assert left == dict.fromkeys(COUNTS, 0)


# --- P-25: intents (D-041) ----------------------------------------------------

INTENTS_REVISION = _revision("c4193b88d395")


async def test_intents_have_fixed_ids_in_order(db: AsyncSession) -> None:
    rows = (
        await db.execute(text("select id, slug, label from intents order by id"))
    ).all()

    assert [row.id for row in rows] == list(range(1, 11))
    assert [row.label for row in rows] == [
        "Something serious",
        "Long term",
        "Situationship",
        "Casual dating",
        "Just one night",
        "No strings attached",
        "Open relationship",
        "Discreet",
        "Friendship",
        "Go with the flow",
    ]
    assert (rows[0].slug, rows[9].slug) == ("something-serious", "go-with-the-flow")


async def test_intent_labels_are_sentence_case(db: AsyncSession) -> None:
    """They sit next to interests as chips on the same profile."""
    labels = (await db.execute(text("select label from intents"))).scalars().all()

    assert [label for label in labels if label[1:] != label[1:].lower()] == []


async def test_seeding_intents_again_changes_nothing(db: AsyncSession) -> None:
    await db.execute(text("update intents set label = 'Serious' where id = 1"))

    for statement in INTENTS_REVISION.reference_data():
        await db.execute(statement)

    count = await db.scalar(text("select count(*) from intents"))
    label = await db.scalar(text("select label from intents where id = 1"))
    assert (count, label) == (10, "Serious")


async def test_intents_downgrade_removes_the_seeds(test_engine: AsyncEngine) -> None:
    try:
        await run_alembic(
            test_engine, command.downgrade, INTENTS_REVISION.down_revision
        )
        async with test_engine.connect() as connection:
            left = await connection.scalar(text("select count(*) from intents"))
    finally:
        await run_alembic(test_engine, command.upgrade, "head")

    assert left == 0


# --- T-3.2: the OTP daily cap (D-066) -------------------------------------------

OTP_CAP_REVISION = _revision("89b155534dcf")


async def test_seeding_the_otp_cap_again_keeps_a_tuned_value(db: AsyncSession) -> None:
    await db.execute(
        text("update app_config set value = '200' where key = 'otp_sms_daily_cap'")
    )

    for statement in OTP_CAP_REVISION.reference_data():
        await db.execute(statement)

    rows = await db.execute(
        text("select value::int from app_config where key = 'otp_sms_daily_cap'")
    )
    assert rows.scalars().all() == [200]


async def test_the_otp_cap_downgrade_removes_exactly_its_key(
    test_engine: AsyncEngine,
) -> None:
    try:
        await run_alembic(
            test_engine, command.downgrade, OTP_CAP_REVISION.down_revision
        )
        async with test_engine.connect() as connection:
            keys = set(
                (await connection.execute(text("select key from app_config")))
                .scalars()
                .all()
            )
    finally:
        await run_alembic(test_engine, command.upgrade, "head")

    assert keys == {
        "swipe_daily_limit_men",
        "discovery_radius_km",
        "thread_hours",
        "mask_first_n_messages",
        "kudos_min_messages",
        "gift_free_daily_limit",
        "gift_same_recipient_cooldown_h",
    }
