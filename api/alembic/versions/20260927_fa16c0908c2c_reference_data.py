"""reference data

Revision ID: fa16c0908c2c
Revises: 959a840bb839
Create Date: 2026-09-27 00:42:59.818031

Reference data — 03-SCHEMA.md §9 (T-1.14): the catalogues the app reads prices,
packs, gifts, settings, interests and areas from. Values come from D-004 (action
prices), D-005 (credit packs), D-016 (gifts), 03-SCHEMA §8 (app_config) and the
founder's interests list. The Bengaluru areas (D-013's default) were drafted in
T-1.14 and approved; centroids are approximate to about 1 km.

Every insert is ON CONFLICT DO NOTHING, so running it again changes nothing — and
never resets a value an admin has tuned since. The tables are written through
sa.table() stand-ins, not the models, so a later model change cannot alter what
this migration does once merged (rule 11).

downgrade() deletes exactly the seeded keys. The foreign keys onto these tables
are RESTRICT, so once a pack is bought or an interest picked, it refuses.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fa16c0908c2c"
down_revision: str | Sequence[str] | None = "959a840bb839"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# D-004: the seven debit reasons of ledger_reason_t. Tying the knot and messaging
# in a knot are free and have no row — permanence is never bought (D-003).
ACTION_PRICES = {
    "thread_open": 5,
    "dm_open": 5,
    "thread_reopen": 3,
    "voice_unlock": 5,
    "album_request": 5,
    "super_like": 5,
    "liked_you_reveal": 20,
}

# D-005: (id, credits, price_paise, sort, variant). Variant B is the beta's cheaper
# entry pack (T-10.4), chosen per user by GET /packs (T-8.1). The first-purchase
# bonus is the column default, 20%.
CREDIT_PACKS = (
    ("pack-25", 25, 150_000, 1, "A"),
    ("pack-50", 50, 250_000, 2, "A"),
    ("pack-75", 75, 337_500, 3, "A"),
    ("pack-100", 100, 400_000, 4, "A"),
    ("entry-25", 25, 99_900, 1, "B"),
)

# D-016: (id, label, asset, credits), shown in this order.
GIFTS = (
    ("smile", "Smile", "😊", 0),
    ("wave", "Wave", "👋", 0),
    ("rose", "Rose", "🌹", 2),
    ("coffee", "Coffee", "☕", 2),
    ("chocolate", "Chocolate", "🍫", 4),
    ("teddy", "Teddy", "🧸", 4),
)

# 03-SCHEMA.md §8.
APP_CONFIG = {
    "swipe_daily_limit_men": 50,
    "discovery_radius_km": 25,
    "thread_hours": 24,
    "mask_first_n_messages": 20,
    "kudos_min_messages": 6,
    "gift_free_daily_limit": 3,
    "gift_same_recipient_cooldown_h": 24,
}

# Who you are — hobbies and vibe, a reason to start a conversation. Users pick
# exactly 5 (T-3.8). Ids are fixed, 1 upward in this order: the API takes them.
INTERESTS = (
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
)

# The location fallback (D-034) for the launch city. D-013 is open, defaulting to
# Bengaluru; another city is a new data migration. Centroids are approximate, to
# about 1 km — enough for a fallback whose distances are shown in whole km.
CITY = "Bengaluru"
AREAS = (
    # (name, latitude, longitude)
    ("Koramangala", 12.9352, 77.6245),
    ("Indiranagar", 12.9784, 77.6408),
    ("HSR Layout", 12.9116, 77.6474),
    ("BTM Layout", 12.9166, 77.6101),
    ("JP Nagar", 12.9063, 77.5857),
    ("Jayanagar", 12.9250, 77.5938),
    ("Basavanagudi", 12.9422, 77.5750),
    ("Banashankari", 12.9255, 77.5468),
    ("Malleshwaram", 13.0035, 77.5647),
    ("Rajajinagar", 12.9915, 77.5545),
    ("Sadashivanagar", 13.0068, 77.5813),
    ("Hebbal", 13.0358, 77.5970),
    ("Yelahanka", 13.1007, 77.5963),
    ("RT Nagar", 13.0220, 77.5950),
    ("Frazer Town", 12.9985, 77.6145),
    ("Ulsoor", 12.9800, 77.6220),
    ("MG Road", 12.9756, 77.6066),
    ("Richmond Town", 12.9610, 77.6020),
    ("Domlur", 12.9610, 77.6387),
    ("Jeevan Bima Nagar", 12.9668, 77.6585),
    ("CV Raman Nagar", 12.9855, 77.6639),
    ("Whitefield", 12.9698, 77.7500),
    ("Marathahalli", 12.9569, 77.7011),
    ("Bellandur", 12.9260, 77.6762),
    ("Electronic City", 12.8452, 77.6602),
    ("Bommanahalli", 12.9060, 77.6240),
    ("Arekere", 12.8865, 77.5980),
    ("Kalyan Nagar", 13.0250, 77.6400),
    ("Kammanahalli", 13.0155, 77.6380),
    ("Banaswadi", 13.0120, 77.6500),
    ("Hennur", 13.0358, 77.6432),
    ("Thanisandra", 13.0545, 77.6340),
    ("Mahadevapura", 12.9900, 77.6910),
    ("KR Puram", 13.0075, 77.6955),
    ("Brookefield", 12.9660, 77.7175),
    ("Yeshwanthpur", 13.0250, 77.5450),
    ("Vijayanagar", 12.9710, 77.5360),
    ("Basaveshwaranagar", 12.9930, 77.5380),
    ("Kengeri", 12.9120, 77.4840),
    ("Sahakar Nagar", 13.0622, 77.5875),
)

action_prices = sa.table("action_prices", sa.column("action"), sa.column("credits"))
credit_packs = sa.table(
    "credit_packs",
    sa.column("id"),
    sa.column("credits"),
    sa.column("price_paise"),
    sa.column("sort"),
    sa.column("variant"),
)
gifts = sa.table(
    "gifts",
    sa.column("id"),
    sa.column("label"),
    sa.column("asset"),
    sa.column("credits"),
    sa.column("sort"),
)
app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)
interests = sa.table(
    "interests", sa.column("id"), sa.column("slug"), sa.column("label")
)
areas = sa.table("areas", sa.column("city"), sa.column("name"), sa.column("centroid"))


def _slug(label: str) -> str:
    return label.lower().replace(" ", "-")


def reference_data() -> list[postgresql.Insert]:
    """The inserts, shared by upgrade() and the test that runs them twice."""
    rows: list[tuple[sa.TableClause, list[dict[str, object]]]] = [
        (
            action_prices,
            [{"action": a, "credits": c} for a, c in ACTION_PRICES.items()],
        ),
        (
            credit_packs,
            [
                {"id": i, "credits": c, "price_paise": p, "sort": s, "variant": v}
                for i, c, p, s, v in CREDIT_PACKS
            ],
        ),
        (
            gifts,
            [
                {"id": i, "label": label, "asset": a, "credits": c, "sort": sort}
                for sort, (i, label, a, c) in enumerate(GIFTS, start=1)
            ],
        ),
        (app_config, [{"key": k, "value": v} for k, v in APP_CONFIG.items()]),
        (
            interests,
            [
                {"id": i, "slug": _slug(label), "label": label}
                for i, label in enumerate(INTERESTS, start=1)
            ],
        ),
        (
            areas,
            [
                {
                    "city": CITY,
                    "name": name,
                    "centroid": sa.func.ST_GeogFromText(
                        f"SRID=4326;POINT({lng} {lat})"
                    ),
                }
                for name, lat, lng in AREAS
            ],
        ),
    ]
    return [
        postgresql.insert(table).values(values).on_conflict_do_nothing()
        for table, values in rows
    ]


def upgrade() -> None:
    """Upgrade schema."""
    for statement in reference_data():
        op.execute(statement)


def downgrade() -> None:
    """Downgrade schema: remove exactly the seeded keys."""
    op.execute(
        sa.delete(areas).where(
            areas.c.city == CITY, areas.c.name.in_([name for name, _, _ in AREAS])
        )
    )
    op.execute(
        sa.delete(interests).where(interests.c.id.in_(range(1, len(INTERESTS) + 1)))
    )
    op.execute(sa.delete(app_config).where(app_config.c.key.in_(list(APP_CONFIG))))
    op.execute(sa.delete(gifts).where(gifts.c.id.in_([row[0] for row in GIFTS])))
    op.execute(
        sa.delete(credit_packs).where(
            credit_packs.c.id.in_([row[0] for row in CREDIT_PACKS])
        )
    )
    op.execute(
        sa.delete(action_prices).where(action_prices.c.action.in_(list(ACTION_PRICES)))
    )
