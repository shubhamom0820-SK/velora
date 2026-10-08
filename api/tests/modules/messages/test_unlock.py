"""Unlocking a voice note and fetching its file (T-7.9, D-621): a man pays 5
once (D-010, `voice_unlock`), at the price he was shown (P-56); its sender and
a woman hear it free; the link is signed for 10 minutes, and never reaches
anyone the Thread isn't theirs, nor across a block."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, MessageKind, ThreadStatus
from app.modules.messages.models import Message, MessageUnlock
from app.modules.safety.models import Block
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("test_redis")

PRIVATE = make_test_settings().R2_BUCKET_PRIVATE
PRICE = 5  # D-004's voice_unlock


async def _voice_note(db: AsyncSession, thread: Thread, sender: User) -> Message:
    row = Message(
        thread_id=thread.id,
        sender_id=sender.id,
        kind=MessageKind.VOICE,
        media_key=f"voice/{thread.id}/{uuid.uuid4()}.webm",
        duration_s=12,
        client_msg_id=uuid.uuid4(),
    )
    db.add(row)
    await db.flush()
    return row


async def _unlock(
    client: AsyncClient, token: str, message_id: uuid.UUID, **body: Any
) -> Response:
    return await client.post(
        f"/v1/messages/{message_id}/unlock", json=body, headers=bearer(token)
    )


async def _media(client: AsyncClient, token: str, message_id: uuid.UUID) -> Response:
    return await client.get(f"/v1/messages/{message_id}/media", headers=bearer(token))


def _url(media_key: str) -> str:
    return f"fake-storage://{PRIVATE}/{media_key}?method=GET&ttl=600"


async def _charges(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int, Any]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta, LedgerEntry.ref_id)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant")
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
    )
    return [(str(reason), delta, ref) for reason, delta, ref in rows]


async def _unlocks(db: AsyncSession, message_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(MessageUnlock)
        .where(MessageUnlock.message_id == message_id)
    )
    return count or 0


async def _setting(
    db: AsyncSession,
    make_user: MakeUser,
    make_thread: MakeThread,
    *,
    credits: int = 10,
    status: ThreadStatus = ThreadStatus.ACTIVE,
) -> tuple[uuid.UUID, str, uuid.UUID, str, uuid.UUID, uuid.UUID, str]:
    """(man, his token, woman, her token, Thread, her voice note, its key)."""
    man, man_token = await make_user(credits=credits)
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status=status)
    note = await _voice_note(db, thread, woman)
    assert note.media_key is not None
    return man.id, man_token, woman.id, token, thread.id, note.id, note.media_key


# --- Unlocking ------------------------------------------------------------------


async def test_he_pays_five_once_and_hears_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man_id, man_token, _, _, thread_id, note_id, key = await _setting(
        db, make_user, make_thread
    )

    locked = await client.get(
        f"/v1/threads/{thread_id}/messages", headers=bearer(man_token)
    )
    assert locked.json()["items"][0]["locked"] is True
    response = await _unlock(client, man_token, note_id, shown_price=PRICE)

    assert response.status_code == 200, response.text
    assert response.json() == {"url": _url(key)}
    assert await _charges(db, man_id) == [("voice_unlock", -PRICE, note_id)]
    assert await _unlocks(db, note_id) == 1
    listed = await client.get(
        f"/v1/threads/{thread_id}/messages", headers=bearer(man_token)
    )
    assert listed.json()["items"][0]["locked"] is False
    media = await _media(client, man_token, note_id)
    assert media.status_code == 200
    assert media.json() == {"url": _url(key)}


async def test_unlocking_again_charges_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man_id, man_token, _, _, _, note_id, key = await _setting(
        db, make_user, make_thread
    )

    first = await _unlock(client, man_token, note_id, shown_price=PRICE)
    # A retry whose screen now shows it unlocked, with no price: nothing to pay.
    again = await _unlock(client, man_token, note_id)

    assert first.status_code == again.status_code == 200, again.text
    assert again.json() == {"url": _url(key)}
    assert await _charges(db, man_id) == [("voice_unlock", -PRICE, note_id)]
    assert await _unlocks(db, note_id) == 1


@pytest.mark.parametrize("body", [{}, {"shown_price": 4}, {"shown_price": 0}])
async def test_a_price_he_wasnt_shown_is_refused_and_nothing_written(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    body: dict[str, Any],
) -> None:
    """P-56, D-600: `shown_price` missing is 0, so it is refused too."""
    man_id, man_token, _, _, _, note_id, _ = await _setting(db, make_user, make_thread)

    response = await _unlock(client, man_token, note_id, **body)

    assert response.status_code == 409
    found = error(response)
    assert found["code"] == "PRICE_CHANGED"
    assert found["details"] == {"price": PRICE}
    assert await _charges(db, man_id) == []
    assert await _unlocks(db, note_id) == 0


async def test_without_the_velas_nothing_is_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man_id, man_token, _, _, _, note_id, _ = await _setting(
        db, make_user, make_thread, credits=4
    )

    response = await _unlock(client, man_token, note_id, shown_price=PRICE)

    assert response.status_code == 402
    found = error(response)
    assert found["code"] == "INSUFFICIENT_CREDITS"
    assert found["details"] == {"required": PRICE, "balance": 4}
    assert await _charges(db, man_id) == []
    assert await _unlocks(db, note_id) == 0
    media = await _media(client, man_token, note_id)
    assert error(media)["code"] == "NOT_ALLOWED"


async def test_an_expired_thread_is_no_bar(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """Unlocking isn't a send (D-097, the founder, 8 October 2026)."""
    man_id, man_token, _, _, _, note_id, _ = await _setting(
        db, make_user, make_thread, status=ThreadStatus.EXPIRED
    )

    response = await _unlock(client, man_token, note_id, shown_price=PRICE)

    assert response.status_code == 200, response.text
    assert await _charges(db, man_id) == [("voice_unlock", -PRICE, note_id)]


async def test_its_sender_hears_it_free_with_nothing_recorded(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    _, _, _, token, _, note_id, key = await _setting(db, make_user, make_thread)

    unlocked = await _unlock(client, token, note_id)
    media = await _media(client, token, note_id)

    assert unlocked.json() == media.json() == {"url": _url(key)}
    assert await _unlocks(db, note_id) == 0


async def test_a_woman_receiving_one_hears_it_free_with_nothing_recorded(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    sender, _ = await make_user(Gender.FEMALE)
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(sender, woman)
    note = await _voice_note(db, thread, sender)
    note_id, key = note.id, note.media_key
    assert key is not None

    media = await _media(client, token, note_id)
    unlocked = await _unlock(client, token, note_id)

    assert media.json() == unlocked.json() == {"url": _url(key)}
    assert await _unlocks(db, note_id) == 0


# --- Never theirs ---------------------------------------------------------------


async def test_a_text_or_anyone_elses_note_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, man_token = await make_user(credits=10)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, messages=1)
    text_id = await db.scalar(select(Message.id).where(Message.thread_id == thread.id))
    assert text_id is not None
    other_man, _ = await make_user()
    elsewhere = await make_thread(other_man, woman)
    theirs = await _voice_note(db, elsewhere, woman)
    man_id, theirs_id = man.id, theirs.id

    for message_id in (text_id, theirs_id, uuid.uuid4()):
        for response in (
            await _unlock(client, man_token, message_id, shown_price=PRICE),
            await _media(client, man_token, message_id),
        ):
            assert response.status_code == 404, message_id
            assert error(response)["code"] == "NOT_FOUND"
    assert await _charges(db, man_id) == []


@pytest.mark.parametrize("by_him", [True, False])
async def test_across_a_block_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    by_him: bool,
) -> None:
    man_id, man_token, woman_id, _, _, note_id, _ = await _setting(
        db, make_user, make_thread
    )
    blocker, blocked = (man_id, woman_id) if by_him else (woman_id, man_id)
    db.add(Block(blocker_id=blocker, blocked_id=blocked))
    await db.flush()

    for response in (
        await _unlock(client, man_token, note_id, shown_price=PRICE),
        await _media(client, man_token, note_id),
    ):
        assert response.status_code == 404
        assert error(response)["code"] == "NOT_FOUND"
    assert await _charges(db, man_id) == []


async def test_locked_its_file_is_not_allowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    _, man_token, _, _, _, note_id, _ = await _setting(db, make_user, make_thread)

    response = await _media(client, man_token, note_id)

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    assert "url" not in response.text


async def test_another_mans_unlock_opens_nothing_for_him(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """An unlock is the man's who paid: one row per (man, note)."""
    _, man_token, _, _, _, note_id, _ = await _setting(db, make_user, make_thread)
    other, _ = await make_user()
    db.add(MessageUnlock(user_id=other.id, message_id=note_id))
    await db.flush()

    response = await _media(client, man_token, note_id)

    assert error(response)["code"] == "NOT_ALLOWED"
