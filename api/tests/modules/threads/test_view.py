"""`GET /v1/threads/{id}` as the conversation screen opens it (T-7.11, D-870):
the Thread, the other person as the chats list shows them, counting no profile
view (D-493), and `send_price`, what my next text message costs now, which is
exactly the `shown_price` the send then takes (P-56, D-600), worked out by the
send's own rules (D-551, D-641)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, Seeking, UserStatus
from app.modules.discovery.models import ProfileView
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, block, error, north, person
from tests.modules.kudos.test_give import _give, _talked

pytestmark = pytest.mark.usefixtures("test_redis")


async def _view(
    client: AsyncClient, token: str, thread_id: uuid.UUID
) -> dict[str, Any]:
    response = await client.get(f"/v1/threads/{thread_id}", headers=bearer(token))
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


async def _price(client: AsyncClient, token: str, thread_id: uuid.UUID) -> int:
    price: int = (await _view(client, token, thread_id))["send_price"]
    return price


async def _send_at(
    client: AsyncClient, token: str, thread_id: uuid.UUID, shown_price: int
) -> None:
    """A text sent at the price the screen showed: the send must take it."""
    response = await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "kind": "text",
            "body": "Hello",
            "shown_price": shown_price,
        },
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text


async def _spent(db: AsyncSession, user_id: uuid.UUID) -> int:
    """What `user_id` has been charged, in Velas: so the price shown is proved
    to be the price taken, not only a price the send accepted."""
    total = await db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.delta), 0)).where(
            LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant"
        )
    )
    return -int(total or 0)


async def test_the_thread_comes_with_the_other_person_and_counts_no_view(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    thread_id, man_id, woman_id = thread.id, man.id, woman.id

    mine = await _view(client, token, thread_id)
    hers = await _view(client, her_token, thread_id)

    assert set(mine) == {
        "id",
        "origin",
        "status",
        "other_user_id",
        "expires_at",
        "knotted_at",
        "i_tied",
        "last_message_at",
        "created_at",
        "other",
        "send_price",
        "can_gift",
        "kudos",
    }
    assert mine["other"] == {
        "id": str(woman_id),
        "first_name": "Test",
        "username": mine["other"]["username"],
        "main_photo_url": None,
        "shows_badge": False,
        "is_online": False,
        "deleted": False,
    }
    assert mine["other_user_id"] == str(woman_id)
    assert hers["other"]["id"] == str(man_id)
    # Her side carries no expiry (D-554), here as in the list.
    assert mine["expires_at"] is not None and hers["expires_at"] is None
    views = await db.scalar(select(func.count()).select_from(ProfileView))
    assert views == 0


async def test_a_deleted_account_is_named_as_one_and_nothing_more(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id, woman_id = (await make_thread(man, woman)).id, woman.id
    await db.execute(
        update(User)
        .where(User.id == woman_id)
        .values(
            status=UserStatus.DELETED,
            deleted_requested_at=clock.now(),
            last_active_at=clock.now(),
        )
    )

    body = await _view(client, token, thread_id)

    assert body["other"] == {
        "id": str(woman_id),
        "first_name": None,
        "username": None,
        "main_photo_url": None,
        "shows_badge": False,
        "is_online": False,
        "deleted": True,
    }


async def test_the_opener_is_shown_free_and_the_send_takes_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id, man_id = (await make_thread(man, woman)).id, man.id

    assert await _price(client, token, thread_id) == 0
    await _send_at(client, token, thread_id, 0)
    assert await _price(client, token, thread_id) == 0
    assert await _spent(db, man_id) == 0


async def test_answering_her_is_shown_as_the_re_open_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """D-250: she opened and wrote; his answer is 2, then nothing."""
    man, token = await make_user(credits=10)
    woman, her_token = await make_user(Gender.FEMALE)
    thread_id, man_id = (await make_thread(woman, man)).id, man.id
    await _send_at(client, her_token, thread_id, 0)

    assert await _price(client, token, thread_id) == 2
    await _send_at(client, token, thread_id, 2)
    assert await _spent(db, man_id) == 2
    assert await _price(client, token, thread_id) == 0


async def test_writing_first_where_she_opened_is_shown_as_the_open(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=10)
    woman, _ = await make_user(Gender.FEMALE)
    thread_id, man_id = (await make_thread(woman, man)).id, man.id

    assert await _price(client, token, thread_id) == 5
    await _send_at(client, token, thread_id, 5)
    assert await _spent(db, man_id) == 5
    assert await _price(client, token, thread_id) == 0


async def test_every_private_message_of_his_is_shown_at_two(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=10)
    woman, her_token = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(woman, man, origin="dm")).id
    man_id, woman_id = man.id, woman.id
    await _send_at(client, her_token, thread_id, 0)

    for sent in (1, 2):
        assert await _price(client, token, thread_id) == 2
        await _send_at(client, token, thread_id, 2)
        assert await _spent(db, man_id) == 2 * sent
    assert await _price(client, her_token, thread_id) == 0
    assert await _spent(db, woman_id) == 0


async def test_a_re_open_he_paid_for_is_his_answer_too(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """D-641: he paid to re-open, so his answer costs nothing more."""
    man, token = await make_user(credits=10)
    woman, her_token = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(woman, man, status="expired")).id
    man_id = man.id
    await _send_at(client, her_token, thread_id, 0)
    reopened = await client.post(
        f"/v1/threads/{thread_id}/reopen",
        json={"shown_price": 2},
        headers={**bearer(token), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert reopened.status_code == 200, reopened.text

    assert await _price(client, token, thread_id) == 0
    await _send_at(client, token, thread_id, 0)
    # The re-open alone: his answer was in what he paid (D-641).
    assert await _spent(db, man_id) == 2


@pytest.mark.parametrize("origin", ["match", "dm"])
async def test_a_knot_is_shown_free(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    origin: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(woman, man, status="knotted", origin=origin)).id
    man_id = man.id

    assert await _price(client, token, thread_id) == 0
    await _send_at(client, token, thread_id, 0)
    assert await _spent(db, man_id) == 0


async def test_she_is_shown_nothing_to_pay_where_he_would_be(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """The mirror of his first message where she opened: she pays 0 (D-098)."""
    man, _ = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread_id, woman_id = (await make_thread(man, woman)).id, woman.id

    assert await _price(client, her_token, thread_id) == 0
    await _send_at(client, her_token, thread_id, 0)
    assert await _spent(db, woman_id) == 0


async def test_someone_elses_thread_is_not_found(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    _, stranger_token = await make_user()
    thread_id = (await make_thread(man, woman)).id

    response = await client.get(
        f"/v1/threads/{thread_id}", headers=bearer(stranger_token)
    )

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"


# --- Whether a gift and kudos can be given here (D-880) ---------------------------
#
# The conversation's gift button and kudos prompt read these, never the other
# person's profile, which records a view on every open (D-870). Each is the
# profile's own answer, and the answer of the endpoint it leads to.


async def _profile(client: AsyncClient, token: str, user_id: uuid.UUID) -> Any:
    response = await client.get(f"/v1/users/{user_id}", headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ("viewer", "viewed", "seeking", "gifts"),
    [
        (Gender.MALE, Gender.FEMALE, Seeking.MEN, True),
        (Gender.MALE, Gender.FEMALE, Seeking.EVERYONE, True),
        (Gender.MALE, Gender.FEMALE, Seeking.WOMEN, False),
        (Gender.MALE, Gender.MALE, Seeking.MEN, False),
        (Gender.FEMALE, Gender.MALE, Seeking.WOMEN, False),
        (Gender.FEMALE, Gender.FEMALE, Seeking.WOMEN, False),
    ],
)
async def test_can_gift_is_the_profiles_and_the_sends_own_answer(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    viewer: Gender,
    viewed: Gender,
    seeking: Seeking,
    gifts: bool,
) -> None:
    me, token = await person(db, make_user, viewer, seeking=Seeking.EVERYONE)
    them, _ = await person(db, make_user, viewed, at=north(1), seeking=seeking)
    thread_id, their_id = (await make_thread(me, them)).id, them.id

    assert (await _view(client, token, thread_id))["can_gift"] is gifts
    assert (await _profile(client, token, their_id))["can_gift"] is gifts
    assert await _gift_sent(client, token, their_id) is gifts


async def _gift_sent(client: AsyncClient, token: str, user_id: uuid.UUID) -> bool:
    response = await client.post(
        "/v1/gifts/send",
        json={"recipient_id": str(user_id), "gift_id": "coffee", "shown_price": 0},
        headers={**bearer(token), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code in (200, 404, 422), response.text
    return response.status_code == 200


async def test_a_gift_is_never_offered_across_a_block(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """A block hides the Thread itself: `NOT_FOUND`, so no gift is offered."""
    man, token = await person(db, make_user, Gender.MALE)
    woman, _ = await person(db, make_user, at=north(1))
    thread_id = (await make_thread(man, woman)).id
    assert (await _view(client, token, thread_id))["can_gift"] is True
    await block(db, woman, man)

    response = await client.get(f"/v1/threads/{thread_id}", headers=bearer(token))

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    ("mine", "gives", "state"),
    [(3, False, "too_early"), (5, False, "can_give"), (5, True, "given")],
)
async def test_kudos_is_the_profiles_and_post_kudos_own_answer(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    mine: int,
    gives: bool,
    state: str,
) -> None:
    man, token = await person(db, make_user, Gender.MALE)
    woman, _ = await person(db, make_user, at=north(1))
    woman_id = woman.id
    thread_id = (await _talked(db, make_thread, man, woman, mine=mine, theirs=1)).id
    if gives:
        assert (await _give(client, token, woman_id)).status_code == 201

    assert (await _view(client, token, thread_id))["kudos"] == state
    assert (await _profile(client, token, woman_id))["thread"]["kudos"] == state
    # What `POST /kudos` does with it: taken only where the view said so.
    taken = {"too_early": 422, "can_give": 201, "given": 409}[state]
    assert (await _give(client, token, woman_id)).status_code == taken
