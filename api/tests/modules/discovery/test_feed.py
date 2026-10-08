"""`GET /v1/discover` (T-6.2): who is in a feed and in what order. Everyone
02-ARCHITECTURE §8 leaves out stays out, each on its own; both sides must want
the other; the radius is `app_config`'s, between grid points (D-490); the
filters (D-041's any overlap, D-393's badge) and the three feeds; and the
ranking, D-491's formula exactly."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import ModuleType

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FraudBand, Gender, OnboardingStep, Seeking, UserStatus
from app.modules.discovery import rules
from app.modules.discovery.service import FEED_CURSOR
from app.modules.profiles.models import ProfileIntent
from tests.conftest import MakeUser
from tests.modules.discovery.support import (
    HERE,
    banded,
    bearer,
    block,
    discover,
    error,
    ids,
    north,
    person,
    photo,
    swipe,
)

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)


# --- Who is left out ------------------------------------------------------------------


async def test_a_man_sees_the_women_nearby_who_want_men(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    wants_men, _ = await person(db, make_user, at=north(1))
    wants_anyone, _ = await person(db, make_user, at=north(2), seeking=Seeking.EVERYONE)
    await person(db, make_user, at=north(3), seeking=Seeking.WOMEN)
    await person(db, make_user, Gender.MALE, at=north(4), seeking=Seeking.EVERYONE)

    assert await ids(client, token) == [str(wants_men.id), str(wants_anyone.id)]


async def test_someone_seeking_everyone_sees_both_who_want_them_and_never_themselves(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE, seeking=Seeking.EVERYONE)
    woman, _ = await person(db, make_user, at=north(1))
    man, _ = await person(db, make_user, Gender.MALE, at=north(2), seeking=Seeking.MEN)
    await person(db, make_user, Gender.MALE, at=north(3), seeking=Seeking.WOMEN)

    found = await ids(client, token)

    assert found == [str(woman.id), str(man.id)]
    assert str(me.id) not in found


@pytest.mark.parametrize("direction", ["like", "pass", "super"])
async def test_someone_i_swiped_is_gone_whichever_way(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, direction: str
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    swiped, _ = await person(db, make_user, at=north(1))
    kept, _ = await person(db, make_user, at=north(2))
    await swipe(db, me, swiped, direction)

    assert await ids(client, token) == [str(kept.id)]


async def test_her_swipe_on_me_leaves_her_in_my_feed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "like")

    assert await ids(client, token) == [str(her.id)]


@pytest.mark.parametrize("who_blocked", ["me", "her"])
async def test_a_block_either_way_hides_each_from_the_other(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, who_blocked: str
) -> None:
    """06-TESTING's critical 9, for the feed: in both directions at once."""
    me, mine = await person(db, make_user, Gender.MALE)
    her, hers = await person(db, make_user, at=north(1))
    kept, _ = await person(db, make_user, at=north(2))
    await person(db, make_user, Gender.MALE, at=north(3))
    if who_blocked == "me":
        await block(db, me, her)
    else:
        await block(db, her, me)

    assert await ids(client, mine) == [str(kept.id)]
    assert str(me.id) not in await ids(client, hers)


async def test_a_hidden_profile_is_left_out(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    await person(db, make_user, at=north(1), is_hidden=True)
    kept, _ = await person(db, make_user, at=north(2))

    assert await ids(client, token) == [str(kept.id)]


@pytest.mark.parametrize(
    "step", [s for s in OnboardingStep if s is not OnboardingStep.DONE]
)
async def test_someone_not_done_is_left_out(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    """Everything else about her would show her: only the step differs."""
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    kept, _ = await person(db, make_user, at=north(2))
    her.onboarding_step = step
    await db.flush()

    assert await ids(client, token) == [str(kept.id)]


@pytest.mark.parametrize(
    "status", [s for s in UserStatus if s is not UserStatus.ACTIVE]
)
async def test_anyone_not_active_is_left_out(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, status: UserStatus
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    kept, _ = await person(db, make_user, at=north(2))
    her.status = status
    await db.flush()

    assert await ids(client, token) == [str(kept.id)]


@pytest.mark.parametrize("viewer_band", [None, FraudBand.MONITOR, FraudBand.SHADOW])
async def test_a_frozen_band_is_left_out_for_everyone(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    viewer_band: FraudBand | None,
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    if viewer_band is not None:
        await banded(db, me, viewer_band)
    frozen, _ = await person(db, make_user, at=north(1))
    kept, _ = await person(db, make_user, at=north(2))
    await banded(db, frozen, FraudBand.FREEZE)

    assert await ids(client, token) == [str(kept.id)]


@pytest.mark.parametrize(
    ("viewer_band", "sees_shadowed"),
    [
        (None, False),
        (FraudBand.NORMAL, False),
        (FraudBand.MONITOR, False),
        (FraudBand.SHADOW, True),
    ],
)
async def test_the_shadowed_are_shown_only_to_the_shadowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    viewer_band: FraudBand | None,
    sees_shadowed: bool,
) -> None:
    """D-031: `shadow` limits whom they reach, never whom they see; `monitor`
    and `normal` reach everyone."""
    me, token = await person(db, make_user, Gender.MALE)
    if viewer_band is not None:
        await banded(db, me, viewer_band)
    shadowed, _ = await person(db, make_user, at=north(1))
    watched, _ = await person(db, make_user, at=north(2))
    scored, _ = await person(db, make_user, at=north(3))
    await banded(db, shadowed, FraudBand.SHADOW)
    await banded(db, watched, FraudBand.MONITOR)
    await banded(db, scored, FraudBand.NORMAL)

    expected = [watched.id, scored.id]
    if sees_shadowed:
        expected.insert(0, shadowed.id)
    assert await ids(client, token) == [str(i) for i in expected]


# --- The radius -------------------------------------------------------------------


async def test_the_radius_is_25_km_between_grid_points(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """22 grid steps north is about 24.5 km, 23 about 25.6 km."""
    _, token = await person(db, make_user, Gender.MALE)
    inside, _ = await person(db, make_user, at=north(22))
    await person(db, make_user, at=north(23))
    metres = await db.scalar(
        text(
            "SELECT ST_Distance(ST_SetSRID(ST_MakePoint(:lng, :a), 4326)::geography,"
            " ST_SetSRID(ST_MakePoint(:lng, :b), 4326)::geography)"
        ),
        {"lng": HERE[1], "a": HERE[0], "b": north(23)[0]},
    )
    assert metres is not None and 25_000 < metres < 26_000

    assert await ids(client, token) == [str(inside.id)]


async def test_the_radius_is_read_from_app_config_within_a_minute(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """Cached 60 s per app (P-47): a change reaches the feed once that runs out."""
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    near, _ = await person(db, make_user, at=north(4))
    far, _ = await person(db, make_user, at=north(6))
    assert await ids(client, token) == [str(near.id), str(far.id)]

    await db.execute(
        text("UPDATE app_config SET value = '5' WHERE key = 'discovery_radius_km'")
    )
    clock.advance(timedelta(seconds=59))
    assert await ids(client, token) == [str(near.id), str(far.id)]
    clock.advance(timedelta(seconds=1))

    assert await ids(client, token) == [str(near.id)]


# --- Filters ------------------------------------------------------------------------


async def _intents(db: AsyncSession, user_id: object, *intent_ids: int) -> None:
    for intent_id in intent_ids:
        db.add(ProfileIntent(user_id=user_id, intent_id=intent_id))
    await db.flush()


async def test_intents_match_on_any_overlap(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-041: ticking two means either is fine."""
    _, token = await person(db, make_user, Gender.MALE)
    both, _ = await person(db, make_user, at=north(1))
    one, _ = await person(db, make_user, at=north(2))
    other, _ = await person(db, make_user, at=north(3))
    await person(db, make_user, at=north(4))
    await _intents(db, both.id, 1, 2)
    await _intents(db, one.id, 2)
    await _intents(db, other.id, 5)

    assert await ids(client, token, intent_ids=[1, 2]) == [str(both.id), str(one.id)]
    assert await ids(client, token, intent_ids=[2, 5]) == [
        str(both.id),
        str(one.id),
        str(other.id),
    ]
    assert await ids(client, token, intent_ids=[9]) == []


@pytest.mark.parametrize("intent_ids", [[11], [0], [-1], ["one"], list(range(1, 12))])
async def test_an_intent_that_isnt_one_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, intent_ids: list[object]
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await discover(client, token, intent_ids=intent_ids)

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_the_verified_filter_is_the_badge_never_is_verified_alone(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-393: every onboarded woman is verified (D-008), so `is_verified`
    alone would keep them all; the badge keeps her whose shown face matched."""
    _, token = await person(db, make_user, Gender.MALE)
    matched, _ = await person(db, make_user, at=north(1))
    unmatched, _ = await person(db, make_user, at=north(2))
    no_photo, _ = await person(db, make_user, at=north(3))
    await photo(db, matched, matched=True)
    await photo(db, unmatched, matched=False)

    assert await ids(client, token, verified="true") == [str(matched.id)]
    assert await ids(client, token, verified="false") == [
        str(matched.id),
        str(unmatched.id),
        str(no_photo.id),
    ]


async def test_a_badge_for_a_man_needs_is_verified_too(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user)
    verified, _ = await person(db, make_user, Gender.MALE, at=north(1), verified=True)
    unverified, _ = await person(
        db, make_user, Gender.MALE, at=north(2), verified=False
    )
    await photo(db, verified, matched=True)
    await photo(db, unverified, matched=True)

    assert await ids(client, token, verified="true") == [str(verified.id)]


# --- The feeds -------------------------------------------------------------------


async def test_the_new_feed_puts_the_new_first_then_ranks_each(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE, created_at=NOON)
    old_near, _ = await person(
        db, make_user, at=north(1), created_at=NOON - timedelta(days=30)
    )
    new_far, _ = await person(
        db, make_user, at=north(15), created_at=NOON - timedelta(days=6)
    )
    new_near, _ = await person(
        db, make_user, at=north(5), created_at=NOON - timedelta(days=1)
    )
    old_far, _ = await person(
        db, make_user, at=north(9), created_at=NOON - timedelta(days=8)
    )

    assert await ids(client, token, feed="new") == [
        str(new_near.id),
        str(new_far.id),
        str(old_near.id),
        str(old_far.id),
    ]
    assert await ids(client, token) == [
        str(old_near.id),
        str(new_near.id),
        str(old_far.id),
        str(new_far.id),
    ]


async def test_the_online_feed_is_the_last_five_minutes_only(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE, last_active_at=NOON)
    now, _ = await person(db, make_user, at=north(2), last_active_at=NOON)
    edge, _ = await person(
        db, make_user, at=north(1), last_active_at=NOON - timedelta(minutes=5)
    )
    await person(
        db,
        make_user,
        at=north(3),
        last_active_at=NOON - timedelta(minutes=5, seconds=1),
    )
    await person(db, make_user, at=north(4))

    assert await ids(client, token, feed="online") == [str(edge.id), str(now.id)]


async def test_the_online_filter_keeps_the_last_five_minutes_in_any_feed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """D-660: T-6.9's "Online now" is a filter, so New keeps its order under it."""
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE, last_active_at=NOON)
    old_online, _ = await person(
        db,
        make_user,
        at=north(1),
        created_at=NOON - timedelta(days=30),
        last_active_at=NOON - timedelta(minutes=5),
    )
    new_online, _ = await person(
        db,
        make_user,
        at=north(9),
        created_at=NOON - timedelta(days=1),
        last_active_at=NOON,
    )
    await person(
        db,
        make_user,
        at=north(2),
        created_at=NOON - timedelta(days=1),
        last_active_at=NOON - timedelta(minutes=5, seconds=1),
    )
    await person(db, make_user, at=north(3), created_at=NOON - timedelta(days=30))

    assert await ids(client, token, feed="new", online="true") == [
        str(new_online.id),
        str(old_online.id),
    ]
    assert await ids(client, token, online="true") == [
        str(old_online.id),
        str(new_online.id),
    ]
    assert await ids(client, token, online="true") == await ids(
        client, token, feed="online"
    )
    assert len(await ids(client, token, online="false")) == 4


async def test_an_online_filter_that_isnt_a_yes_or_no_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await discover(client, token, online="maybe")

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_a_feed_that_isnt_one_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await discover(client, token, feed="nearby")

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


# --- The ranking -------------------------------------------------------------------


async def test_each_term_ranks_on_its_own(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """Pairs that differ by one term only, each in its own feed."""
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    nearer, _ = await person(db, make_user, at=north(2))
    farther, _ = await person(db, make_user, at=north(8))
    assert await ids(client, token) == [str(nearer.id), str(farther.id)]

    _, token = await person(db, make_user, Gender.MALE, at=north(-100))
    recent, _ = await person(
        db, make_user, at=north(-98), last_active_at=NOON - timedelta(hours=1)
    )
    stale, _ = await person(
        db, make_user, at=north(-98), last_active_at=NOON - timedelta(days=3)
    )
    assert await ids(client, token) == [str(recent.id), str(stale.id)]

    _, token = await person(db, make_user, Gender.MALE, at=north(-200))
    fuller, _ = await person(db, make_user, at=north(-198), completeness=90)
    thinner, _ = await person(db, make_user, at=north(-198), completeness=50)
    assert await ids(client, token) == [str(fuller.id), str(thinner.id)]


async def test_is_verified_ranks_whether_or_not_the_badge_shows(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """P-290, answered 8 October 2026: D-032's boost stays, badge or not."""
    _, token = await person(db, make_user)
    verified, _ = await person(db, make_user, Gender.MALE, at=north(3), verified=True)
    unverified, _ = await person(
        db, make_user, Gender.MALE, at=north(3), verified=False
    )

    assert await ids(client, token) == [str(verified.id), str(unverified.id)]


async def test_the_score_is_d491s_formula_exactly(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """Read back from the cursor, which carries the last card's score."""
    clock.freeze(NOON)
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(
        db,
        make_user,
        at=north(4),
        completeness=70,
        last_active_at=NOON - timedelta(hours=6),
    )
    await person(db, make_user, at=north(9))

    response = await discover(client, token, limit=1)

    assert response.status_code == 200
    assert [c["id"] for c in response.json()["items"]] == [str(her.id)]
    as_of, score, last = FEED_CURSOR.decode(response.json()["next_cursor"])
    assert (as_of, last) == (NOON, her.id)
    distance = await db.scalar(
        text(
            "SELECT ST_Distance(a.location, b.location) FROM profiles a, profiles b "
            "WHERE a.user_id = :me AND b.user_id = :her"
        ),
        {"me": me.id, "her": her.id},
    )
    assert distance is not None and 4_000 < distance < 5_000
    expected = (
        rules.WEIGHT_DISTANCE / (1 + distance / 1000 / rules.DISTANCE_HALF_KM)
        + rules.WEIGHT_RECENCY / (1 + 6 / 24)
        + rules.WEIGHT_VERIFIED * 1
        + rules.WEIGHT_COMPLETENESS * 0.70
    )
    assert score == pytest.approx(expected, rel=1e-12)
    assert (rules.WEIGHT_DISTANCE, rules.WEIGHT_RECENCY) == (0.40, 0.30)
    assert (rules.WEIGHT_VERIFIED, rules.WEIGHT_COMPLETENESS) == (0.15, 0.15)


async def test_the_weights_order_a_near_stranger_above_a_far_regular(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """0 km, never active: 0.40 + 0.15 + 0.075. About 24 km, active now:
    0.40/5.9 + 0.30 + 0.15 + 0.075. Distance weighs most (D-491)."""
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    near, _ = await person(db, make_user)
    far, _ = await person(db, make_user, at=north(22), last_active_at=NOON)

    assert await ids(client, token) == [str(near.id), str(far.id)]


# --- Who may ask -------------------------------------------------------------------


async def test_without_a_token_it_is_auth_required(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.get("/v1/discover")

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


async def test_before_onboarding_is_done_it_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await discover(client, token)

    assert response.status_code == 403
    assert error(response) | {"message": None} == {
        "code": "ONBOARDING_INCOMPLETE",
        "message": None,
        "details": {"step": "seeking"},
    }


# --- Swipes left today (T-6.5) ---------------------------------------------------------


async def _cap(db: AsyncSession, limit: int) -> None:
    await db.execute(
        text(
            "UPDATE app_config SET value = CAST(:v AS jsonb)"
            " WHERE key = 'swipe_daily_limit_men'"
        ),
        {"v": str(limit)},
    )


async def test_a_mans_feed_says_his_swipes_left_before_and_after_a_swipe(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The deck says it before his first swipe (the founder, 8 October 2026):
    the cap from `app_config`, less what `POST /swipes` counted today."""
    await _cap(db, 3)
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))

    before = await discover(client, token)
    assert set(before.json()) == {"items", "next_cursor", "swipes_left"}
    assert before.json()["swipes_left"] == 3

    await swipe_by_api(client, token, her.id, "like")

    assert (await discover(client, token)).json()["swipes_left"] == 2


async def test_a_womans_feed_has_no_count(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Women have no cap (D-492): null, never a number."""
    _, token = await person(db, make_user)
    await person(db, make_user, Gender.MALE, at=north(1))

    response = await discover(client, token)

    assert response.status_code == 200
    assert response.json()["swipes_left"] is None


async def swipe_by_api(
    client: AsyncClient, token: str, target: object, direction: str
) -> None:
    response = await client.post(
        "/v1/swipes",
        json={"target_id": str(target), "dir": direction},
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text
