"""`POST /v1/swipes` (T-6.4): a like, a pass or a Super Like, once per pair;
men's daily cap (like and pass count, a Super Like doesn't, D-492) by the IST
day, its place given back when nothing is written; a Super Like 5 Velas for a
man through the wallet and nothing for a woman (D-250, D-002); only someone the
feed could show you (D-492); and a like back makes one match, both told."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import IST
from app.core.enums import FraudBand, Gender, OnboardingStep, Seeking
from app.modules.matches.models import Match
from app.modules.notifications.models import Notification
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles.models import Profile
from app.modules.swipes.models import Swipe
from app.modules.swipes.router import SWIPES_PER_MINUTE
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import MakeUser
from tests.modules.discovery.support import (
    HERE,
    banded,
    bearer,
    block,
    error,
    north,
    person,
)

pytestmark = pytest.mark.usefixtures("test_redis")

# 18:00 IST, 8 October 2026.
EVENING = datetime(2026, 10, 8, 18, 0, tzinfo=IST)


async def _swipe(
    client: AsyncClient, token: str, target: object, direction: str = "like"
) -> Response:
    return await client.post(
        "/v1/swipes",
        json={"target_id": str(target), "dir": direction},
        headers=bearer(token),
    )


async def _ok(
    client: AsyncClient, token: str, target: object, direction: str = "like"
) -> dict[str, Any]:
    response = await _swipe(client, token, target, direction)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert set(body) == {"matched", "match_id", "swipes_left"}
    return body


async def _cap(db: AsyncSession, limit: int) -> None:
    await db.execute(
        text(
            "UPDATE app_config SET value = CAST(:v AS jsonb)"
            " WHERE key = 'swipe_daily_limit_men'"
        ),
        {"v": str(limit)},
    )


async def _women(db: AsyncSession, make_user: MakeUser, count: int) -> list[uuid.UUID]:
    return [(await person(db, make_user, at=north(n % 9)))[0].id for n in range(count)]


async def _swipes_by(db: AsyncSession, user_id: uuid.UUID) -> int:
    found = await db.scalar(
        select(func.count()).select_from(Swipe).where(Swipe.swiper_id == user_id)
    )
    return found or 0


async def _ledger(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[str, int, str, uuid.UUID]]:
    rows = await db.execute(
        select(
            LedgerEntry.reason,
            LedgerEntry.delta,
            LedgerEntry.ref_type,
            LedgerEntry.ref_id,
        )
        .where(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.created_at)
        .execution_options(populate_existing=True)
    )
    return [(str(r[0]), r[1], str(r[2]), r[3]) for r in rows]


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    found = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


# --- A swipe ------------------------------------------------------------------------


@pytest.mark.parametrize("direction", ["like", "pass"])
async def test_a_swipe_is_written_once_and_counted_for_a_man(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, direction: str
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    me_id, her_id = me.id, her.id

    body = await _ok(client, token, her_id, direction)

    assert body == {"matched": False, "match_id": None, "swipes_left": 49}
    written = (
        await db.execute(
            select(Swipe.swiper_id, Swipe.target_id, Swipe.dir).execution_options(
                populate_existing=True
            )
        )
    ).all()
    assert [(a, b, str(d)) for a, b, d in written] == [(me_id, her_id, direction)]


async def test_a_woman_has_no_cap_and_no_count(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await _cap(db, 2)
    _, token = await person(db, make_user)
    men = [
        (await person(db, make_user, Gender.MALE, at=north(n)))[0].id for n in range(4)
    ]

    for man in men:
        assert (await _ok(client, token, man))["swipes_left"] is None


async def test_a_swipe_far_beyond_the_radius_is_still_a_swipe(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-492: the radius is the feed's, not the swipe's: someone found by
    their @username across India may be liked."""
    _, token = await person(db, make_user, Gender.MALE)
    far, _ = await person(db, make_user, at=(12.97, 77.59))

    assert (await _ok(client, token, far.id))["matched"] is False


# --- The daily cap -----------------------------------------------------------------


async def test_the_cap_is_app_configs_and_the_next_swipe_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(EVENING)
    await _cap(db, 3)
    me, token = await person(db, make_user, Gender.MALE)
    me_id = me.id
    women = await _women(db, make_user, 4)

    lefts = [
        (await _ok(client, token, w, d))["swipes_left"]
        for w, d in zip(women[:3], ["like", "pass", "like"], strict=True)
    ]
    refused = await _swipe(client, token, women[3])

    assert lefts == [2, 1, 0]
    assert refused.status_code == 429
    assert error(refused) == {
        "code": "SWIPE_LIMIT_REACHED",
        "message": "That's today's swipes. More tomorrow.",
        "details": {"limit": 3, "resets_at": "2026-10-09T00:00:00+05:30"},
    }
    assert await _swipes_by(db, me_id) == 3


async def test_a_super_like_doesnt_count_and_goes_past_the_cap(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-492: it is its own, paid action (D-250), not swiping."""
    await _cap(db, 1)
    me, token = await make_user(credits=10)
    await person_at(db, me)
    women = await _women(db, make_user, 3)

    assert (await _ok(client, token, women[0], "super"))["swipes_left"] == 1
    assert (await _ok(client, token, women[1]))["swipes_left"] == 0
    assert (await _ok(client, token, women[2], "super"))["swipes_left"] == 0


async def test_the_count_starts_again_at_ist_midnight(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(datetime(2026, 10, 8, 23, 59, tzinfo=IST))
    await _cap(db, 1)
    _, token = await person(db, make_user, Gender.MALE)
    women = await _women(db, make_user, 3)
    await _ok(client, token, women[0])
    assert (await _swipe(client, token, women[1])).status_code == 429

    clock.advance(timedelta(minutes=1))

    assert (await _ok(client, token, women[1]))["swipes_left"] == 0


@pytest.mark.parametrize("refusal", ["duplicate", "nobody", "blocked"])
async def test_a_swipe_not_written_gives_its_place_back(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, refusal: str
) -> None:
    await _cap(db, 2)
    me, token = await person(db, make_user, Gender.MALE)
    women = await _women(db, make_user, 3)
    await _ok(client, token, women[0])
    if refusal == "blocked":
        await db.execute(
            text("INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b)"),
            {"a": women[1], "b": me.id},
        )
    target = {"duplicate": women[0], "nobody": uuid.uuid4(), "blocked": women[1]}[
        refusal
    ]

    refused = await _swipe(client, token, target)

    assert refused.status_code in (404, 409)
    assert (await _ok(client, token, women[2]))["swipes_left"] == 0


# --- The Super Like ----------------------------------------------------------------


async def test_a_mans_super_like_debits_five_through_the_wallet(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(credits=12)
    await person_at(db, me)
    her, _ = await person(db, make_user, at=north(1))
    me_id, her_id = me.id, her.id

    await _ok(client, token, her_id, "super")

    assert await _balance(db, me_id) == 7
    entries = await _ledger(db, me_id)
    assert entries[-1] == ("super_like", -5, "user", her_id)


async def person_at(db: AsyncSession, user: User) -> None:
    """`make_user`'s man, placed on the grid as `person` places one."""
    profile = await db.get(Profile, user.id)
    assert profile is not None
    profile.location = profiles_repository.point(*HERE)
    await db.flush()


async def test_a_super_like_he_cant_afford_is_402_and_writes_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(credits=4)
    await person_at(db, me)
    her, _ = await person(db, make_user, at=north(1))
    me_id = me.id

    refused = await _swipe(client, token, her.id, "super")

    assert refused.status_code == 402
    assert error(refused)["code"] == "INSUFFICIENT_CREDITS"
    assert error(refused)["details"] == {"required": 5, "balance": 4}
    assert await _swipes_by(db, me_id) == 0
    assert await _balance(db, me_id) == 4


async def test_a_womans_super_like_is_free_and_writes_no_ledger_row(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-002, 06-TESTING's critical 6 for this action."""
    her, token = await person(db, make_user)
    him, _ = await person(db, make_user, Gender.MALE, at=north(1))
    her_id = her.id

    body = await _ok(client, token, him.id, "super")

    assert body["swipes_left"] is None
    assert await _ledger(db, her_id) == []


async def test_a_second_super_like_is_already_exists_and_charges_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(credits=20)
    await person_at(db, me)
    her, _ = await person(db, make_user, at=north(1))
    me_id, her_id = me.id, her.id
    await _ok(client, token, her_id, "super")

    again = await _swipe(client, token, her_id, "super")

    assert again.status_code == 409
    assert error(again)["code"] == "ALREADY_EXISTS"
    assert await _balance(db, me_id) == 15


@pytest.mark.parametrize(
    ("first", "second"), [("like", "pass"), ("pass", "like"), ("pass", "super")]
)
async def test_one_swipe_per_pair_ever(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, first: str, second: str
) -> None:
    me, token = await make_user(credits=20)
    await person_at(db, me)
    her, _ = await person(db, make_user, at=north(1))
    me_id = me.id
    await _ok(client, token, her.id, first)

    again = await _swipe(client, token, her.id, second)

    assert again.status_code == 409
    assert error(again)["code"] == "ALREADY_EXISTS"
    assert await _swipes_by(db, me_id) == 1
    assert await _balance(db, me_id) == 20


# --- Who may be swiped -------------------------------------------------------------


async def test_nobody_the_feed_could_never_show_you_can_be_swiped(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-492: the same `NOT_FOUND` for each, and nothing written."""
    me, token = await person(db, make_user, Gender.MALE)
    me_id = me.id
    hidden, _ = await person(db, make_user, is_hidden=True)
    blocked_by_me, _ = await person(db, make_user)
    blocked_me, _ = await person(db, make_user)
    wants_women, _ = await person(db, make_user, seeking=Seeking.WOMEN)
    a_man, _ = await person(db, make_user, Gender.MALE)
    unfinished, _ = await person(db, make_user)
    shadowed, _ = await person(db, make_user)
    frozen, _ = await person(db, make_user)
    await block(db, me, blocked_by_me)
    await block(db, blocked_me, me)
    unfinished.onboarding_step = OnboardingStep.SELFIE
    await banded(db, shadowed, FraudBand.SHADOW)
    await banded(db, frozen, FraudBand.FREEZE)
    await db.flush()
    targets = [
        me_id,
        uuid.uuid4(),
        *(
            u.id
            for u in (
                hidden,
                blocked_by_me,
                blocked_me,
                wants_women,
                a_man,
                unfinished,
                shadowed,
                frozen,
            )
        ),
    ]

    for target in targets:
        refused = await _swipe(client, token, target)
        assert refused.status_code == 404, target
        assert refused.json() == {
            "error": {"code": "NOT_FOUND", "message": "Not found."}
        }
    assert await _swipes_by(db, me_id) == 0


# --- The match ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hers", "mine"), [("like", "like"), ("super", "like"), ("like", "super")]
)
async def test_a_like_back_makes_one_match_and_tells_both(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, hers: str, mine: str
) -> None:
    me, token = await make_user(credits=10)
    await person_at(db, me)
    her, her_token = await person(db, make_user, at=north(1))
    me_id, her_id = me.id, her.id
    first = await _ok(client, her_token, me_id, hers)
    assert (first["matched"], first["match_id"]) == (False, None)

    body = await _ok(client, token, her_id, mine)

    assert body["matched"] is True
    match = await db.scalar(select(Match).execution_options(populate_existing=True))
    assert match is not None and body["match_id"] == str(match.id)
    assert {match.user_low, match.user_high} == {me_id, her_id}
    assert match.user_low.bytes < match.user_high.bytes
    told = (
        await db.execute(
            select(
                Notification.user_id, Notification.kind, Notification.payload
            ).execution_options(populate_existing=True)
        )
    ).all()
    assert sorted(told, key=lambda r: str(r[0])) == sorted(
        [
            (me_id, "match", {"match_id": str(match.id), "user_id": str(her_id)}),
            (her_id, "match", {"match_id": str(match.id), "user_id": str(me_id)}),
        ],
        key=lambda r: str(r[0]),
    )


@pytest.mark.parametrize(("hers", "mine"), [("pass", "like"), ("like", "pass")])
async def test_a_pass_either_way_makes_no_match(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, hers: str, mine: str
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, her_token = await person(db, make_user, at=north(1))
    me_id, her_id = me.id, her.id
    await _ok(client, her_token, me_id, hers)

    body = await _ok(client, token, her_id, mine)

    assert (body["matched"], body["match_id"]) == (False, None)
    assert await db.scalar(select(func.count()).select_from(Match)) == 0
    assert await db.scalar(select(func.count()).select_from(Notification)) == 0


# --- The request -------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"target_id": str(uuid.uuid4()), "dir": "right"},
        {"target_id": "ananya_d", "dir": "like"},
        {"target_id": str(uuid.uuid4())},
        {"target_id": str(uuid.uuid4()), "dir": "like", "price": 0},
    ],
)
async def test_a_body_the_schema_refuses_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, body: dict[str, Any]
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await client.post("/v1/swipes", json=body, headers=bearer(token))

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_past_120_a_minute_it_is_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Refused swipes count too: the limit is on asking."""
    assert SWIPES_PER_MINUTE == 120
    _, token = await person(db, make_user)
    for _ in range(SWIPES_PER_MINUTE):
        assert (await _swipe(client, token, uuid.uuid4())).status_code == 404

    limited = await _swipe(client, token, uuid.uuid4())

    assert limited.status_code == 429
    assert error(limited)["code"] == "RATE_LIMITED"


async def test_without_a_token_it_is_auth_required(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.post(
        "/v1/swipes", json={"target_id": str(uuid.uuid4()), "dir": "like"}
    )

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


async def test_before_onboarding_is_done_it_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await _swipe(client, token, uuid.uuid4())

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"
