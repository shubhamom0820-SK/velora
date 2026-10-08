"""A crowd of finished profiles for discovery's plan and timing (T-6.2), written
in one statement per table, the same every run (`setseed`).

Two shapes, the plan's Q7:

- `spread`: across twenty Indian cities, each person within about 20 km of
  their city's middle, so 25 km around Phagwara holds a twentieth of them. The
  radius is selective: the case the GIST index is for.
- `launch`: everyone inside Phagwara's 25 km (D-013), the day-one city. The
  radius selects all of them, so this is the worst case for the ranking,
  which must score every candidate.

Half are women seeking men, half men seeking women; every woman is verified
(D-008), a third of the men. Every position is a grid point (D-490), as the
CHECK requires. Activity, age on the app and completeness spread across what
the rules allow. Never seeded anywhere but a test's own transaction or the
bench's own database: these rows have no wallet and no sign-in.
"""

from __future__ import annotations

from typing import Final, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Shape = Literal["spread", "launch"]

PHAGWARA: Final = (31.22, 75.77)
# (lat, lng): Phagwara first, then nineteen more, north to south.
CITIES: Final = (
    PHAGWARA,
    (32.73, 74.86),  # Jammu
    (30.90, 75.85),  # Ludhiana
    (30.73, 76.78),  # Chandigarh
    (28.61, 77.21),  # Delhi
    (26.91, 75.79),  # Jaipur
    (26.85, 80.95),  # Lucknow
    (25.59, 85.14),  # Patna
    (26.14, 91.74),  # Guwahati
    (23.02, 72.57),  # Ahmedabad
    (23.26, 77.41),  # Bhopal
    (22.57, 88.36),  # Kolkata
    (21.15, 79.09),  # Nagpur
    (19.08, 72.88),  # Mumbai
    (18.52, 73.86),  # Pune
    (17.39, 78.49),  # Hyderabad
    (12.97, 77.59),  # Bengaluru
    (13.08, 80.27),  # Chennai
    (9.93, 76.27),  # Kochi
    (8.52, 76.94),  # Thiruvananthapuram
)
SPREAD_KM: Final = 20.0
LAUNCH_KM: Final = 24.0
ABOUT: Final = "A crowd profile for discovery's plan and its timing, nobody real."


async def crowd(session: AsyncSession, count: int, shape: Shape, *, tag: str) -> None:
    """`count` people of `shape`, their usernames and phone hashes carrying
    `tag`, so two crowds never collide. In the caller's transaction."""
    centres = [PHAGWARA] if shape == "launch" else list(CITIES)
    radius_km = LAUNCH_KM if shape == "launch" else SPREAD_KM
    values = ", ".join(f"({i}, {lat}, {lng})" for i, (lat, lng) in enumerate(centres))
    await session.execute(text("SELECT setseed(0.4242)"))
    await session.execute(
        text(
            f"""
            CREATE TEMP TABLE crowd_people ON COMMIT DROP AS
            SELECT n, gen_random_uuid() AS id,
                   CASE WHEN n % 2 = 0 THEN 'female' ELSE 'male' END AS gender,
                   c.lat, c.lng, random() AS r1, random() AS r2, random() AS r3
            FROM generate_series(1, :count) AS n
            JOIN (VALUES {values}) AS c(i, lat, lng) ON c.i = n % :centres
            """
        ),
        {"count": count, "centres": len(centres)},
    )
    await session.execute(
        text(
            """
            INSERT INTO users (id, phone_hash, phone_enc, gender, dob, role, status,
                               onboarding_step, is_verified, referral_code,
                               last_active_at, created_at, updated_at)
            SELECT id, 'crowd-' || :tag || '-' || n, '\\x00'::bytea,
                   CAST(gender AS gender_t), DATE '1998-01-01' + (n % 3000),
                   'user', 'active', 'done',
                   gender = 'female' OR n % 3 = 0,
                   'CR' || :tag || n,
                   CASE WHEN n % 10 = 0 THEN NULL
                        ELSE now() - make_interval(mins => (r3 * 20000)::int) END,
                   now() - make_interval(days => n % 40), now()
            FROM crowd_people
            """
        ),
        {"tag": tag},
    )
    await session.execute(
        text(
            """
            INSERT INTO profiles (user_id, first_name, username, about, hometown, city,
                                  seeking, location, location_updated_at,
                                  completeness, created_at, updated_at)
            SELECT id, 'Crowd', 'c' || :tag || n, :about, 'Somewhere', 'Somewhere',
                   CAST(CASE WHEN gender = 'female' THEN 'men' ELSE 'women' END
                        AS seeking_t),
                   ST_SnapToGrid(ST_Project(
                       ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
                       :radius_m * sqrt(r1), radians(360 * r2))::geometry, 0.01
                   )::geography,
                   now(), 50 + 10 * (n % 6), now(), now()
            FROM crowd_people
            """
        ),
        {"tag": tag, "about": ABOUT, "radius_m": radius_km * 1000},
    )
    await session.execute(text("DROP TABLE crowd_people"))
    await session.execute(text("ANALYZE users"))
    await session.execute(text("ANALYZE profiles"))
