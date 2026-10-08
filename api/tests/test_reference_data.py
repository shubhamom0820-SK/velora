"""Reference data (T-1.14): the catalogues match D-004, D-005, D-016 and
03-SCHEMA.md §8, and seeding twice changes nothing. P-25 adds the intents
catalogue (D-041), and T-3.2 the OTP daily cap (D-066), tested the same way.
T-5.2's data migrations reprice them (D-098, D-099, D-231, D-250): the tests
read the head, and one goes back to T-1.14's values to check its downgrades.
P-370 moves the "liked you" reveal from 20 to 1 Vela, tested the same way.
P-38 replaces T-1.14's Bengaluru areas with Phagwara's (D-013).

Expected values are written out here, not read from the migration, so a wrong
value in the migration fails a test instead of agreeing with itself.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from collections.abc import Callable
from itertools import pairwise
from types import ModuleType

import pytest
from alembic.config import Config
from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from alembic import command
from app.core.enums import LedgerReason
from tests.conftest import MakeUser
from tests.infra import API_DIR, run_alembic

COUNTS = {
    "action_prices": 9,
    "credit_packs": 8,
    "gifts": 6,
    "app_config": 11,
    "interests": 24,
    "areas": 17,
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


# Prices (D-004, then D-098, D-231 and D-250: T-5.2).


async def test_action_prices_are_d098_and_d231(db: AsyncSession) -> None:
    rows = await db.execute(
        text("select action, credits from action_prices where active")
    )

    assert dict(rows.tuples().all()) == {
        "thread_open": 5,
        "thread_reopen": 2,  # D-098, was D-004's 3
        "thread_extend": 10,  # D-097, D-098: re-open and Extend move together
        "dm_open": 8,  # D-231, the first private message, was 5
        "dm_message": 2,  # D-231, each private message after it
        "album_request": 1,  # D-231, viewing private pictures, was 5
        "voice_unlock": 5,  # D-004's, by default (D-231)
        "super_like": 5,  # D-004's, by default: not swiping (D-250)
        "liked_you_reveal": 1,  # the founder, 8 October 2026 (P-370), was 20
    }
    assert await db.scalar(text("select count(*) from action_prices")) == 9


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


# Packs (D-005, then D-099 and D-250: T-5.2).


async def test_the_active_packs_are_the_d099_ladder(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            text(
                "select id, credits, price_paise, variant from credit_packs "
                "where active order by sort"
            )
        )
    ).all()

    assert [tuple(row) for row in rows] == [
        ("pack-30", 30, 150_000, "A"),
        # Dominated on purpose (D-099): ₹1,500 more buys 150 more Velas.
        ("pack-100", 100, 450_000, "A"),
        ("pack-250", 250, 600_000, "A"),
        ("pack-450", 450, 1_000_000, "A"),
    ]
    # Each larger pack is cheaper per Vela — compared in integers (D-029).
    assert all(
        price * next_credits > next_price * credits
        for (_, credits, price, _), (_, next_credits, next_price, _) in pairwise(rows)
    )


async def test_the_old_packs_are_retired_never_deleted(db: AsyncSession) -> None:
    """D-005's three that D-099 dropped, and `entry-25`, T-10.4's variant B:
    ₹40 a Vela, below the new entry pack's ₹50 (D-250). Kept, since
    `payments` points at packs (rule 12)."""
    rows = await db.execute(
        text("select id, credits, price_paise from credit_packs where not active")
    )

    assert sorted(tuple(row) for row in rows) == [
        ("entry-25", 25, 99_900),
        ("pack-25", 25, 150_000),
        ("pack-50", 50, 250_000),
        ("pack-75", 75, 337_500),
    ]


async def test_every_pack_has_the_first_purchase_bonus(db: AsyncSession) -> None:
    """20%, kept on D-099's packs (D-231)."""
    rows = await db.execute(text("select distinct bonus_first_pct from credit_packs"))

    assert rows.scalars().all() == [20]


# Gifts (D-016, then D-231 and D-252: T-5.2).


async def test_the_active_gifts_are_d231s_four(db: AsyncSession) -> None:
    rows = await db.execute(
        text("select id, label, asset, credits from gifts where active order by sort")
    )

    assert [tuple(row) for row in rows] == [
        ("coffee", "Coffee", "☕", 5),
        ("rose", "Rose", "🌹", 10),
        ("chocolate", "Chocolate", "🍫", 15),
        ("teddy", "Teddy", "🧸", 20),
    ]


async def test_the_free_gifts_are_retired_never_deleted(db: AsyncSession) -> None:
    """`gift_sends` points at gifts (rule 12)."""
    rows = await db.execute(text("select id from gifts where not active order by id"))

    assert rows.scalars().all() == ["smile", "wave"]


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
        # D-231, T-5.2: free sends a week, replacing D-016's 3 a day.
        "gift_free_weekly_limit": 15,
        "gift_same_recipient_cooldown_h": 24,
        # T-3.2, D-066: at most ₹100 a day of Path B SMS at ₹0.20 each.
        "otp_sms_daily_cap": 500,
        # T-8.1, D-450, D-482: 18%, read only once registered (P-350).
        "gst_rate_bps": 1800,
        # T-7.1, D-098: a woman's limits by the IST day, never prices.
        "women_new_men_daily_limit": 30,
        "women_private_messages_daily_limit": 30,
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


# Areas: the launch city's location fallback (D-034), Phagwara's since P-38.

PHAGWARA = "SRID=4326;POINT(75.7696 31.2207)"  # OSM's point for the town
PHAGWARA_AREAS = {
    "Guru Hargobind Nagar",
    "Model Town",
    "Banga Road",
    "Sarai Road",
    "Satnampura",
    "Bhagatpura",
    "Chahal Nagar",
    "Sukhchain Nagar",
    "Hadiabad",
    "Law Gate",
    "LPU",
    "Maheru",
    "Chaheru",
    "Guru Nanak Nagar",
    "Chachoki",
    "Ghauspur",
    "Bhullarai",
}


async def test_areas_are_in_the_launch_city(db: AsyncSession) -> None:
    """Swapped latitude and longitude would land thousands of km away, and a
    Bengaluru area left behind would show up as a second city."""
    cities, farthest_km, distinct_points = (
        await db.execute(
            text(
                "select array_agg(distinct city), "
                "max(ST_Distance(centroid, ST_GeogFromText(:centre))) / 1000, "
                "count(distinct ST_AsText(centroid)) from areas"
            ),
            {"centre": PHAGWARA},
        )
    ).one()

    assert cities == ["Phagwara"]
    assert farthest_km < 10
    assert distinct_points == COUNTS["areas"]


async def test_the_areas_are_phagwaras_list(db: AsyncSession) -> None:
    names = set((await db.execute(text("select name from areas"))).scalars())

    assert names == PHAGWARA_AREAS


# Running it again.


async def test_seeding_again_changes_nothing(db: AsyncSession) -> None:
    """Run twice: a later migration may remove a seeded row, which the first
    run puts back (T-5.2 retired `gift_free_daily_limit`, P-38 Bengaluru's 40
    areas); the second must change nothing."""
    for statement in REVISION.reference_data():
        await db.execute(statement)
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


# --- T-5.2: the data migrations go back to T-1.14's values --------------------

T52_SCHEMA = "a1d7de534ef7"  # the last of T-5.2's schema migrations


async def _catalogues(
    connection: AsyncConnection,
) -> dict[str, set[tuple[object, ...]]]:
    queries = {
        "action_prices": "select action, credits, active from action_prices",
        "credit_packs": (
            "select id, credits, price_paise, sort, variant, active from credit_packs"
        ),
        "gifts": "select id, label, asset, credits, sort, active from gifts",
        "app_config": "select key, value::text from app_config",
    }
    return {
        table: {tuple(row) for row in await connection.execute(text(query))}
        for table, query in queries.items()
    }


async def test_t52_data_downgrades_restore_t114s_values(
    test_engine: AsyncEngine,
) -> None:
    """Each of T-5.2's data migrations undone puts back exactly what T-1.14
    seeded, with nothing of T-5.2's left over, active or not."""
    try:
        await run_alembic(test_engine, command.downgrade, T52_SCHEMA)
        async with test_engine.connect() as connection:
            found = await _catalogues(connection)
    finally:
        await run_alembic(test_engine, command.upgrade, "head")

    assert found["action_prices"] == {
        (action, credits, True) for action, credits in REVISION.ACTION_PRICES.items()
    }
    assert found["credit_packs"] == {
        (pack_id, credits, price, sort, variant, True)
        for pack_id, credits, price, sort, variant in REVISION.CREDIT_PACKS
    }
    assert found["gifts"] == {
        (gift_id, label, asset, credits, sort, True)
        for sort, (gift_id, label, asset, credits) in enumerate(REVISION.GIFTS, start=1)
    }
    assert found["app_config"] == {
        (key, json.dumps(value))
        for key, value in {**REVISION.APP_CONFIG, "otp_sms_daily_cap": 500}.items()
    }


# --- P-370: the "liked you" reveal at 1 Vela (D-004's note) -------------------

REVEAL_REVISION = _revision("e4e517f62ce3")


async def _prices(connection: AsyncConnection) -> dict[str, tuple[int, bool]]:
    rows = await connection.execute(
        text("select action, credits, active from action_prices")
    )
    return {action: (credits, active) for action, credits, active in rows}


async def test_the_reveal_moves_and_nothing_else_does(test_engine: AsyncEngine) -> None:
    """Undone, the reveal is D-004's 20; done again, 1. Every other row is the
    same throughout, credits and active alike."""
    async with test_engine.connect() as connection:
        at_head = await _prices(connection)
    try:
        await run_alembic(test_engine, command.downgrade, REVEAL_REVISION.down_revision)
        async with test_engine.connect() as connection:
            undone = await _prices(connection)
    finally:
        await run_alembic(test_engine, command.upgrade, "head")
    async with test_engine.connect() as connection:
        redone = await _prices(connection)

    assert at_head["liked_you_reveal"] == (1, True)
    assert undone == {**at_head, "liked_you_reveal": (20, True)}
    assert redone == at_head


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


# --- P-38: Phagwara's areas replace Bengaluru's (D-013) ---------------------------

AREAS_REVISION = _revision("bc589ac265c2")


async def _alembic(db: AsyncSession, run: Callable[..., object], revision: str) -> None:
    """Run an Alembic command on the test's own connection, inside its
    transaction: Alembic sees one already open and leaves it to us."""
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        run(config, revision)

    await connection.run_sync(_run)


async def _place(db: AsyncSession, user_id: uuid.UUID, city: str, name: str) -> None:
    """Put the user in an area, by SQL alone: the schema may be one a
    downgrade left, older than the models (T-9.6 added a `users` column)."""
    await db.execute(
        text(
            "update profiles set area_id = "
            "(select id from areas where city = :city and name = :name) "
            "where user_id = :user"
        ),
        {"city": city, "name": name, "user": user_id},
    )


async def _cities(db: AsyncSession) -> dict[str, int]:
    rows = await db.execute(text("select city, count(*) from areas group by city"))
    return {city: count for city, count in rows.tuples()}


async def test_the_downgrade_puts_bengalurus_40_back(test_engine: AsyncEngine) -> None:
    try:
        await run_alembic(test_engine, command.downgrade, AREAS_REVISION.down_revision)
        async with test_engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "select city, count(*), "
                    "ST_AsText((array_agg(centroid) filter "
                    "(where name = 'Koramangala'))[1]) from areas group by city"
                )
            )
            found = rows.all()
    finally:
        await run_alembic(test_engine, command.upgrade, "head")

    assert [tuple(row) for row in found] == [
        ("Bengaluru", 40, "POINT(77.6245 12.9352)")
    ]


@pytest.mark.parametrize(
    ("direction", "city", "name", "found", "fix"),
    [
        (
            "upgrade",
            "Bengaluru",
            "Koramangala",
            (
                "1 profiles are in Bengaluru's areas, which this migration removes "
                "(P-38), so it stopped before changing anything."
            ),
            (
                "tell the founder, then make infra-reset (it drops every session's "
                "databases), then make infra-up migrate seed."
            ),
        ),
        (
            "downgrade",
            "Phagwara",
            "Law Gate",
            (
                "1 profiles are in Phagwara's areas, which this migration removes "
                "(P-38), so it stopped before changing anything."
            ),
            "Move them out of those areas first",
        ),
    ],
    ids=["upgrade", "downgrade"],
)
async def test_the_migration_refuses_to_remove_an_area_in_use(
    db: AsyncSession,
    make_user: MakeUser,
    direction: str,
    city: str,
    name: str,
    found: str,
    fix: str,
) -> None:
    """A profile in an area it would remove: it stops with a message naming the
    fix, not a bare foreign-key error, and changes nothing. Rolled back. The
    user is made at head, through the models, before any downgrade."""
    user, _ = await make_user()
    with pytest.raises(RuntimeError) as refused:
        async with db.begin_nested():
            if direction == "upgrade":
                await _alembic(db, command.downgrade, AREAS_REVISION.down_revision)
                await _place(db, user.id, city, name)
                await _alembic(db, command.upgrade, AREAS_REVISION.revision)
            else:
                await _place(db, user.id, city, name)
                await _alembic(db, command.downgrade, AREAS_REVISION.down_revision)

    assert type(refused.value).__name__ == "AreasInUse"
    assert found in str(refused.value)
    assert fix in str(refused.value)
    assert await _cities(db) == {"Phagwara": 17}  # head, as the harness left it


async def test_the_migration_counts_only_the_areas_it_removes(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Someone in another city's area doesn't stop it: the count has the
    delete's own condition, not "anyone with an area"."""
    user, _ = await make_user()
    async with db.begin_nested():
        await _alembic(db, command.downgrade, AREAS_REVISION.down_revision)
        await db.execute(
            text(
                "insert into areas (city, name, centroid) values "
                "('Elsewhere', 'Somewhere', ST_GeogFromText('SRID=4326;POINT(75 31)'))"
            )
        )
        await _place(db, user.id, "Elsewhere", "Somewhere")
        await _alembic(db, command.upgrade, AREAS_REVISION.revision)

    assert await _cities(db) == {"Phagwara": 17, "Elsewhere": 1}
