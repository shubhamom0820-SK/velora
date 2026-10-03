"""The dev seed's checks and writes (T-1.15, D-064).

Order matters: every check that can refuse runs before a row is written. The
two checks on settings run before anything connects. The marker check is the
first statement on the connection. The whole seed is one transaction.

Every account is created by signup's own service (`users.service`, T-3.3),
with the keys the local API reads, and the PIN goes through `hash_pin`, so
sign-in finds these accounts exactly as it finds anyone else.
"""

from __future__ import annotations

import hashlib
import math
import sys
from collections.abc import KeysView, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TextIO
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.db import build_engine
from app.core.enums import Gender, OnboardingStep, SwipeDirection, UserStatus
from app.core.errors import AppError
from app.core.security import hash_phone, hash_pin, normalize_phone
from app.modules.auth import pins
from app.modules.profiles import rules
from app.modules.profiles.models import (
    Area,
    Intent,
    Interest,
    Profile,
    ProfileIntent,
    ProfileInterest,
)
from app.modules.swipes.models import Swipe
from app.modules.users import service as users_service
from app.modules.users.models import User
from seed.data import PEOPLE, SWIPES, Person, SeedSwipe

# --- The three checks: each an allowlist (rule 16, D-064) ---------------------

SEED_ALLOWED_IN: frozenset[str] = frozenset({"local"})
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})
# What `make infra-up` stamps on the local stack's database, from
# infra/postgres/stamp-local.sql. The two must match exactly; a test reads that
# file and fails if they drift. No brand name: renaming the brand mustn't
# unstamp every developer's database (rule 17).
LOCAL_DATABASE_MARKER = (
    "local-dev: stamped by make infra-up (infra/postgres/stamp-local.sql). "
    "The dev seed writes only to a database carrying this (T-1.15, D-064)."
)

# The block every seeded number sits in (seed/data.py, D-064).
SEED_PHONE_PREFIX = "+9190000"
# The profiles' areas are this city's until P-38 replaces them.
AREA_CITY = "Bengaluru"
# How far from its area's centroid a profile may sit (`scatter`). Under half the
# distance between the two closest centroids of all 40 areas (Rajajinagar and
# Malleshwaram, 1,728 m), so every profile stays nearer its own area's centroid
# than any other's; a test checks that, so P-38's areas can't quietly break it.
SCATTER_RADIUS_M = 750


class SeedRefused(Exception):
    """A check said no. The message says which, and what to do."""


def refuse_unless_local(settings: Settings) -> None:
    if settings.ENV not in SEED_ALLOWED_IN:
        raise SeedRefused(
            f"ENV={settings.ENV}: the dev seed runs only where ENV is "
            f"{', '.join(sorted(SEED_ALLOWED_IN))} (D-064). Its users are fake, "
            "and its phone numbers may be real people's."
        )


def refuse_unless_loopback(database_url: str) -> None:
    host = make_url(database_url).host
    if host not in LOOPBACK_HOSTS:
        raise SeedRefused(
            f"DATABASE_URL points at {host!r}: the dev seed writes only to a "
            f"database on this machine ({', '.join(sorted(LOOPBACK_HOSTS))}), "
            "and only to the local stack's (D-064)."
        )


async def require_local_marker(session: AsyncSession) -> None:
    """Ask the database itself. An SSH tunnel makes staging answer on
    localhost, which passes the host check; only `make infra-up` stamps this."""
    row = (
        await session.execute(
            text(
                "SELECT current_database(), shobj_description(oid, 'pg_database') "
                "FROM pg_database WHERE datname = current_database()"
            )
        )
    ).one()
    name, marker = row
    if marker != LOCAL_DATABASE_MARKER:
        raise SeedRefused(
            f"Database {name!r} isn't stamped as the local stack's. If it is the "
            "local stack's, run make infra-up, which stamps it (a container from "
            "before T-1.15 has no stamp yet), then make seed again. Otherwise the "
            "dev seed won't write to it (D-064): a tunnel can make another "
            "database's address look local, but it can't give it the stamp."
        )


# --- The data, checked against the rules before anything is written ----------


def age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def check_people(
    people: Sequence[Person], swipes: Sequence[SeedSwipe], today: date
) -> None:
    """Every rule the services will enforce but don't exist yet to enforce,
    plus the ones `make_user` holds tests to. All problems are named at once."""
    problems: list[str] = []
    for kind, values in (
        ("key", [p.key for p in people]),
        ("phone", [p.phone for p in people]),
        ("username", [p.username for p in people if p.username]),
    ):
        duplicates = sorted({v for v in values if values.count(v) > 1})
        if duplicates:
            problems.append(f"the same {kind} twice: {', '.join(duplicates)}")
    for person in people:
        problems += [f"{person.key}: {p}" for p in _person_problems(person, today)]

    by_key = {p.key: p for p in people}
    pairs = [(s.swiper, s.target) for s in swipes]
    likes = {(s.swiper, s.target) for s in swipes if s.dir is not SwipeDirection.PASS}
    for swipe in swipes:
        label = f"swipe {swipe.swiper} -> {swipe.target}"
        swiper, target = by_key.get(swipe.swiper), by_key.get(swipe.target)
        if swiper is None or target is None:
            problems.append(f"{label}: names someone who isn't in the seed")
            continue
        if swipe.swiper == swipe.target:
            problems.append(f"{label}: nobody swipes on themselves")
        if pairs.count((swipe.swiper, swipe.target)) > 1:
            problems.append(f"{label}: swiped twice; a swipe is written once")
        if {swiper.step, target.step} != {OnboardingStep.DONE}:
            problems.append(
                f"{label}: both must have finished onboarding; only they swipe "
                "and are swiped"
            )
        if {(swipe.swiper, swipe.target), (swipe.target, swipe.swiper)} <= likes:
            problems.append(
                f"{label}: liked back, which would make a match; T-6.4 makes "
                "matches, not the seed"
            )
    if problems:
        raise SeedRefused(
            "The seed's data breaks the rules (seed/data.py):\n  - "
            + "\n  - ".join(problems)
        )


def _person_problems(person: Person, today: date) -> list[str]:
    problems: list[str] = []
    try:
        if normalize_phone(person.phone) != person.phone:
            problems.append("write the phone as normalize_phone returns it")
    except AppError as error:
        problems.append(f"normalize_phone refuses the phone ({error.code})")
    if not person.phone.startswith(SEED_PHONE_PREFIX):
        problems.append(f"the phone must be in the seed's block, {SEED_PHONE_PREFIX}")

    # T-3.9's rule itself (D-069), so the seeded PIN is one the API would take.
    if person.pin is not None and (problem := pins.pin_problem(person.pin)):
        problems.append(f"the PIN {problem} (T-3.9)")

    if person.step is OnboardingStep.DOB:
        asked_later = (
            "gender",
            "dob",
            "first_name",
            "username",
            "about",
            "hometown",
            "area",
            "seeking",
            "pin",
        )
        filled = [name for name in asked_later if getattr(person, name) is not None]
        if filled or person.interests or person.intents or person.verified:
            problems.append(
                "onboarding not started, so nothing it would ask for can be set"
            )
        return problems

    for name in ("gender", "dob", "first_name", "username", "about", "hometown"):
        if getattr(person, name) is None:
            problems.append(f"past onboarding's first steps, so needs {name}")
    if person.area is None or person.seeking is None:
        problems.append("needs an area and who they're seeking")
    if person.dob is not None and age_on(person.dob, today) < 18:
        problems.append("under 18 today in IST (D-009)")
    # T-3.7's rules themselves, so a seeded profile is one the API would take.
    texts = {
        "first_name": (person.first_name, rules.first_name_problem),
        "about": (person.about, rules.about_problem),
        "hometown": (person.hometown, rules.place_problem),
    }
    for name, (value, rule) in texts.items():
        if value is None:
            continue
        if rules.clean_text(value) != value:
            problems.append(f"{name} isn't as the API stores it, trimmed and in NFC")
        elif (problem := rule(value)) is not None:
            problems.append(f"{name} {problem} (T-3.7)")
    if person.username is not None:
        if (problem := rules.username_problem(person.username)) is not None:
            problems.append(f"username {problem} (T-3.7)")
        elif rules.is_reserved(person.username):
            problems.append("username is reserved (T-3.7)")
    if len(person.interests) != 5 or len(set(person.interests)) != 5:
        problems.append("exactly 5 different interests (T-3.8)")
    if not 1 <= len(set(person.intents)) == len(person.intents) <= 3:
        problems.append("1 to 3 different intents (D-041)")
    if (
        person.step is OnboardingStep.DONE
        and person.gender is Gender.FEMALE
        and not person.verified
    ):
        problems.append(
            "an onboarded woman is always verified (D-008): the app can't "
            "produce one who isn't"
        )
    return problems


# --- The writes ------------------------------------------------------------------


def scatter(username: str) -> tuple[float, float]:
    """Where a profile sits from its area's centroid: (metres, bearing in degrees).

    On the centroid itself, everyone in one area would be 0 m apart, so
    discovery's distance sort would be all ties and `hide_distance` would have
    nothing to hide. Derived from the username, so every run puts everyone in
    the same place, and spread evenly over a disc of `SCATTER_RADIUS_M`.
    """
    digest = hashlib.sha256(username.encode()).digest()
    distance_share = int.from_bytes(digest[:8]) / 2**64
    bearing_share = int.from_bytes(digest[8:16]) / 2**64
    return SCATTER_RADIUS_M * math.sqrt(distance_share), 360 * bearing_share


@dataclass
class SeedReport:
    created: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    swipes_added: int = 0


async def write_seed(
    session: AsyncSession,
    settings: Settings,
    people: Sequence[Person] = PEOPLE,
    swipes: Sequence[SeedSwipe] = SWIPES,
) -> SeedReport:
    """Write everyone who isn't there yet, and the swipes. Insert-only: someone
    found by their phone hash is left exactly as they are."""
    # `interests.label` and `areas.name` are nullable (P-24); a row without one
    # can't be the one a label names.
    interest_ids = {
        label: id_
        for label, id_ in await session.execute(select(Interest.label, Interest.id))
        if label is not None
    }
    intent_ids = {
        label: id_
        for label, id_ in await session.execute(select(Intent.label, Intent.id))
    }
    area_ids = {
        name: id_
        for name, id_ in await session.execute(
            select(Area.name, Area.id).where(Area.city == AREA_CITY)
        )
        if name is not None
    }
    _require_catalogues(
        people,
        {
            "interest": interest_ids.keys(),
            "intent": intent_ids.keys(),
            "area": area_ids.keys(),
        },
    )

    now = clock.now()
    report = SeedReport()
    user_ids: dict[str, UUID] = {}
    for person in people:
        phone = normalize_phone(person.phone)
        phone_hash = hash_phone(phone, settings)
        existing = await session.scalar(
            select(User.id).where(User.phone_hash == phone_hash)
        )
        if existing is not None:
            user_ids[person.key] = existing
            report.existing.append(person.key)
            continue
        if person.username is not None:
            holder = await session.scalar(
                select(Profile.user_id).where(Profile.username == person.username)
            )
            if holder is not None:
                raise SeedRefused(
                    f"The username {person.username!r} belongs to a user the "
                    "seed didn't create. Start over with make infra-reset, then "
                    "make infra-up migrate seed."
                )

        account = await users_service.create_account(
            session, phone, settings, referral_code=person.referral_code
        )
        user, profile = account.user, account.profile
        user.gender = person.gender
        user.dob = person.dob
        user.role = person.role
        user.status = UserStatus.ACTIVE
        user.onboarding_step = person.step
        user.is_verified = person.verified
        user.pin_hash = (
            None if person.pin is None else await hash_pin(person.pin, settings)
        )
        user.created_at = now - timedelta(days=person.joined_days_ago)
        user_ids[person.key] = user.id

        area_id = area_ids[person.area] if person.area is not None else None
        location = None
        if area_id is not None and person.username is not None:
            metres, bearing = scatter(person.username)
            centroid = select(Area.centroid).where(Area.id == area_id)
            location = func.ST_Project(
                centroid.scalar_subquery(), metres, func.radians(bearing)
            )
        profile.first_name = person.first_name
        profile.username = person.username
        profile.about = person.about
        profile.hometown = person.hometown
        profile.city = AREA_CITY if area_id is not None else None
        profile.area_id = area_id
        profile.location = location
        profile.location_updated_at = None if location is None else now
        profile.seeking = person.seeking
        profile.is_hidden = person.is_hidden
        profile.hide_age = person.hide_age
        profile.hide_distance = person.hide_distance
        profile.show_kudos = person.show_kudos
        profile.show_gifts = person.show_gifts
        session.add_all(
            [
                ProfileInterest(user_id=user.id, interest_id=interest_ids[label])
                for label in person.interests
            ]
            + [
                ProfileIntent(user_id=user.id, intent_id=intent_ids[label])
                for label in person.intents
            ]
        )
        await session.flush()
        report.created.append(person.key)

    for swipe in swipes:
        result = await session.execute(
            insert(Swipe)
            .values(
                swiper_id=user_ids[swipe.swiper],
                target_id=user_ids[swipe.target],
                dir=swipe.dir,
            )
            .on_conflict_do_nothing(index_elements=["swiper_id", "target_id"])
            .returning(Swipe.swiper_id)
        )
        report.swipes_added += len(result.all())
    return report


def _require_catalogues(
    people: Sequence[Person], there: Mapping[str, KeysView[str]]
) -> None:
    wanted = {
        "interest": {label for p in people for label in p.interests},
        "intent": {label for p in people for label in p.intents},
        "area": {p.area for p in people if p.area is not None},
    }
    missing = sorted(
        f"{kind} {name!r}"
        for kind, names in wanted.items()
        for name in names - there[kind]
    )
    if missing:
        raise SeedRefused(
            f"The database's catalogues lack {', '.join(missing)}. Run make "
            "migrate first. If P-38 has replaced the areas, the seed's must move "
            f"too: they are {AREA_CITY}'s."
        )


# --- make seed -------------------------------------------------------------------


def summary(report: SeedReport) -> str:
    """What `make seed` prints. Never a phone number or the PIN (rule 15)."""
    lines = [
        (
            f"seed: {len(report.created)} people written, {len(report.existing)} "
            f"already there; {report.swipes_added} swipes added."
        ),
        (
            "  Sign in locally as test_man or test_woman, or the moderator: their "
            "numbers, and her PIN, are in api/seed/data.py. The seed never prints "
            "them."
        ),
        (
            "  Running it again changes nothing. To start over: make infra-reset, "
            "then make infra-up migrate seed."
        ),
    ]
    if report.existing:
        lines.append(
            "  Anyone already there was left as they are, even if seed/data.py "
            "changed since."
        )
    return "\n".join(lines) + "\n"


async def main(
    settings: Settings | None = None,
    *,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    """0 when seeded; 2 when a check refused, saying which on `err`."""
    try:
        settings = settings or get_settings()
        refuse_unless_local(settings)
        refuse_unless_loopback(settings.DATABASE_URL)
        check_people(PEOPLE, SWIPES, clock.today_ist())
        engine = build_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0)
        try:
            async with (
                AsyncSession(engine, expire_on_commit=False) as session,
                session.begin(),
            ):
                await require_local_marker(session)
                report = await write_seed(session, settings)
        finally:
            await engine.dispose()
    except SeedRefused as refusal:
        err.write(f"seed: refused. {refusal}\n")
        return 2
    out.write(summary(report))
    return 0
