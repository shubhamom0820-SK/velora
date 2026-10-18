"""The dev seed (T-1.15, D-064): where it refuses to run, what it writes, and
that a second run changes nothing.

`main()` is only ever run here down a path that refuses: run to the end, it
commits, and the test database would keep 23 users. The writes are tested
through `write_seed()` inside the `db` fixture's rolled-back transaction.
"""

from __future__ import annotations

import io
import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_ist
from app.core.config import Settings
from app.core.enums import (
    Gender,
    LedgerReason,
    OnboardingStep,
    PhotoKind,
    ReviewStatus,
    Role,
    Seeking,
    SwipeDirection,
)
from app.core.providers.storage import FakeStorage
from app.core.security import decrypt_phone, hash_phone, normalize_phone, verify_pin
from app.modules.admin.models import AuditLogEntry
from app.modules.admin.service import SYSTEM_USER_ID
from app.modules.matches.models import Match
from app.modules.notifications.models import NotificationPrefs
from app.modules.onboarding import repository as onboarding_repository
from app.modules.onboarding import rules as onboarding_rules
from app.modules.onboarding import service as onboarding_service
from app.modules.photos.models import Photo
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles import rules
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.swipes.models import Swipe
from app.modules.users.models import User
from app.modules.verification.models import Verification
from app.modules.wallet.models import LedgerEntry, Wallet
from seed import run
from seed.data import (
    LIKE,
    PASS,
    PEOPLE,
    PROTOTYPE,
    SWIPES,
    TEST_WOMAN_PIN,
    Person,
    SeedSwipe,
)
from seed.photos import dust
from seed.run import (
    AREA_CITY,
    LOCAL_DATABASE_MARKER,
    SCATTER_RADIUS_M,
    SeedRefused,
    check_people,
    refuse_unless_loopback,
    require_local_marker,
    scatter,
    summary,
    write_seed,
)
from tests.conftest import MakeUser, make_test_settings
from tests.infra import API_DIR, TEST_DATABASE_URL, requires_infra
from tests.keys import r2_settings, random_keys, vapid_settings

REPO = API_DIR.parent
BY_KEY = {person.key: person for person in PEOPLE}

# Nothing listens here, so a seed that got past its checks would fail with a
# connection error, never with the refusal these tests expect.
NOTHING_LISTENS = "postgresql+asyncpg://velora:velora@127.0.0.1:1/velora"


def deployed_settings(env: str) -> Settings:
    """Settings as staging or production must set them, so only `ENV` refuses."""
    return Settings(
        _env_file=None,
        ENV=env,
        DATABASE_URL=NOTHING_LISTENS,
        REDIS_URL="rediss://default:x@redis.example:6379/0",
        CLIENT_IP_HEADER="Caddy-Client-IP",
        AUTH_PHONE_PROVIDER="firebase",
        FIREBASE_PROJECT_ID="velora-test",
        SMS_PROVIDER="msg91",
        PAYMENTS_PROVIDER="razorpay",
        MODERATION_PROVIDER="sightengine",
        FACEMATCH_PROVIDER="sface",
        STORAGE_PROVIDER="s3",
        PUSH_PROVIDER="webpush",
        **vapid_settings(),  # type: ignore[arg-type]
        **r2_settings(),  # type: ignore[arg-type]
        **random_keys(),  # type: ignore[arg-type]
    )


async def run_main(settings: Settings) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = await run.main(settings, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def no_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if a refused run ever reaches the writes."""

    async def must_not_write(*_: Any, **__: Any) -> None:
        raise AssertionError("the seed reached its writes")

    monkeypatch.setattr(run, "write_seed", must_not_write)


# --- Where it refuses to run ---------------------------------------------------


@pytest.mark.critical
@pytest.mark.parametrize("env", ["staging", "production"])
async def test_staging_and_production_are_refused_before_connecting(
    env: str, no_writes: None
) -> None:
    code, out, err = await run_main(deployed_settings(env))
    assert code == 2
    assert err == (
        f"seed: refused. ENV={env}: the dev seed runs only where ENV is local "
        "(D-064). Its users are fake, and its phone numbers may be real people's.\n"
    )
    assert out == ""


@pytest.mark.critical
async def test_a_database_on_another_host_is_refused_even_locally(
    no_writes: None,
) -> None:
    settings = make_test_settings().model_copy(
        update={"DATABASE_URL": "postgresql+asyncpg://u:p@db.abc.supabase.co:5432/x"}
    )
    code, out, err = await run_main(settings)
    assert code == 2
    assert "DATABASE_URL points at 'db.abc.supabase.co'" in err
    assert ":p@" not in err  # never the password
    assert out == ""


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_this_machine_passes_the_host_check(host: str) -> None:
    refuse_unless_loopback(f"postgresql+asyncpg://u:p@{host}:5432/velora")


@pytest.mark.critical
@requires_infra
async def test_a_local_address_to_an_unstamped_database_is_refused(
    no_writes: None,
) -> None:
    """A tunnel's case: ENV is local and the host is loopback, but the database
    isn't the one `make infra-up` stamped. A test database is never stamped."""
    settings = make_test_settings()
    assert settings.DATABASE_URL == TEST_DATABASE_URL
    code, out, err = await run_main(settings)
    assert code == 2
    assert err.startswith(
        f"seed: refused. Database '{make_url(TEST_DATABASE_URL).database}' isn't "
        "stamped as the local "
        "stack's. If it is the local stack's, run make infra-up, which stamps it"
    )
    assert out == ""


async def test_the_marker_is_read_from_the_database_itself(db: AsyncSession) -> None:
    """Both ways, inside the test's transaction (a database comment rolls back)."""
    await db.execute(
        text("SELECT set_config('seed.marker', :m, true)").bindparams(
            m=LOCAL_DATABASE_MARKER
        )
    )
    stamp = (
        "DO $$ BEGIN EXECUTE format('COMMENT ON DATABASE %I IS %L', "
        "current_database(), current_setting('seed.marker')); END $$"
    )
    await db.execute(text(stamp))
    await require_local_marker(db)

    await db.execute(text("SELECT set_config('seed.marker', 'local-ish', true)"))
    await db.execute(text(stamp))
    with pytest.raises(SeedRefused, match="isn't stamped as the local stack's"):
        await require_local_marker(db)


def test_the_marker_is_what_make_infra_up_stamps() -> None:
    """Two copies of one string: if they drift, the seed refuses every local
    database, and someone 'fixes' it by loosening the check."""
    stamp = (REPO / "infra/postgres/stamp-local.sql").read_text()
    assert f"'{LOCAL_DATABASE_MARKER}'" in stamp
    makefile = (REPO / "Makefile").read_text()
    infra_up = makefile.split("\ninfra-up:", 1)[1].split("\n\n", 1)[0]
    assert "exec -T db" in infra_up
    assert "< infra/postgres/stamp-local.sql" in infra_up


# --- The data, against the rules -------------------------------------------------


def test_the_seed_data_keeps_every_rule() -> None:
    check_people(PEOPLE, SWIPES, today_ist())


def _with(key: str, **changes: Any) -> list[Person]:
    return [replace(p, **changes) if p.key == key else p for p in PEOPLE]


TODAY = date(2026, 10, 3)


@pytest.mark.parametrize(
    ("people", "swipes", "problem"),
    [
        (
            _with("dev", interests=("Startups", "Running", "Photography", "Reading")),
            SWIPES,
            "dev: exactly 5 different interests (T-3.8)",
        ),
        (
            _with("dev", interests=("Startups",) * 5),
            SWIPES,
            "dev: exactly 5 different interests (T-3.8)",
        ),
        (_with("dev", intents=()), SWIPES, "dev: 1 to 3 different intents (D-041)"),
        (
            _with("dev", intents=("Long term",) * 2),
            SWIPES,
            "dev: 1 to 3 different intents (D-041)",
        ),
        (
            _with(
                "dev",
                intents=("Long term", "Friendship", "Discreet", "Casual dating"),
            ),
            SWIPES,
            "dev: 1 to 3 different intents (D-041)",
        ),
        (
            _with("dev", dob=date(2008, 10, 4)),  # 18 tomorrow
            SWIPES,
            "dev: under 18 today in IST (D-009)",
        ),
        (
            _with("meera", verified=False),
            SWIPES,
            "meera: an onboarded woman is always verified (D-008)",
        ),
        (
            _with("dev", about="Find me at www.example.com, I'm on there daily."),
            SWIPES,
            "dev: about can't hold a link (T-3.7)",
        ),
        (
            _with("dev", about="Text me on 98765 43210 any time, I reply fast."),
            SWIPES,
            "dev: about can't hold a phone number (T-3.7)",
        ),
        (
            _with("dev", about="Too short to say anything about me at all"[:39]),
            SWIPES,
            "dev: about must be 40 to 300 characters (T-3.7)",
        ),
        (
            _with("dev", first_name="Dev2"),
            SWIPES,
            "dev: first_name may only hold letters, single spaces, and an apostrophe",
        ),
        (
            _with("dev", first_name="Dev "),
            SWIPES,
            "dev: first_name isn't as the API stores it, trimmed and in NFC",
        ),
        (
            _with("dev", username="Dev"),
            SWIPES,
            "dev: username must be 4 to 20 of a-z, 0-9, '.' and '_' (T-3.7)",
        ),
        (
            _with("dev", username="ad.min"),
            SWIPES,
            "dev: username is reserved (T-3.7)",
        ),
        (
            _with("dev", phone="+919800000112"),
            SWIPES,
            "dev: the phone must be in the seed's block, +9190000",
        ),
        (
            _with("dev", phone="+91 90000 00112"),
            SWIPES,
            "dev: write the phone as normalize_phone returns it",
        ),
        (
            _with("dev", phone="+915000000112"),
            SWIPES,
            "dev: normalize_phone refuses the phone (VALIDATION_ERROR)",
        ),
        (
            _with("dev", phone="+919000000101"),
            SWIPES,
            "the same phone twice: +919000000101",
        ),
        (
            _with("dev", username="ananya_d"),
            SWIPES,
            "the same username twice: ananya_d",
        ),
        (
            _with("test_woman", pin="1234"),
            SWIPES,
            "test_woman: the PIN is a straight run of digits (T-3.9)",
        ),
        (
            _with("test_woman", pin="7777"),
            SWIPES,
            "test_woman: the PIN is one digit four times (T-3.9)",
        ),
        (
            _with("test_woman", pin="2001"),
            SWIPES,
            "test_woman: the PIN is one of the most common PINs (T-3.9)",
        ),
        (
            _with("moderator", gender=Gender.MALE),
            SWIPES,
            "moderator: onboarding not started, so nothing it would ask for",
        ),
        (
            _with("test_woman", credits=5),
            SWIPES,
            "test_woman: only a man may hold credits (D-076)",
        ),
        (
            # No gender yet: the allowlist refuses her too (D-076).
            _with("moderator", credits=5),
            SWIPES,
            "moderator: only a man may hold credits (D-076)",
        ),
        (
            _with("test_man", credits=-60),
            SWIPES,
            "test_man: credits are granted, never taken: 0 or more",
        ),
        (
            PEOPLE,
            (*SWIPES, SeedSwipe("test_man", "ananya", LIKE)),
            "swipe test_man -> ananya: liked back, which would make a match",
        ),
        (
            PEOPLE,
            (*SWIPES, SeedSwipe("test_man", "diya", LIKE)),
            "swipe test_man -> diya: swiped twice; a swipe is written once",
        ),
        (
            PEOPLE,
            (*SWIPES, SeedSwipe("riya", "test_man", LIKE)),
            "swipe riya -> test_man: both must have finished onboarding",
        ),
        (
            PEOPLE,
            (*SWIPES, SeedSwipe("nobody", "test_man", LIKE)),
            "swipe nobody -> test_man: names someone who isn't in the seed",
        ),
        (
            _with("ishita", gradient=None),
            SWIPES,
            (
                "ishita: past the photos step, so needs a gradient: two #RRGGBB "
                "colours (T-4.4)"
            ),
        ),
        (
            _with("dev", gradient=("#C43450", "red")),
            SWIPES,
            (
                "dev: past the photos step, so needs a gradient: two #RRGGBB "
                "colours (T-4.4)"
            ),
        ),
        (
            _with("moderator", gradient=("#C43450", "#5A0E22")),
            SWIPES,
            "moderator: onboarding not started, so nothing it would ask for can be set",
        ),
    ],
)
def test_data_that_breaks_a_rule_is_refused(
    people: Sequence[Person], swipes: Sequence[SeedSwipe], problem: str
) -> None:
    with pytest.raises(SeedRefused) as refused:
        check_people(people, swipes, TODAY)
    assert f"  - {problem}" in str(refused.value)


def test_eighteen_today_is_old_enough() -> None:
    check_people(_with("dev", dob=date(2008, 10, 3)), SWIPES, TODAY)


def test_the_seed_holds_names_and_abouts_to_the_apis_own_rules() -> None:
    """T-3.7's rules, not an ASCII stand-in: a Gurmukhi name and a range of
    years pass, as they do through the API."""
    people = _with(
        "dev",
        first_name="ਗੁਰਪ੍ਰੀਤ",
        about="I lived in Delhi 2010-2015, then moved here for the food and stayed.",
    )
    check_people(people, SWIPES, TODAY)


def test_a_pass_back_on_a_like_makes_no_match_so_is_allowed() -> None:
    check_people(PEOPLE, (*SWIPES, SeedSwipe("test_man", "meera", PASS)), TODAY)


# --- What it writes ----------------------------------------------------------------


@pytest.fixture
async def seeded(db: AsyncSession) -> run.SeedReport:
    return await write_seed(db, make_test_settings())


async def _user(db: AsyncSession, phone: str) -> User:
    phone_hash = hash_phone(normalize_phone(phone), make_test_settings())
    user = await db.scalar(select(User).where(User.phone_hash == phone_hash))
    assert user is not None
    return user


async def _wallet(db: AsyncSession, person: Person) -> Wallet:
    wallet = await db.get(Wallet, (await _user(db, person.phone)).id)
    assert wallet is not None
    await db.refresh(wallet)
    return wallet


async def _seeded_ids(db: AsyncSession) -> list[UUID]:
    settings = make_test_settings()
    hashes = [hash_phone(normalize_phone(p.phone), settings) for p in PEOPLE]
    return list(await db.scalars(select(User.id).where(User.phone_hash.in_(hashes))))


async def _seeded_entries(db: AsyncSession) -> list[LedgerEntry]:
    """The seeded people's ledger rows, never the whole table's."""
    ids = await _seeded_ids(db)
    return list(
        await db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.user_id.in_(ids))
            .order_by(LedgerEntry.created_at)
        )
    )


async def test_everyone_is_written_with_the_rows_signup_creates(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    assert seeded.created == [p.key for p in PEOPLE]
    assert seeded.existing == []
    assert len(PEOPLE) == 23
    for person in PEOPLE:
        user = await _user(db, person.phone)
        assert await db.get(Profile, user.id) is not None
        assert await db.get(NotificationPrefs, user.id) is not None
        assert await db.get(Wallet, user.id) is not None


async def test_only_the_test_man_holds_credits_granted_once(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """His 60, through the wallet (rule 5), under the seed's own key. Scoped to
    the seeded people: other tests in the run commit ledger rows of their own."""
    test_man = await _user(db, BY_KEY["test_man"].phone)
    balances = {person.key: (await _wallet(db, person)).balance for person in PEOPLE}
    assert seeded.credited == ["test_man"]
    assert balances == {p.key: 60 if p.key == "test_man" else 0 for p in PEOPLE}
    assert [
        (e.user_id, e.reason, e.delta, e.balance_after, e.ref_type, e.idempotency_key)
        for e in await _seeded_entries(db)
    ] == [
        (
            test_man.id,
            LedgerReason.ADMIN_GRANT,
            60,
            60,
            "audit_log",
            f"{test_man.id}:admin_grant:dev-seed",
        )
    ]
    # The grant names the system user's audit row (D-905, D-923).
    [entry] = await _seeded_entries(db)
    audit = await db.get(AuditLogEntry, entry.ref_id)
    assert audit is not None
    assert (audit.actor_id, audit.action, audit.target_id, audit.meta) == (
        SYSTEM_USER_ID,
        "seed.grant",
        test_man.id,
        {"credits": 60},
    )
    assert "Credits granted to test_man." in summary(seeded)


async def test_the_test_man_is_found_as_login_will_find_him(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """Typed the way people type it, through normalize_phone and hash_phone."""
    user = await _user(db, "+91 90000 00001")
    assert user.phone_enc is not None
    assert decrypt_phone(user.phone_enc, make_test_settings()) == "+919000000001"
    profile = await db.get(Profile, user.id)
    assert profile is not None and profile.username == "test_man"
    assert user.onboarding_step is OnboardingStep.DONE
    assert user.gender is Gender.MALE and profile.seeking is Seeking.WOMEN


async def test_test_accounts_keep_readable_codes_and_profiles_get_generated_ones(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """T-3.3: the test accounts' fixed codes, everyone else's from signup."""
    fixed = {"test_man": "TESTMAN", "test_woman": "TESTWOMAN", "moderator": "MODERATOR"}
    generated = set()
    for person in PEOPLE:
        user = await _user(db, person.phone)
        if person.key in fixed:
            assert user.referral_code == fixed[person.key]
        else:
            assert re.fullmatch(
                r"[23456789ABCDEFGHJKMNPQRSTVWXYZ]{8}", user.referral_code
            )
            generated.add(user.referral_code)
    assert len(generated) == len(PEOPLE) - 3


async def test_only_the_test_woman_has_a_pin_and_it_verifies(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    settings = make_test_settings()
    woman = await _user(db, "+919000000002")
    assert woman.pin_hash is not None
    assert await verify_pin(TEST_WOMAN_PIN, woman.pin_hash, settings)
    assert not await verify_pin("0000", woman.pin_hash, settings)
    with_pins = await db.scalar(
        select(func.count()).select_from(User).where(User.pin_hash.is_not(None))
    )
    assert with_pins == 1


async def test_who_is_verified_and_who_is_still_onboarding(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """D-008 for onboarded women; three left at the selfie step for T-4.5."""
    at_selfie = set()
    for person in PEOPLE:
        user = await _user(db, person.phone)
        assert user.is_verified is person.verified
        if user.onboarding_step is OnboardingStep.SELFIE:
            at_selfie.add(person.key)
            assert not user.is_verified
        if user.gender is Gender.FEMALE and user.onboarding_step is OnboardingStep.DONE:
            assert user.is_verified
    assert at_selfie == {"ishita", "riya", "pooja"}
    verified = [p.key for p in PEOPLE if p.verified]
    assert len(verified) == 15  # 7 women, 7 men, the test woman: T-4.5's rows


async def test_every_finished_profile_could_have_finished(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """T-4.8's requirements, read as `POST /me/onboarding/complete` reads them,
    hold for everyone the seed leaves `done`, and their completeness is what
    finishing makes it (D-310): never signup's 0, which no finished profile
    has. One approved photo each, so 50 for all, until a seeded profile shows
    more."""
    finished = [p for p in PEOPLE if p.step is OnboardingStep.DONE]
    for person in finished:
        user = await _user(db, person.phone)
        profile = await onboarding_repository.profile_of(db, user.id)
        facts = await onboarding_service.facts_of(db, profile)
        assert onboarding_rules.missing(facts) == [], person.key
        assert user.is_verified or not onboarding_rules.needs_a_match(user.gender)
        assert profile.completeness == onboarding_rules.completeness(
            facts.approved_photos
        ), person.key
        assert profile.completeness == 50, person.key
    assert seeded.completeness_set == [p.key for p in finished]
    assert "Completeness set for 19 finished profiles (D-310)." in summary(seeded)


async def test_the_moderator_has_not_started_onboarding(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    user = await _user(db, "+919000000003")
    assert user.role is Role.MODERATOR
    assert user.onboarding_step is OnboardingStep.DOB
    assert user.gender is None and user.dob is None and user.pin_hash is None
    profile = await db.get(Profile, user.id)
    assert profile is not None
    assert (profile.first_name, profile.username, profile.location) == (None,) * 3


async def test_interests_and_intents_spread_as_the_rules_allow(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    intent_counts = []
    for person in [p for p in PEOPLE if p.step is not OnboardingStep.DOB]:
        user = await _user(db, person.phone)
        interests = await db.scalar(
            select(func.count()).where(ProfileInterest.user_id == user.id)
        )
        intents = await db.scalar(
            select(func.count()).where(ProfileIntent.user_id == user.id)
        )
        assert interests == 5
        assert intents is not None and 1 <= intents <= 3
        intent_counts.append(intents)
    # D-041's 1-3 and its any-overlap filter run on real variety.
    assert set(intent_counts) == {1, 2, 3}


def test_the_profile_flags_take_both_values() -> None:
    """A flag that's the same on all 20 is one the developer never sees work."""
    for flag in ("hide_age", "hide_distance", "is_hidden", "show_kudos", "show_gifts"):
        assert {getattr(p, flag) for p in PROTOTYPE} == {True, False}, flag


def test_the_scatter_is_fixed_by_the_username_and_inside_the_radius() -> None:
    assert scatter("ananya_d") == scatter("ananya_d")
    placed = [scatter(p.username) for p in PEOPLE if p.username is not None]
    assert all(0 <= metres <= SCATTER_RADIUS_M for metres, _ in placed)
    assert all(0 <= bearing < 360 for _, bearing in placed)
    assert len(set(placed)) == len(placed)


async def test_the_scatter_stays_under_half_the_closest_gap(db: AsyncSession) -> None:
    """Under half the gap between the two closest centroids, any point within
    the radius is nearer its own centroid than any other. Read from the
    database, so moving a centroid (P-38's are drafts) can't quietly break it."""
    closest = await db.scalar(
        text(
            "SELECT min(ST_Distance(a.centroid, b.centroid)) FROM areas a "
            "JOIN areas b ON a.id < b.id AND a.city = b.city WHERE a.city = :city"
        ),
        {"city": AREA_CITY},
    )

    assert closest is not None
    assert SCATTER_RADIUS_M < closest / 2, (
        f"{AREA_CITY}'s two closest centroids are {closest:.0f} m apart; "
        f"SCATTER_RADIUS_M must stay under {closest / 2:.0f} m"
    )


# Where `scatter` put each seeded profile's shared position, exactly: the point
# its area is found from (D-220), before the grid (D-490).
_SHARED = (
    "ST_Project(a.centroid, CAST(:metres AS float8), radians(CAST(:bearing AS float8)))"
)


async def test_each_profile_sits_on_its_scatters_grid_point_inside_its_area(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """Stored at the grid point of where `scatter` says (D-490), and that
    shared position nearer its own area's centroid than any other area's:
    inside the area, as far as centroids can say."""
    rows = (
        await db.execute(
            text(
                "SELECT pr.username, pr.area_id FROM profiles pr "
                "WHERE pr.area_id IS NOT NULL"
            )
        )
    ).all()
    assert len(rows) == 22  # everyone but the moderator
    for username, area_id in rows:
        metres, bearing = scatter(username)
        on_grid, nearest_is_own = (
            await db.execute(
                text(
                    f"SELECT ST_Equals(pr.location::geometry, ST_SnapToGrid("
                    f"{_SHARED}::geometry, CAST(:grid AS float8))), "
                    f"(SELECT o.id FROM areas o WHERE o.city = a.city "
                    f" ORDER BY o.centroid <-> {_SHARED} LIMIT 1) = a.id "
                    f"FROM profiles pr JOIN areas a ON a.id = pr.area_id "
                    f"WHERE pr.username = :username"
                ),
                {
                    "metres": metres,
                    "bearing": bearing,
                    "grid": rules.GRID_DEG,
                    "username": username,
                },
            )
        ).one()
        assert on_grid, username
        assert nearest_is_own, username
        assert area_id is not None


async def test_each_profile_has_the_area_its_position_would_get_if_shared(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """As if it had shared its position (T-4.10): the area `PUT /me/location`
    would give that position, by the API's own rule and query (D-220), is
    the one the seed wrote; and the time is written with it, so `Me` reads
    the location as set."""
    rows = (
        await db.execute(
            text(
                "SELECT username, area_id, location_updated_at FROM profiles "
                "WHERE location IS NOT NULL"
            )
        )
    ).all()
    assert len(rows) == 22  # everyone but the moderator
    for username, area_id, updated_at in rows:
        metres, bearing = scatter(username)
        lat, lng = (
            await db.execute(
                text(
                    f"SELECT ST_Y(p::geometry), ST_X(p::geometry) FROM ("
                    f"SELECT {_SHARED} AS p FROM areas a WHERE a.id = :area) AS t"
                ),
                {"metres": metres, "bearing": bearing, "area": area_id},
            )
        ).one()
        assert rules.position_problems(lat, lng) == {}, username
        shared = await profiles_repository.nearest_area_id(
            db, lat, lng, within_m=rules.AREA_WITHIN_M
        )
        assert (shared, updated_at is not None) == (area_id, True), username


async def test_the_grid_puts_some_on_one_point_and_spreads_the_rest(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """On the grid (D-490) several profiles share a point, so the 1 km floor
    shows (D-034), and the rest spread over several kilometres, so distance
    sorting has a range to show."""
    points, shared, farthest = (
        await db.execute(
            text(
                "SELECT count(DISTINCT ST_AsText(location)), "
                "count(*) - count(DISTINCT ST_AsText(location)), "
                "(SELECT max(ST_Distance(a.location, b.location)) FROM profiles a "
                " JOIN profiles b ON a.user_id < b.user_id "
                " WHERE a.location IS NOT NULL AND b.location IS NOT NULL) "
                "FROM profiles WHERE location IS NOT NULL"
            )
        )
    ).one()
    assert points >= 5
    assert shared >= 1
    assert farthest > 3000


async def test_the_swipes_are_written_and_make_no_match(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    ids = {p.key: (await _user(db, p.phone)).id for p in PEOPLE}
    written = {
        (s.swiper_id, s.target_id, s.dir) for s in await db.scalars(select(Swipe))
    }
    assert written == {(ids[s.swiper], ids[s.target], s.dir) for s in SWIPES}
    assert seeded.swipes_added == 8
    directions = [s.dir for s in SWIPES]
    assert directions.count(SwipeDirection.PASS) == 3
    assert directions.count(SwipeDirection.SUPER) == 1
    assert await db.scalar(select(func.count()).select_from(Match)) == 0


async def test_joined_sets_when_they_signed_up(db: AsyncSession, clock: Any) -> None:
    frozen = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    clock.freeze(frozen)
    await write_seed(db, make_test_settings())
    for person in PEOPLE:
        user = await _user(db, person.phone)
        assert user.created_at == frozen - timedelta(days=person.joined_days_ago)


# --- Twice, and what it refuses mid-way ---------------------------------------------


_COUNTED = (
    User,
    Profile,
    Wallet,
    NotificationPrefs,
    ProfileInterest,
    ProfileIntent,
    Photo,
)


async def _counts(db: AsyncSession) -> list[int | None]:
    ids = await _seeded_ids(db)
    return [
        *[
            await db.scalar(select(func.count()).select_from(model))
            for model in (*_COUNTED, Swipe)
        ],
        # The ledger, and the balances, scoped to the seeded people.
        await db.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.user_id.in_(ids))
        ),
        await db.scalar(
            select(func.sum(Wallet.balance)).where(Wallet.user_id.in_(ids))
        ),
    ]


async def test_a_second_run_changes_nothing(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    before = await _counts(db)
    again = await write_seed(db, make_test_settings())
    assert await _counts(db) == before
    assert again.created == []
    assert again.existing == [p.key for p in PEOPLE]
    assert again.swipes_added == 0
    assert again.completeness_set == []
    assert (again.credited, again.already_credited) == ([], ["test_man"])
    assert "Anyone already there was left as they are" in summary(again)
    assert "(test_man had them already)" in summary(again)


async def test_credits_reach_a_test_man_already_there(db: AsyncSession) -> None:
    """The one exception to insert-only: a test man written before credits
    existed still gets his 60, once."""
    before_credits = _with("test_man", credits=0)
    first = await write_seed(db, make_test_settings(), people=before_credits)
    assert first.credited == []
    assert (await _wallet(db, BY_KEY["test_man"])).balance == 0

    second = await write_seed(db, make_test_settings())

    assert second.created == [] and "test_man" in second.existing
    assert second.credited == ["test_man"]
    assert (await _wallet(db, BY_KEY["test_man"])).balance == 60
    assert len(await _seeded_entries(db)) == 1


async def test_a_grant_is_never_changed_by_a_later_seed(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    with pytest.raises(SeedRefused) as refused:
        await write_seed(db, make_test_settings(), people=_with("test_man", credits=70))

    assert str(refused.value).startswith(
        "test_man's credits were refused: an earlier seed granted 60, not 70."
    )
    assert "make infra-reset" in str(refused.value)


async def test_an_earlier_seeds_grant_with_no_ref_is_left_as_it_is(
    db: AsyncSession,
) -> None:
    """A dev database seeded before T-9.5 holds a grant naming no audit row,
    which the ledger keeps (T-1.12). Seeding again reads it and writes
    nothing, so no infra-reset is needed (the founder, 16 October 2026; D-923).
    The old row is made as the old rule allowed, inside the test's
    transaction, which rolls the rule back with it."""
    first = await write_seed(
        db, make_test_settings(), people=_with("test_man", credits=0)
    )
    assert first.credited == []
    test_man = await _user(db, BY_KEY["test_man"].phone)
    await db.execute(
        text(
            "alter table ledger_entries drop constraint ck_ledger_entries_ref_required"
        )
    )
    await db.execute(
        text(
            "insert into ledger_entries (user_id, delta, balance_after, reason, "
            "idempotency_key) values (:u, 60, 60, 'admin_grant', :k)"
        ),
        {"u": test_man.id, "k": f"{test_man.id}:admin_grant:dev-seed"},
    )
    await db.execute(
        text("update wallets set balance = 60 where user_id = :u"), {"u": test_man.id}
    )
    audits_before = await db.scalar(select(func.count()).select_from(AuditLogEntry))

    again = await write_seed(db, make_test_settings())

    assert again.credited == [] and again.already_credited == ["test_man"]
    assert [(e.ref_type, e.ref_id) for e in await _seeded_entries(db)] == [(None, None)]
    assert (
        await db.scalar(select(func.count()).select_from(AuditLogEntry))
        == audits_before
    )


async def test_a_username_someone_else_holds_is_refused(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    profile = await db.get(Profile, user.id)
    assert profile is not None
    profile.username = "ananya_d"
    await db.flush()
    with pytest.raises(SeedRefused, match="'ananya_d' belongs to a user the seed"):
        await write_seed(db, make_test_settings())


async def test_a_label_missing_from_the_catalogue_is_refused(db: AsyncSession) -> None:
    kavya = replace(
        BY_KEY["kavya"],
        interests=("Carnatic", "Running", "Photography", "Yoga", "Filter coffee"),
    )
    with pytest.raises(SeedRefused, match="catalogues lack interest 'Carnatic'"):
        await write_seed(db, make_test_settings(), people=[kavya], swipes=[])


# --- Rule 15 --------------------------------------------------------------------------

# The output's log lines carry timestamps and ids, whose digits can spell a four-digit
# PIN by chance: CI's run 37206663207 failed on `13:45:58.482903Z`, which holds 4829.
# The PIN counts only as a number of its own, and timestamps and ids go before looking,
# since either can hold one (a fraction `.4829`, a segment `-4829-`). So the check fails
# on a printed PIN and never on a coincidence.
ISO_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
UUID_TEXT = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


def prints_pin(printed: str, pin: str) -> bool:
    text = UUID_TEXT.sub(" ", ISO_TIMESTAMP.sub(" ", printed))
    return re.search(rf"(?<!\d){re.escape(pin)}(?!\d)", text) is not None


@pytest.mark.parametrize(
    "line",
    [
        # The line CI failed on, as structlog's console renderer drew it.
        (
            "\x1b[2m2026-10-04T13:45:58.482903Z\x1b[0m [\x1b[32m\x1b[1minfo     \x1b[0m] "
            "\x1b[1mwallet.repeated\x1b[0m \x1b[36muser_id\x1b[0m=\x1b[35m"
            "f4f718db-9e82-4bf4-9688-00d665493f95\x1b[0m"
        ),
        "user_id=f4f718db-9e82-4829-9688-00d665493f95",
        "2026-10-04T13:45:58.104829+05:30 seed done",
        # A fraction of four digits is a number of its own: only the strip removes it.
        "2026-10-04T13:45:58.4829Z seed done",
    ],
)
def test_the_pin_check_ignores_the_pin_inside_a_timestamp_or_an_id(line: str) -> None:
    assert not prints_pin(line, "4829")


@pytest.mark.parametrize(
    "line",
    [
        "pin=4829",
        "test_woman's PIN is 4829.",
        "\x1b[36mpin\x1b[0m=\x1b[35m4829\x1b[0m",
        "2026-10-04T13:45:58.482903Z seeded, pin 4829",
    ],
)
def test_the_pin_check_catches_a_printed_pin(line: str) -> None:
    assert prints_pin(line, "4829")


async def test_the_output_never_has_a_phone_number_or_the_pin(
    db: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    first = await write_seed(db, make_test_settings())
    second = await write_seed(db, make_test_settings())
    captured = capsys.readouterr()
    printed = summary(first) + summary(second) + captured.out + captured.err
    digits = re.sub(r"\D", "", printed)
    for person in PEOPLE:
        national = person.phone.removeprefix("+91")
        assert national not in digits, person.key
    assert not prints_pin(printed, TEST_WOMAN_PIN)


# --- Placeholder photos (T-4.4) ------------------------------------------------------

PUBLIC, PRIVATE = "velora-public", "velora-private"


async def _photos_of(
    db: AsyncSession, person: Person, kind: PhotoKind = PhotoKind.PUBLIC
) -> list[Photo]:
    user = await _user(db, person.phone)
    return list(
        await db.scalars(
            select(Photo).where(Photo.user_id == user.id, Photo.kind == kind)
        )
    )


async def test_everyone_past_the_photos_step_has_an_approved_photo_at_place_0(
    db: AsyncSession,
) -> None:
    """Everyone but the moderator, the three women at the selfie step included;
    each stored in both buckets as moderation leaves an approved photo."""
    storage = FakeStorage()

    report = await write_seed(db, make_test_settings(), storage=storage)

    past = [p.key for p in PEOPLE if run.past_photos(p.step)]
    assert report.photos_added == past
    assert len(past) == 22 and "moderator" not in past
    assert {"ishita", "riya", "pooja"} <= set(past)
    assert await _photos_of(db, BY_KEY["moderator"]) == []
    for key in past:
        [photo] = await _photos_of(db, BY_KEY[key])
        assert (photo.kind, photo.position, photo.status) == (
            PhotoKind.PUBLIC,
            0,
            ReviewStatus.APPROVED,
        )
        assert photo.raw_key == f"raw/{photo.user_id}/{photo.id}"
        assert photo.public_key == f"p/{photo.id}.jpg"
        assert (photo.width, photo.height) == (900, 1200)
        private = storage.objects[(PRIVATE, photo.raw_key)]
        assert storage.objects[(PUBLIC, photo.public_key)] == private
        assert private.content_type == "image/jpeg"
        # Re-encoded like any upload: a JPEG with nothing before its pixels
        # but JFIF, its tables and its frame.
        header = private.data[: private.data.index(b"\xff\xda")]
        assert b"JFIF" in header and b"Exif" not in header
    public = [key for bucket, key in storage.objects if bucket == PUBLIC]
    assert len(public) == len(past)


async def test_each_photo_is_its_profiles_prototype_gradient(db: AsyncSession) -> None:
    """The bottom-right corner is far from both glows: the second colour,
    dusted as the prototype dusts it."""
    storage = FakeStorage()
    await write_seed(db, make_test_settings(), storage=storage)

    for key in ("ananya", "yash", "test_man"):
        [photo] = await _photos_of(db, BY_KEY[key])
        gradient = BY_KEY[key].gradient
        assert gradient is not None
        with Image.open(
            io.BytesIO(storage.objects[(PUBLIC, f"p/{photo.id}.jpg")].data)
        ) as image:
            corner = image.convert("RGB").getpixel((895, 1195))
        assert isinstance(corner, tuple)
        expected = dust(gradient[1])
        assert all(abs(a - b) <= 6 for a, b in zip(corner, expected, strict=True))


async def test_a_second_run_adds_no_photo(db: AsyncSession) -> None:
    storage = FakeStorage()
    await write_seed(db, make_test_settings(), storage=storage)
    before = dict(storage.objects)

    again = await write_seed(db, make_test_settings(), storage=storage)

    assert (
        again.photos_added,
        again.verifications_added,
        again.face_photos_added,
        again.badges_set,
    ) == ([], [], [], [])
    assert storage.objects == before
    for person in PEOPLE:
        assert len(await _photos_of(db, person)) == (1 if person.gradient else 0)
        assert len(await _photos_of(db, person, PhotoKind.SELFIE)) == (
            1 if person.verified else 0
        )
        assert len(await _photos_of(db, person, PhotoKind.VERIFICATION)) == (
            1 if run.has_face_photo(person) else 0
        )


async def test_someone_seeded_before_photos_gets_one_once(db: AsyncSession) -> None:
    """The other exception to insert-only: a seed from before T-4.4 left
    people with no photo; the next run adds one each, once."""
    before_photos = [replace(p, gradient=None) for p in PEOPLE]
    first = await write_seed(db, make_test_settings(), people=before_photos)
    assert first.photos_added == []

    second = await write_seed(db, make_test_settings())

    assert second.created == []
    assert len(second.photos_added) == 22
    assert len(second.verifications_added) == 15
    assert len(second.face_photos_added) == 18
    assert len(second.badges_set) == 15
    assert "Placeholder photos added for 22 people." in summary(second)
    assert "Placeholder selfies, approved, added for 15 people." in summary(second)
    assert "Placeholder face photos, private, added for 18 people." in summary(second)
    assert "The badge's record set, on the seed's word, for 15 verified" in summary(
        second
    )


# --- Placeholder selfies (T-4.5) -----------------------------------------------------


async def test_everyone_marked_verified_has_an_approved_selfie_never_compared(
    db: AsyncSession,
) -> None:
    """15: the test woman and the prototype's 14 `v` profiles, 7 women and 7
    men. Ishita, Riya and Pooja, at the selfie step, have none: they are who
    T-4.5 verifies. Each selfie is private only, and its record says the seed
    put it there, never that a face was compared (D-263)."""
    storage = FakeStorage()

    report = await write_seed(db, make_test_settings(), storage=storage)

    verified = [p.key for p in PEOPLE if p.verified]
    assert report.verifications_added == verified
    assert len(verified) == 15
    women = [k for k in verified if BY_KEY[k].gender is Gender.FEMALE]
    assert (len(women), "test_woman" in women) == (8, True)
    for key in ("ishita", "riya", "pooja", "moderator"):
        user = await _user(db, BY_KEY[key].phone)
        assert (
            await db.scalar(select(func.count()).where(Verification.user_id == user.id))
            == 0
        )
    for key in verified:
        user = await _user(db, BY_KEY[key].phone)
        [verification] = list(
            await db.scalars(
                select(Verification).where(Verification.user_id == user.id)
            )
        )
        [selfie] = await _photos_of(db, BY_KEY[key], PhotoKind.SELFIE)
        assert (verification.status, verification.challenge) == (
            ReviewStatus.APPROVED,
            "none",
        )
        assert (verification.selfie_photo_id, verification.similarity) == (
            selfie.id,
            None,
        )
        assert (selfie.status, selfie.public_key, selfie.moderation) == (
            ReviewStatus.APPROVED,
            None,
            {"decided_by": "seed"},
        )
        assert user.is_verified
        assert (PRIVATE, selfie.raw_key) in storage.objects
        assert not any(
            k.endswith(str(selfie.id)) for b, k in storage.objects if b == PUBLIC
        )


# --- Placeholder face photos and the badge's record (T-4.12) ----------------------------


async def test_the_verified_and_the_selfie_step_women_have_a_private_face_photo(
    db: AsyncSession,
) -> None:
    """18: the 15 marked verified, whose selfie is recorded as matched against
    it, and Ishita, Riya and Pooja, who verify against it from the selfie step
    (D-391). Each is approved by the seed's word, in the private bucket only,
    with no public copy, and the gradient turned round as the selfie is."""
    storage = FakeStorage()

    report = await write_seed(db, make_test_settings(), storage=storage)

    with_one = [p.key for p in PEOPLE if run.has_face_photo(p)]
    assert report.face_photos_added == with_one
    assert len(with_one) == 18
    assert {"ishita", "riya", "pooja"} <= set(with_one)
    assert all(
        BY_KEY[k].verified for k in with_one if k not in {"ishita", "riya", "pooja"}
    )
    for person in PEOPLE:
        faces = await _photos_of(db, person, PhotoKind.VERIFICATION)
        if person.key not in with_one:
            assert faces == []
            continue
        [face] = faces
        assert (face.status, face.public_key, face.moderation) == (
            ReviewStatus.APPROVED,
            None,
            {"decided_by": "seed"},
        )
        assert face.raw_key == f"raw/{face.user_id}/{face.id}"
        assert (PRIVATE, face.raw_key) in storage.objects
        assert not any(
            k.endswith(str(face.id)) for b, k in storage.objects if b == PUBLIC
        )


async def test_the_badges_record_is_the_seeds_word_on_the_verified_ones_photos(
    db: AsyncSession,
) -> None:
    """D-393, in dev: the 15 verified profiles' public photos say their face
    matched the selfie on the seed's word, with no number and no face claimed
    (the founder, 8 October 2026), so the badge shows on their cards; nobody
    else's photo says anything about a match."""
    from app.modules.verification import repository as verification_repository

    report = await write_seed(db, make_test_settings())

    verified = [p.key for p in PEOPLE if p.verified]
    assert report.badges_set == verified
    for person in PEOPLE:
        user = await _user(db, person.phone)
        shown = await _photos_of(db, person)
        record = shown[0].moderation if shown else None
        if person.verified:
            assert record == {
                "decided_by": "seed",
                "selfie_match": {"matched": True, "decided_by": "seed"},
            }
            assert "faces" not in record
            assert await verification_repository.shows_badge(db, user.id)
        else:
            assert record is None
            assert not await verification_repository.shows_badge(db, user.id)


async def test_a_place_0_that_already_holds_a_live_photo_gets_none(
    db: AsyncSession,
) -> None:
    """Someone who uploaded their own: the seed never puts one beside it."""
    await write_seed(db, make_test_settings(), people=_with("test_man", gradient=None))
    man = await _user(db, BY_KEY["test_man"].phone)
    photo_id = uuid4()
    db.add(
        Photo(
            id=photo_id,
            user_id=man.id,
            kind=PhotoKind.PUBLIC,
            position=0,
            raw_key=f"raw/{man.id}/{photo_id}",
        )
    )
    await db.flush()

    again = await write_seed(db, make_test_settings())

    assert "test_man" not in again.photos_added
    assert [p.id for p in await _photos_of(db, BY_KEY["test_man"])] == [photo_id]
