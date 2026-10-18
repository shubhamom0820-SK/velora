"""The ledger audit (T-9.9): every way Velas leave a man's wallet, each with
the same three tests, through the API as the app takes them.

- **A man** pays once: exactly one new ledger entry among everyone the action
  touches, his, with the reason, the price and the ref, and his balance down by
  the price; and the action happened.
- **A woman** pays nothing (06-TESTING's critical 6, D-098): her outcome as
  the rules give it, free or refused, and no ledger entry for anyone.
- **Too few Velas** buys nothing: refused, nothing in the ledger, no balance
  moved, nothing the action writes written, no notification, nothing
  published.

Each price is the plan's literal (D-004, D-098, D-231, D-016's coffee), never
read from the code, so a changed price turns these red. `SPENDS` holds every
debit reason in `wallet/rules.py` but those `EXEMPT` names, and
`test_every_debit_of_velas_has_its_three_tests` holds that, both ways: a new
debit can't land without its row (T-9.9, the founder's answer of 14 October
2026).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, LedgerReason, MessageKind
from app.modules.album.models import AlbumRequest
from app.modules.gifts.models import GiftSend
from app.modules.matches.models import Match
from app.modules.messages.models import Message, MessageUnlock
from app.modules.notifications.models import Notification
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles.models import Profile
from app.modules.swipes.models import LikedYouReveal, Swipe
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet
from app.modules.wallet.rules import RULES, Direction
from tests.conftest import MakeThread, MakeUser
from tests.modules.admin.support import ADMIN, REASON, audits, staff
from tests.modules.album.support import album_of
from tests.modules.discovery.support import HERE, bearer, error, north, person, swipe
from tests.modules.gifts.support import set_config

pytestmark = pytest.mark.usefixtures("test_redis")

# Debits that aren't a purchase, so the three tests don't fit them: named, with
# why, and where their own tests are.
EXEMPT: dict[LedgerReason, str] = {
    LedgerReason.PURCHASE_REVERSAL: (
        "D-520: a refund or chargeback taking a payment's Velas back, not "
        "something he buys; it never refuses, taking the balance down to 0, "
        "and no woman holds Velas. tests/modules/payments/test_reversals.py"
    ),
}


# --- The table ----------------------------------------------------------------------


@dataclass(frozen=True)
class World:
    db: AsyncSession
    client: AsyncClient
    make_user: MakeUser
    make_thread: MakeThread


@dataclass(frozen=True)
class Act:
    """One action, set up and ready to send. `send(shown)` sends it with
    `shown` as the price its screen showed (P-56); `written()` reads, fresh,
    what it writes; `ref()` is what his entry must name, read after it ran."""

    payer: uuid.UUID
    others: tuple[uuid.UUID, ...]
    send: Callable[[int], Awaitable[Response]]
    written: Callable[[], Awaitable[object]]
    ref: Callable[[], Awaitable[tuple[str, uuid.UUID]]]


Arrange = Callable[[World, Gender, int], Awaitable[Act]]


@dataclass(frozen=True)
class Her:
    """A woman's outcome: `status`, the error `code` when refused, and
    whether the action wrote anything (a voice note is never locked for her,
    so hearing one writes nothing)."""

    status: int
    code: str | None = None
    wrote: bool = False


FREE = Her(200, wrote=True)
HEARD = Her(200)
REFUSED = Her(422, "NOT_ALLOWED")


@dataclass(frozen=True)
class Spend:
    id: str
    reason: LedgerReason
    price: int
    arrange: Arrange
    her: Her
    # Too few Velas: the status, code and details. The wallet's 402 unless
    # the action checks the balance first.
    short_status: int = 402
    short_code: str = "INSUFFICIENT_CREDITS"
    short_details: dict[str, Any] | None = None

    def details_when_short(self) -> dict[str, Any]:
        if self.short_details is not None:
            return self.short_details
        return {"required": self.price, "balance": self.price - 1}


def _other(gender: Gender) -> Gender:
    return Gender.FEMALE if gender is Gender.MALE else Gender.MALE


def _fresh(query: Any) -> Any:
    return query.execution_options(populate_existing=True)


async def _placed(db: AsyncSession, user: User) -> None:
    """On the grid at `HERE`, as `person` places one."""
    profile = await db.get(Profile, user.id)
    assert profile is not None
    profile.location = profiles_repository.point(*HERE)
    await db.flush()


async def _thread_ids(db: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> list[uuid.UUID]:
    low, high = sorted((a, b))
    rows = await db.scalars(
        _fresh(
            select(Thread.id).where(Thread.user_low == low, Thread.user_high == high)
        )
    )
    return list(rows)


async def _one_thread(db: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> uuid.UUID:
    [thread_id] = await _thread_ids(db, a, b)
    return thread_id


async def _thread_state(db: AsyncSession, thread_id: uuid.UUID) -> object:
    row = (
        await db.execute(
            _fresh(
                select(Thread.status, Thread.expires_at, Thread.expiry_warned_at).where(
                    Thread.id == thread_id
                )
            )
        )
    ).one()
    return tuple(row)


async def _messages_by(
    db: AsyncSession, thread_id: uuid.UUID, sender_id: uuid.UUID
) -> list[uuid.UUID]:
    rows = await db.scalars(
        _fresh(
            select(Message.id)
            .where(Message.thread_id == thread_id, Message.sender_id == sender_id)
            .order_by(Message.created_at, Message.id)
        )
    )
    return list(rows)


async def _text(
    client: AsyncClient, token: str, thread_id: uuid.UUID, shown: int
) -> Response:
    return await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "kind": "text",
            "body": "Hello",
            "shown_price": shown,
        },
        headers=bearer(token),
    )


# --- Opening a Thread ---------------------------------------------------------------


async def _open_from_a_match(w: World, gender: Gender, credits: int) -> Act:
    payer, token = await w.make_user(gender, credits=credits)
    other, _ = await w.make_user(_other(gender))
    payer_id, other_id = payer.id, other.id
    low, high = sorted((payer_id, other_id))
    match = Match(user_low=low, user_high=high)
    w.db.add(match)
    await w.db.flush()
    match_id = match.id

    async def send(shown: int) -> Response:
        return await w.client.post(
            "/v1/threads",
            json={"match_id": str(match_id), "shown_price": shown},
            headers=bearer(token),
        )

    async def written() -> object:
        linked = await w.db.scalar(
            _fresh(select(Match.thread_id).where(Match.id == match_id))
        )
        return (await _thread_ids(w.db, payer_id, other_id), linked)

    async def ref() -> tuple[str, uuid.UUID]:
        return "thread", await _one_thread(w.db, payer_id, other_id)

    return Act(payer_id, (other_id,), send, written, ref)


async def _private_message(w: World, gender: Gender, credits: int) -> Act:
    payer, token = await w.make_user(gender, credits=credits)
    other, _ = await w.make_user(_other(gender))
    payer_id, other_id = payer.id, other.id

    async def send(shown: int) -> Response:
        return await w.client.post(
            "/v1/threads",
            json={
                "user_id": str(other_id),
                "first_message": "Hello",
                "shown_price": shown,
            },
            headers=bearer(token),
        )

    async def written() -> object:
        ids = await _thread_ids(w.db, payer_id, other_id)
        return ids, [await _messages_by(w.db, t, payer_id) for t in ids]

    async def ref() -> tuple[str, uuid.UUID]:
        return "thread", await _one_thread(w.db, payer_id, other_id)

    return Act(payer_id, (other_id,), send, written, ref)


def _answering(*, she_wrote: bool) -> Arrange:
    """His first message in a Thread from a match the other opened: the open's
    price, or the re-open's once she has written (D-551, D-641)."""

    async def arrange(w: World, gender: Gender, credits: int) -> Act:
        payer, token = await w.make_user(gender, credits=credits)
        other, _ = await w.make_user(_other(gender))
        payer_id, other_id = payer.id, other.id
        thread = await w.make_thread(other, payer, messages=1 if she_wrote else 0)
        thread_id = thread.id

        async def send(shown: int) -> Response:
            return await _text(w.client, token, thread_id, shown)

        async def written() -> object:
            return (
                await _messages_by(w.db, thread_id, payer_id),
                await _thread_state(w.db, thread_id),
            )

        async def ref() -> tuple[str, uuid.UUID]:
            return "thread", thread_id

        return Act(payer_id, (other_id,), send, written, ref)

    return arrange


# --- Buying time ----------------------------------------------------------------------


def _buying(what: str, status: str) -> Arrange:
    """`POST /v1/threads/{id}/reopen` or `/extend` on a Thread he opened."""

    async def arrange(w: World, gender: Gender, credits: int) -> Act:
        payer, token = await w.make_user(gender, credits=credits)
        other, _ = await w.make_user(_other(gender))
        payer_id, other_id = payer.id, other.id
        thread = await w.make_thread(payer, other, status=status)
        thread_id = thread.id

        async def send(shown: int) -> Response:
            return await w.client.post(
                f"/v1/threads/{thread_id}/{what}",
                json={"shown_price": shown},
                headers={**bearer(token), "Idempotency-Key": uuid.uuid4().hex},
            )

        async def written() -> object:
            return await _thread_state(w.db, thread_id)

        async def ref() -> tuple[str, uuid.UUID]:
            return "thread", thread_id

        return Act(payer_id, (other_id,), send, written, ref)

    return arrange


# --- In a Thread ------------------------------------------------------------------------


async def _each_private_message(w: World, gender: Gender, credits: int) -> Act:
    """A message in a private Thread the other opened: every one of his is
    priced, the first included, since hers opened it (D-251)."""
    payer, token = await w.make_user(gender, credits=credits)
    other, _ = await w.make_user(_other(gender))
    payer_id, other_id = payer.id, other.id
    thread = await w.make_thread(other, payer, origin="dm")
    thread_id = thread.id

    async def send(shown: int) -> Response:
        return await _text(w.client, token, thread_id, shown)

    async def written() -> object:
        return await _messages_by(w.db, thread_id, payer_id)

    async def ref() -> tuple[str, uuid.UUID]:
        [message_id] = await _messages_by(w.db, thread_id, payer_id)
        return "message", message_id

    return Act(payer_id, (other_id,), send, written, ref)


async def _voice_unlock(w: World, gender: Gender, credits: int) -> Act:
    payer, token = await w.make_user(gender, credits=credits)
    other, _ = await w.make_user(_other(gender))
    payer_id, other_id = payer.id, other.id
    thread = await w.make_thread(payer, other)
    note = Message(
        thread_id=thread.id,
        sender_id=other_id,
        kind=MessageKind.VOICE,
        media_key=f"voice/{thread.id}/{uuid.uuid4()}.webm",
        duration_s=12,
        client_msg_id=uuid.uuid4(),
    )
    w.db.add(note)
    await w.db.flush()
    note_id = note.id

    async def send(shown: int) -> Response:
        return await w.client.post(
            f"/v1/messages/{note_id}/unlock",
            json={"shown_price": shown},
            headers=bearer(token),
        )

    async def written() -> object:
        return await w.db.scalar(
            _fresh(
                select(func.count())
                .select_from(MessageUnlock)
                .where(MessageUnlock.message_id == note_id)
            )
        )

    async def ref() -> tuple[str, uuid.UUID]:
        return "message", note_id

    return Act(payer_id, (other_id,), send, written, ref)


# --- Profiles -------------------------------------------------------------------------------


async def _album_request(w: World, gender: Gender, credits: int) -> Act:
    payer, token = await w.make_user(gender, credits=credits)
    owner, _ = await w.make_user(_other(gender))
    payer_id, owner_id = payer.id, owner.id
    await album_of(w.db, owner)

    async def send(shown: int) -> Response:
        return await w.client.post(
            "/v1/album-requests",
            json={"owner_id": str(owner_id), "shown_price": shown},
            headers=bearer(token),
        )

    async def requests() -> list[uuid.UUID]:
        rows = await w.db.scalars(
            _fresh(
                select(AlbumRequest.id).where(
                    AlbumRequest.requester_id == payer_id,
                    AlbumRequest.owner_id == owner_id,
                )
            )
        )
        return list(rows)

    async def ref() -> tuple[str, uuid.UUID]:
        [request_id] = await requests()
        return "album_request", request_id

    return Act(payer_id, (owner_id,), send, requests, ref)


async def _super_like(w: World, gender: Gender, credits: int) -> Act:
    payer, token = await w.make_user(gender, credits=credits)
    await _placed(w.db, payer)
    other, _ = await person(w.db, w.make_user, _other(gender), at=north(1))
    payer_id, other_id = payer.id, other.id

    async def send(shown: int) -> Response:
        return await w.client.post(
            "/v1/swipes",
            json={"target_id": str(other_id), "dir": "super", "shown_price": shown},
            headers=bearer(token),
        )

    async def written() -> object:
        rows = await w.db.scalars(
            _fresh(select(Swipe.target_id).where(Swipe.swiper_id == payer_id))
        )
        return list(rows)

    async def ref() -> tuple[str, uuid.UUID]:
        return "user", other_id

    return Act(payer_id, (other_id,), send, written, ref)


async def _liked_you_reveal(w: World, gender: Gender, credits: int) -> Act:
    payer, token = await w.make_user(gender, credits=credits)
    await _placed(w.db, payer)
    other, _ = await person(w.db, w.make_user, _other(gender), at=north(2))
    await swipe(w.db, other, payer, "like")
    payer_id, other_id = payer.id, other.id
    listed = await w.client.get("/v1/likes", headers=bearer(token))
    assert listed.status_code == 200, listed.text
    [item] = listed.json()["items"]
    handle = item["handle"]

    async def send(shown: int) -> Response:
        return await w.client.post(
            f"/v1/likes/{handle}/reveal",
            json={"shown_price": shown},
            headers=bearer(token),
        )

    async def written() -> object:
        rows = await w.db.scalars(
            _fresh(
                select(LikedYouReveal.liker_id).where(
                    LikedYouReveal.viewer_id == payer_id
                )
            )
        )
        return list(rows)

    async def ref() -> tuple[str, uuid.UUID]:
        return "user", other_id

    return Act(payer_id, (other_id,), send, written, ref)


# --- Gifts and corrections ---------------------------------------------------------------


async def _gift(w: World, gender: Gender, credits: int) -> Act:
    """A coffee, past the week's free sends (none here; D-231)."""
    await set_config(w.db, "gift_free_weekly_limit", 0)
    payer, token = await w.make_user(gender, credits=credits)
    other, _ = await w.make_user(_other(gender))
    payer_id, other_id = payer.id, other.id

    async def send(shown: int) -> Response:
        return await w.client.post(
            "/v1/gifts/send",
            json={
                "recipient_id": str(other_id),
                "gift_id": "coffee",
                "shown_price": shown,
            },
            headers={**bearer(token), "Idempotency-Key": uuid.uuid4().hex},
        )

    async def sends() -> list[uuid.UUID]:
        rows = await w.db.scalars(
            _fresh(select(GiftSend.id).where(GiftSend.sender_id == payer_id))
        )
        return list(rows)

    async def ref() -> tuple[str, uuid.UUID]:
        [send_id] = await sends()
        return "gift_send", send_id

    return Act(payer_id, (other_id,), send, sends, ref)


CORRECTION = 4  # Velas an admin takes back here; the man's "price"


async def _admin_correction(w: World, gender: Gender, credits: int) -> Act:
    """`POST /v1/admin/users/{id}/credits` with a negative delta (T-9.5,
    D-923): the man pays nothing he chose, but Velas leave his wallet, so it
    has its three tests too. Nothing is shown to him, so `shown` is unused."""
    admin_id, admin_token = await staff(w.make_user)
    payer, _ = await w.make_user(gender, credits=credits)
    payer_id = payer.id

    async def send(shown: int) -> Response:
        return await w.client.post(
            f"{ADMIN}/users/{payer_id}/credits",
            json={"delta": -CORRECTION, "reason": REASON},
            headers={
                **bearer(admin_token),
                "Idempotency-Key": f"key-{uuid.uuid4().hex[:12]}",
            },
        )

    async def written() -> object:
        return [a.id for a in await audits(w.db, admin_id, "user.credits")]

    async def ref() -> tuple[str, uuid.UUID]:
        [audit] = await audits(w.db, admin_id, "user.credits")
        return "audit_log", audit.id

    return Act(payer_id, (admin_id,), send, written, ref)


SPENDS: Sequence[Spend] = (
    Spend("thread_open", LedgerReason.THREAD_OPEN, 5, _open_from_a_match, FREE),
    Spend(
        "thread_open-answering",
        LedgerReason.THREAD_OPEN,
        5,
        _answering(she_wrote=False),
        FREE,
    ),
    Spend("dm_open", LedgerReason.DM_OPEN, 8, _private_message, FREE),
    Spend(
        "thread_reopen",
        LedgerReason.THREAD_REOPEN,
        2,
        _buying("reopen", "expired"),
        REFUSED,
    ),
    Spend(
        "thread_reopen-answering",
        LedgerReason.THREAD_REOPEN,
        2,
        _answering(she_wrote=True),
        FREE,
    ),
    Spend(
        "thread_extend",
        LedgerReason.THREAD_EXTEND,
        10,
        _buying("extend", "active"),
        REFUSED,
    ),
    Spend("dm_message", LedgerReason.DM_MESSAGE, 2, _each_private_message, FREE),
    Spend("voice_unlock", LedgerReason.VOICE_UNLOCK, 5, _voice_unlock, HEARD),
    Spend("album_request", LedgerReason.ALBUM_REQUEST, 1, _album_request, FREE),
    Spend("super_like", LedgerReason.SUPER_LIKE, 5, _super_like, FREE),
    Spend(
        "liked_you_reveal", LedgerReason.LIKED_YOU_REVEAL, 1, _liked_you_reveal, FREE
    ),
    Spend("gift", LedgerReason.GIFT, 5, _gift, REFUSED),
    Spend(
        "admin_correction",
        LedgerReason.ADMIN_CORRECTION,
        CORRECTION,
        _admin_correction,
        REFUSED,
        # The panel checks the balance before the wallet is asked (D-923).
        short_status=422,
        short_code="NOT_ALLOWED",
        short_details={"why": "balance", "balance": CORRECTION - 1},
    ),
)


# --- Reading what moved -------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    id: uuid.UUID
    user_id: uuid.UUID
    reason: LedgerReason
    delta: int
    ref_type: str | None
    ref_id: uuid.UUID | None


async def _ledger(db: AsyncSession, user_ids: Sequence[uuid.UUID]) -> list[Entry]:
    rows = await db.execute(
        _fresh(
            select(
                LedgerEntry.id,
                LedgerEntry.user_id,
                LedgerEntry.reason,
                LedgerEntry.delta,
                LedgerEntry.ref_type,
                LedgerEntry.ref_id,
            )
            .where(LedgerEntry.user_id.in_(user_ids))
            .order_by(LedgerEntry.created_at, LedgerEntry.id)
        )
    )
    return [Entry(*row) for row in rows]


async def _balances(
    db: AsyncSession, user_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        _fresh(
            select(Wallet.user_id, Wallet.balance).where(Wallet.user_id.in_(user_ids))
        )
    )
    return {user_id: balance for user_id, balance in rows}


async def _notes(db: AsyncSession, user_ids: Sequence[uuid.UUID]) -> int:
    count = await db.scalar(
        _fresh(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id.in_(user_ids))
        )
    )
    return count or 0


@pytest.fixture
def world(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> World:
    return World(db, client, make_user, make_thread)


BY_ID = pytest.mark.parametrize("spend", SPENDS, ids=[s.id for s in SPENDS])


# --- The three tests ----------------------------------------------------------------------


@pytest.mark.critical  # rule 5: one action, one entry, at the row's price
@BY_ID
async def test_a_man_pays_once_at_the_price(
    world: World, db: AsyncSession, spend: Spend
) -> None:
    act = await spend.arrange(world, Gender.MALE, spend.price + 3)
    everyone = (act.payer, *act.others)
    before = {e.id for e in await _ledger(db, everyone)}
    balances = await _balances(db, everyone)
    written = await act.written()

    response = await act.send(spend.price)

    assert response.status_code in (200, 204), response.text
    new = [e for e in await _ledger(db, everyone) if e.id not in before]
    ref_type, ref_id = await act.ref()
    assert [(e.user_id, e.reason, e.delta, e.ref_type, e.ref_id) for e in new] == [
        (act.payer, spend.reason, -spend.price, ref_type, ref_id)
    ]
    assert await _balances(db, everyone) == {
        **balances,
        act.payer: balances[act.payer] - spend.price,
    }
    assert await act.written() != written, "the Velas bought nothing"


@pytest.mark.critical  # 06-TESTING's 6: women never pay
@BY_ID
async def test_a_woman_pays_nothing(
    world: World, db: AsyncSession, spend: Spend
) -> None:
    act = await spend.arrange(world, Gender.FEMALE, 0)
    everyone = (act.payer, *act.others)
    before = await _ledger(db, everyone)
    balances = await _balances(db, everyone)
    written = await act.written()

    response = await act.send(0)

    assert response.status_code == spend.her.status, response.text
    if spend.her.code is not None:
        assert error(response)["code"] == spend.her.code
    assert await _ledger(db, everyone) == before
    assert await _ledger(db, (act.payer,)) == []
    assert await _balances(db, everyone) == balances
    if spend.her.wrote:
        assert await act.written() != written, "free, so it must have happened"
    else:
        assert await act.written() == written


@pytest.mark.critical  # rule 5: a refused debit takes what it bought back with it
@BY_ID
async def test_too_few_velas_buys_nothing(
    world: World,
    db: AsyncSession,
    spend: Spend,
    published: list[events.Event],
) -> None:
    act = await spend.arrange(world, Gender.MALE, spend.price - 1)
    everyone = (act.payer, *act.others)
    before = await _ledger(db, everyone)
    balances = await _balances(db, everyone)
    written = await act.written()
    notes = await _notes(db, everyone)
    sent_before = len(published)

    response = await act.send(spend.price)

    assert response.status_code == spend.short_status, response.text
    assert error(response)["code"] == spend.short_code
    assert error(response)["details"] == spend.details_when_short()
    assert await _ledger(db, everyone) == before
    assert await _balances(db, everyone) == balances
    assert await act.written() == written
    assert await _notes(db, everyone) == notes
    assert published[sent_before:] == []


# --- The guard ------------------------------------------------------------------------------


def test_every_debit_of_velas_has_its_three_tests() -> None:
    """Exactly the debit reasons, both ways: one `rules.py` gains (T-9.5's
    `admin_correction` was the first) is red until it has a row here or a
    named exemption; a row for anything but a debit is red too."""
    debits = {
        reason for reason, rule in RULES.items() if rule.direction is Direction.DEBIT
    }
    audited = {spend.reason for spend in SPENDS}

    assert audited | set(EXEMPT) == debits
    assert audited & set(EXEMPT) == set()
    assert len({spend.id for spend in SPENDS}) == len(SPENDS)
