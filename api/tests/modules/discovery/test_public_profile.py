"""`GET /v1/users/{id}` (T-6.3, D-493): a `Card` and the rest of the profile,
to anyone `visible_to` allows without seeking or the radius; a hidden profile
only to someone it shares a match or a Thread with; every refusal one and the
same `NOT_FOUND`, a block either way among them; a view recorded once per pair
and counted, never for your own profile or a refusal; and nothing private in
the answer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    FraudBand,
    Gender,
    OnboardingStep,
    PhotoKind,
    ReviewStatus,
    Seeking,
    UserStatus,
)
from app.modules.discovery.models import ProfileView
from app.modules.profiles.models import Profile, ProfileInterest
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings
from tests.modules.discovery.support import (
    banded,
    bearer,
    block,
    error,
    north,
    person,
    photo,
)

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)

FIELDS = {
    "id",
    "first_name",
    "age",
    "username",
    "city",
    "hometown",
    "distance_km",
    "intent_ids",
    "bio_line",
    "main_photo_url",
    "shows_badge",
    "is_online",
    "is_new",
    "about",
    "photo_urls",
    "interest_ids",
    "kudos",
    "album_photo_count",
    "match_id",
    "thread",
    "can_gift",
}


async def _get(client: AsyncClient, token: str, user_id: object) -> Response:
    return await client.get(f"/v1/users/{user_id}", headers=bearer(token))


async def _ok(client: AsyncClient, token: str, user: User) -> dict[str, Any]:
    response = await _get(client, token, user.id)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert set(body) == FIELDS
    return body


def _url(key: str) -> str:
    return f"{make_test_settings().PUBLIC_CDN_URL}/{key}"


async def _views(db: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    rows = await db.execute(
        select(
            ProfileView.viewer_id, ProfileView.viewed_id, ProfileView.view_count
        ).execution_options(populate_existing=True)
    )
    return [(row[0], row[1], row[2]) for row in rows]


def _pair(a: User, b: User) -> tuple[uuid.UUID, uuid.UUID]:
    return (a.id, b.id) if a.id.bytes < b.id.bytes else (b.id, a.id)


async def _thread(
    db: AsyncSession, a: User, b: User, status: str = "active"
) -> uuid.UUID:
    low, high = _pair(a, b)
    thread_id = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO threads (id, user_low, user_high, origin, opened_by, status,"
            " expires_at, knotted_at) VALUES (:id, :low, :high, 'match', :by,"
            " CAST(:status AS thread_status_t), :expires, :knotted)"
        ),
        {
            "id": thread_id,
            "low": low,
            "high": high,
            "by": a.id,
            "status": status,
            "expires": None if status == "knotted" else NOON + timedelta(hours=1),
            "knotted": NOON if status == "knotted" else None,
        },
    )
    return thread_id


async def _match(db: AsyncSession, a: User, b: User) -> uuid.UUID:
    low, high = _pair(a, b)
    match_id = uuid.uuid4()
    await db.execute(
        text("INSERT INTO matches (id, user_low, user_high) VALUES (:id, :low, :high)"),
        {"id": match_id, "low": low, "high": high},
    )
    return match_id


# --- What it says ---------------------------------------------------------------------


async def test_a_profile_says_its_card_and_the_rest(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    about = "Morning runs by the canal, evening chai, and a long list of books. " * 3
    her, _ = await person(
        db, make_user, at=north(3), first_name="Simran", about=about[:300]
    )
    shown = [await photo(db, her, place=n) for n in (2, 0, 4)]
    for interest_id in (9, 3, 14):
        db.add(ProfileInterest(user_id=her.id, interest_id=interest_id))
    await db.flush()
    profile = await db.get(Profile, her.id)
    assert profile is not None

    body = await _ok(client, token, her)

    assert body["id"] == str(her.id)
    assert body["first_name"] == "Simran"
    assert body["username"] == profile.username
    assert body["about"] == about[:300]
    assert body["bio_line"] == about[:90]
    assert body["distance_km"] == 3
    in_order = sorted(shown, key=lambda p: p.position or 0)
    assert body["photo_urls"] == [_url(f"p/{p.id}.jpg") for p in in_order]
    assert body["main_photo_url"] == body["photo_urls"][0]
    assert body["interest_ids"] == [3, 9, 14]
    assert body["kudos"] == {
        "great_conversation": 0,
        "genuinely_funny": 0,
        "easy_to_talk_to": 0,
        "really_thoughtful": 0,
    }
    assert (body["album_photo_count"], body["match_id"], body["thread"]) == (
        0,
        None,
        None,
    )


async def test_only_approved_public_photos_are_shown_and_nothing_private_named(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """06-TESTING's critical 14 for this answer: no private, selfie or face
    photo, no raw key, ever; private ones only as a count."""
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    main = await photo(db, her, place=1)
    await photo(db, her, place=0, status=ReviewStatus.REJECTED)
    # Removed by her: rejected as `user_deleted`, its row keeping the key of
    # the public copy that `delete_photo` took away (T-4.3).
    removed = await photo(db, her, place=3)
    removed.status, removed.reject_reason = ReviewStatus.REJECTED, "user_deleted"
    await photo(db, her, place=2, status=ReviewStatus.PENDING)
    await photo(db, her, kind=PhotoKind.VERIFICATION)
    await photo(db, her, kind=PhotoKind.SELFIE)
    await photo(db, her, kind=PhotoKind.PRIVATE)
    await photo(db, her, kind=PhotoKind.PRIVATE)
    await photo(db, her, kind=PhotoKind.PRIVATE, status=ReviewStatus.PENDING)
    # Approved before D-700 wrote scored copies: the album never shows it, so
    # the count, what a man pays to see, doesn't count it (T-8.4).
    await photo(db, her, kind=PhotoKind.PRIVATE, scored=False)

    response = await _get(client, token, her.id)

    body = response.json()
    assert body["photo_urls"] == [_url(f"p/{main.id}.jpg")]
    assert body["album_photo_count"] == 2
    assert "raw/" not in response.text


async def test_no_photo_is_no_photos_and_a_null_main(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))

    body = await _ok(client, token, her)

    assert (body["photo_urls"], body["main_photo_url"]) == ([], None)


async def test_kudos_are_counted_and_null_when_hidden(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    givers = [
        (await person(db, make_user, Gender.MALE, at=north(9)))[0] for _ in range(3)
    ]
    for giver, kind in zip(
        givers, ["genuinely_funny", "genuinely_funny", "really_thoughtful"], strict=True
    ):
        thread_id = await _thread(db, giver, her)
        await db.execute(
            text(
                "INSERT INTO kudos (from_id, to_id, kind, thread_id) VALUES"
                " (:a, :b, CAST(:kind AS kudos_t), :thread)"
            ),
            {"a": giver.id, "b": her.id, "kind": kind, "thread": thread_id},
        )

    body = await _ok(client, token, her)
    assert body["kudos"] == {
        "great_conversation": 0,
        "genuinely_funny": 2,
        "easy_to_talk_to": 0,
        "really_thoughtful": 1,
    }

    profile = await db.get(Profile, her.id)
    assert profile is not None
    profile.show_kudos = False
    await db.flush()

    assert (await _ok(client, token, her))["kudos"] is None


@pytest.mark.parametrize("status", ["active", "expired", "knotted"])
async def test_the_thread_with_me_and_the_match(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, status: str
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    match_id = await _match(db, me, her)
    thread_id = await _thread(db, me, her, status)

    body = await _ok(client, token, her)

    assert body["match_id"] == str(match_id)
    assert body["thread"] == {
        "id": str(thread_id),
        "status": status,
        "expires_at": None
        if status == "knotted"
        else (NOON + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        # No messages yet (D-790; tests/modules/kudos/test_state.py).
        "kudos": "too_early",
    }


async def test_someone_elses_thread_is_not_mine(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    other, _ = await person(db, make_user, Gender.MALE, at=north(2))
    await _match(db, other, her)
    await _thread(db, other, her)

    body = await _ok(client, token, her)

    assert (body["match_id"], body["thread"]) == (None, None)


async def test_hidden_age_and_distance_stay_hidden(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), hide_age=True, hide_distance=True)

    body = await _ok(client, token, her)

    assert (body["age"], body["distance_km"]) == (None, None)


# --- Who may see it ---------------------------------------------------------------


async def test_seeking_and_the_radius_dont_apply_a_link_reaches_past_them(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-493: a profile is reached by link too (T-6.8), so a man seeking women
    may open a man's, and anyone's from across India."""
    _, token = await person(db, make_user, Gender.MALE)
    man, _ = await person(db, make_user, Gender.MALE, at=north(1))
    far, _ = await person(db, make_user, at=(12.97, 77.59), seeking=Seeking.WOMEN)

    assert (await _ok(client, token, man))["id"] == str(man.id)
    assert (await _ok(client, token, far))["distance_km"] > 1500


async def _refusal(client: AsyncClient, token: str, user_id: object) -> dict[str, Any]:
    response = await _get(client, token, user_id)
    assert response.status_code == 404, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_every_refusal_is_the_same_not_found_as_nobody(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Which reason, the asker never learns: the body is nobody's."""
    me, token = await person(db, make_user, Gender.MALE)
    hidden, _ = await person(db, make_user, is_hidden=True)
    blocked_by_me, _ = await person(db, make_user)
    blocked_me, _ = await person(db, make_user)
    unfinished, _ = await person(db, make_user)
    frozen_band, _ = await person(db, make_user)
    shadowed, _ = await person(db, make_user)
    await block(db, me, blocked_by_me)
    await block(db, blocked_me, me)
    unfinished.onboarding_step = OnboardingStep.SELFIE
    await banded(db, frozen_band, FraudBand.FREEZE)
    await banded(db, shadowed, FraudBand.SHADOW)
    await db.flush()

    # Read now: each request's commit expires the objects a test holds.
    refused = [
        u.id
        for u in (hidden, blocked_by_me, blocked_me, unfinished, frozen_band, shadowed)
    ]
    nobody = await _refusal(client, token, uuid.uuid4())
    assert nobody == {"error": {"code": "NOT_FOUND", "message": "Not found."}}
    for user_id in refused:
        assert await _refusal(client, token, user_id) == nobody, user_id


@pytest.mark.parametrize(
    "status", [s for s in UserStatus if s is not UserStatus.ACTIVE]
)
async def test_an_account_not_active_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, status: UserStatus
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    her.status = status
    await db.flush()

    assert (await _refusal(client, token, her.id))["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("shared", ["match", "thread"])
async def test_a_hidden_profile_opens_to_someone_it_shares_a_match_or_thread_with(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, shared: str
) -> None:
    """D-493: hidden leaves the feed and search, never a chat's own header."""
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), is_hidden=True)
    stranger, strangers = await person(db, make_user, Gender.MALE, at=north(2))
    if shared == "match":
        await _match(db, me, her)
    else:
        await _thread(db, me, her)
    await _match(db, stranger, (await person(db, make_user, at=north(3)))[0])

    assert (await _ok(client, token, her))["id"] == str(her.id)
    assert (await _refusal(client, strangers, her.id))["error"]["code"] == "NOT_FOUND"


async def test_a_block_beats_a_shared_thread(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), is_hidden=True)
    await _thread(db, me, her)
    await block(db, her, me)

    assert (await _refusal(client, token, her.id))["error"]["code"] == "NOT_FOUND"


async def test_the_shadowed_open_to_the_shadowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await banded(db, me, FraudBand.SHADOW)
    await banded(db, her, FraudBand.SHADOW)

    assert (await _ok(client, token, her))["id"] == str(her.id)


async def test_my_own_profile_opens_with_nothing_between_us(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Even hidden: it's mine. No view of myself is recorded."""
    me, token = await person(db, make_user, Gender.MALE, is_hidden=True)

    body = await _ok(client, token, me)

    assert body["id"] == str(me.id)
    assert (body["match_id"], body["thread"], body["distance_km"]) == (None, None, None)
    assert await _views(db) == []


# --- Whether he may send her a gift (T-8.10, D-780) ------------------------------


async def _sends(client: AsyncClient, token: str, user_id: object) -> bool:
    """Whether `POST /gifts/send` takes a free gift to them, as the gift
    button would send it: the answer `can_gift` must agree with."""
    response = await client.post(
        "/v1/gifts/send",
        json={"recipient_id": str(user_id), "gift_id": "coffee", "shown_price": 0},
        headers={**bearer(token), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code in (200, 404, 422), response.text
    return response.status_code == 200


@pytest.mark.parametrize(
    ("viewer", "viewed", "seeking", "gifts"),
    [
        (Gender.MALE, Gender.FEMALE, Seeking.MEN, True),
        (Gender.MALE, Gender.FEMALE, Seeking.EVERYONE, True),
        # D-493 opens her profile by link; D-653 reaches her only as a
        # private message would, each wanting the other's gender.
        (Gender.MALE, Gender.FEMALE, Seeking.WOMEN, False),
        (Gender.MALE, Gender.MALE, Seeking.MEN, False),
        (Gender.FEMALE, Gender.MALE, Seeking.WOMEN, False),
        (Gender.FEMALE, Gender.FEMALE, Seeking.WOMEN, False),
    ],
)
async def test_can_gift_is_the_sends_own_answer(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    viewer: Gender,
    viewed: Gender,
    seeking: Seeking,
    gifts: bool,
) -> None:
    """The gift button shows exactly where a send is taken: a man viewing a
    woman he could send a private message to, and nobody else."""
    _, token = await person(db, make_user, viewer, seeking=Seeking.EVERYONE)
    them, _ = await person(db, make_user, viewed, at=north(1), seeking=seeking)
    their_id = them.id

    assert (await _ok(client, token, them))["can_gift"] is gifts
    assert await _sends(client, token, their_id) is gifts


@pytest.mark.parametrize("gender", [Gender.MALE, Gender.FEMALE])
async def test_my_own_profile_offers_no_gift(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, gender: Gender
) -> None:
    me, token = await person(db, make_user, gender)

    assert (await _ok(client, token, me))["can_gift"] is False


# --- The view ---------------------------------------------------------------------


async def test_a_view_is_one_row_per_pair_counted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    me, token = await person(db, make_user, Gender.MALE)
    her, hers = await person(db, make_user, at=north(1))

    await _ok(client, token, her)
    clock.advance(timedelta(minutes=3))
    await _ok(client, token, her)
    await _ok(client, hers, me)

    assert sorted(await _views(db)) == sorted([(me.id, her.id, 2), (her.id, me.id, 1)])
    last = await db.scalar(
        select(ProfileView.last_viewed_at)
        .where(ProfileView.viewer_id == me.id)
        .execution_options(populate_existing=True)
    )
    assert last == NOON + timedelta(minutes=3)


async def test_a_refusal_records_no_view(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await block(db, her, me)

    await _refusal(client, token, her.id)
    await _refusal(client, token, uuid.uuid4())

    assert await _views(db) == []


# --- Who may ask ------------------------------------------------------------------


async def test_without_a_token_it_is_auth_required(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.get(f"/v1/users/{uuid.uuid4()}")

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


async def test_before_onboarding_is_done_it_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await _get(client, token, uuid.uuid4())

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"


async def test_an_id_that_isnt_one_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await _get(client, token, "ananya_d")

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
