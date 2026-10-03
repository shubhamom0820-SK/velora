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

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_ist
from app.core.config import Settings
from app.core.enums import Gender, OnboardingStep, Role, Seeking, SwipeDirection
from app.core.security import decrypt_phone, hash_phone, normalize_phone, verify_pin
from app.modules.matches.models import Match
from app.modules.notifications.models import NotificationPrefs
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.swipes.models import Swipe
from app.modules.users.models import User
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
from seed.run import (
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
from tests.keys import random_keys

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
        CLIENT_IP_HEADER="Fly-Client-IP",
        AUTH_PHONE_PROVIDER="firebase",
        SMS_PROVIDER="msg91",
        PAYMENTS_PROVIDER="razorpay",
        MODERATION_PROVIDER="sightengine",
        FACEMATCH_PROVIDER="rekognition",
        STORAGE_PROVIDER="s3",
        PUSH_PROVIDER="webpush",
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
    isn't the one `make infra-up` stamped. velora_test is never stamped."""
    settings = make_test_settings()
    assert settings.DATABASE_URL == TEST_DATABASE_URL
    code, out, err = await run_main(settings)
    assert code == 2
    assert err.startswith(
        "seed: refused. Database 'velora_test' isn't stamped as the local "
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
        wallet = await db.get(Wallet, user.id)
        assert wallet is not None and wallet.balance == 0  # rule 5: T-5.1
    assert await db.scalar(select(func.count()).select_from(LedgerEntry)) == 0


async def test_the_test_man_is_found_as_login_will_find_him(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """Typed the way people type it, through normalize_phone and hash_phone."""
    user = await _user(db, "+91 90000 00001")
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


async def test_each_profile_sits_at_its_scatter_inside_its_area(
    db: AsyncSession, seeded: run.SeedReport
) -> None:
    """Exactly where `scatter` says, and nearer its own area's centroid than
    any other area's: inside the area, as far as centroids can say."""
    rows = (
        await db.execute(
            text(
                "SELECT pr.username, ST_Distance(a.centroid, pr.location), "
                "degrees(ST_Azimuth(a.centroid, pr.location)), "
                "(SELECT o.id FROM areas o WHERE o.city = a.city "
                " ORDER BY o.centroid <-> pr.location LIMIT 1) = a.id "
                "FROM profiles pr JOIN areas a ON a.id = pr.area_id"
            )
        )
    ).all()
    assert len(rows) == 22  # everyone but the moderator
    for username, metres, bearing, nearest_is_own in rows:
        expected_metres, expected_bearing = scatter(username)
        assert metres == pytest.approx(expected_metres, abs=0.001), username
        assert bearing == pytest.approx(expected_bearing, abs=1e-6), username
        assert nearest_is_own, username


async def test_nobody_shares_a_spot(db: AsyncSession, seeded: run.SeedReport) -> None:
    """The point of the scatter: no two profiles 0 m apart, so distance sorting
    has a spread to show."""
    closest = await db.scalar(
        text(
            "SELECT min(ST_Distance(a.location, b.location)) FROM profiles a "
            "JOIN profiles b ON a.user_id < b.user_id "
            "WHERE a.location IS NOT NULL AND b.location IS NOT NULL"
        )
    )
    assert closest is not None and closest > 100


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


_COUNTED = (User, Profile, Wallet, NotificationPrefs, ProfileInterest, ProfileIntent)


async def _counts(db: AsyncSession) -> list[int | None]:
    return [
        await db.scalar(select(func.count()).select_from(model))
        for model in (*_COUNTED, Swipe, LedgerEntry)
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
    assert "Anyone already there was left as they are" in summary(again)


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
    assert TEST_WOMAN_PIN not in printed
