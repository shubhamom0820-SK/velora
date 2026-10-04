"""phagwara areas

Revision ID: bc589ac265c2
Revises: 8f09b5c19ccd
Create Date: 2026-10-05 00:31:23.764849

Phagwara's areas replace Bengaluru's (P-38). D-013 made Phagwara the launch
city; T-1.14's reference data (fa16c0908c2c) had seeded 40 Bengaluru
neighbourhoods as that decision's old default. This deletes those 40 and inserts
Phagwara's; fa16c0908c2c stays as merged (rule 11). The registered office is in
Hajipur, and these stay Phagwara's: they differ on purpose (D-058).

Where the points come from: drafted by Claude on 5 October 2026 from
OpenStreetMap (Overpass and Nominatim, read that day). Each is a point inside the
locality as OSM has it (an address there, a health centre, a village's own
point), not a measured centre; each row names its source. Which localities to
take, and why some are left out, is in P-38's entry in docs/05-PLAN.md. Every
row says whether the founder confirmed it; "not yet reviewed" is a draft nobody
has checked against the ground.

The closest two are 510 m apart (Guru Hargobind Nagar and Model Town). The dev
seed scatters each profile under half that from its centroid (seed/run.py,
SCATTER_RADIUS_M), and a test holds it there.

Removing an area a profile points at fails on its foreign key
(`profiles.area_id`, on delete restrict), which says nothing about why. So each
direction first counts the profiles in the areas it would remove, with the same
condition as the delete, and stops with a message naming the fix if there are
any (P-38, from T-1.15).

Bengaluru's 40 are copied here, not imported from fa16c0908c2c, so what the
downgrade restores is fixed in this file. Tables are written through sa.table()
stand-ins, not the models (rule 11).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bc589ac265c2"
down_revision: str | Sequence[str] | None = "8f09b5c19ccd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNREVIEWED = "not yet reviewed"

CITY = "Phagwara"
AREAS = (
    # (name, latitude, longitude, the founder's review), each sourced above it.
    # In town. Mean of 11 OSM addresses naming it (hospitals, cafes, a blood bank).
    ("Guru Hargobind Nagar", 31.2153, 75.7747, UNREVIEWED),
    # One OSM address: a shop on Geeta Bhawan Road, Model Town.
    ("Model Town", 31.2139, 75.7696, UNREVIEWED),
    # Mean of 4 OSM addresses on Banga Road, one naming Subhash Nagar.
    ("Banga Road", 31.2196, 75.7776, UNREVIEWED),
    # One OSM address: a shop on Sarai Road.
    ("Sarai Road", 31.2212, 75.7710, UNREVIEWED),
    # Nominatim: Rivera Cineplex, addressed Satnampura.
    ("Satnampura", 31.2223, 75.7606, UNREVIEWED),
    # Nominatim: the middle of Bhagatpura Road.
    ("Bhagatpura", 31.2166, 75.7602, UNREVIEWED),
    # One OSM address: the Civil Hospital, Chahal Nagar.
    ("Chahal Nagar", 31.2304, 75.7628, UNREVIEWED),
    # One OSM address, near the Sai Mandir.
    ("Sukhchain Nagar", 31.2213, 75.7867, UNREVIEWED),
    # Nominatim: Primary Health Centre Hadiabad, Raja Garden Road.
    ("Hadiabad", 31.2229, 75.7420, UNREVIEWED),
    # Around LPU. Mean of 7 OSM addresses on Law Gate Road.
    ("Law Gate", 31.2536, 75.6969, UNREVIEWED),
    # Nominatim: Lovely Professional University's own point.
    ("LPU", 31.2533, 75.7033, UNREVIEWED),
    # Nominatim: Maheru's health sub-centre.
    ("Maheru", 31.2414, 75.6821, UNREVIEWED),
    # Nominatim: Chaheru's health sub-centre.
    ("Chaheru", 31.2698, 75.7028, UNREVIEWED),
    # Villages within 3 km of OSM's point for the town. OSM's own village points.
    ("Guru Nanak Nagar", 31.2257, 75.7977, UNREVIEWED),
    ("Chachoki", 31.1965, 75.7742, UNREVIEWED),
    ("Ghauspur", 31.2187, 75.8006, UNREVIEWED),
    ("Bhullarai", 31.2440, 75.7856, UNREVIEWED),
)

# What fa16c0908c2c seeded, for the downgrade to put back. Copied verbatim.
OLD_CITY = "Bengaluru"
OLD_AREAS = (
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

areas = sa.table(
    "areas",
    sa.column("id"),
    sa.column("city"),
    sa.column("name"),
    sa.column("centroid"),
)
profiles = sa.table("profiles", sa.column("area_id"))


class AreasInUse(RuntimeError):
    """Profiles sit in areas this migration would remove."""


def _these(city: str, names: Sequence[str]) -> sa.ColumnElement[bool]:
    """The one condition both the count and the delete use, so they can't differ."""
    return sa.and_(areas.c.city == city, areas.c.name.in_(names))


def _insert(city: str, rows: Sequence[tuple[str, float, float]]) -> sa.Executable:
    return (
        postgresql.insert(areas)
        .values(
            [
                {
                    "city": city,
                    "name": name,
                    "centroid": sa.func.ST_GeogFromText(
                        f"SRID=4326;POINT({lng} {lat})"
                    ),
                }
                for name, lat, lng in rows
            ]
        )
        .on_conflict_do_nothing()
    )


def _replace(
    remove: tuple[str, Sequence[str]],
    add: tuple[str, Sequence[tuple[str, float, float]]],
    fix: str,
) -> None:
    city, names = remove
    bind = op.get_bind()
    in_use = bind.scalar(
        sa.select(sa.func.count())
        .select_from(profiles.join(areas, profiles.c.area_id == areas.c.id))
        .where(_these(city, names))
    )
    if in_use:
        raise AreasInUse(
            f"{in_use} profiles are in {city}'s areas, which this migration "
            f"removes (P-38), so it stopped before changing anything. {fix}"
        )
    op.execute(sa.delete(areas).where(_these(city, names)))
    op.execute(_insert(*add))


def upgrade() -> None:
    """Upgrade schema."""
    _replace(
        (OLD_CITY, [name for name, _, _ in OLD_AREAS]),
        (CITY, [(name, lat, lng) for name, lat, lng, _ in AREAS]),
        "On a dev database they're the seed's: tell the founder, then make "
        "infra-reset (it drops every session's databases), then make infra-up "
        "migrate seed. Anywhere else they're real people: move their areas to "
        f"{CITY}'s first, never delete them.",
    )


def downgrade() -> None:
    """Downgrade schema."""
    _replace(
        (CITY, [name for name, _, _, _ in AREAS]),
        (OLD_CITY, OLD_AREAS),
        "Move them out of those areas first, or stay at this revision.",
    )
