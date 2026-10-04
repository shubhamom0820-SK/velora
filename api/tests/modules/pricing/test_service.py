"""`pricing.service.price_for()` and `charge()` (T-5.2, D-098, D-231, D-250),
each check in the order the service makes it.

Expected prices are written out here, never read from the migrations, so a wrong
value in a migration fails a test instead of agreeing with itself.
"""

from __future__ import annotations

import secrets
import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import Gender, LedgerReason
from app.core.errors import AppError
from app.core.security import normalize_phone
from app.modules.pricing import service
from app.modules.pricing.service import PricingMisuse
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet
from app.modules.wallet.rules import Ref, RefType
from tests.conftest import MakeUser, make_test_settings

# What a man pays, in Velas: D-097 to D-099, D-231 and D-250, the founder's.
PRICES = {
    LedgerReason.THREAD_OPEN: 5,
    LedgerReason.THREAD_REOPEN: 2,
    LedgerReason.THREAD_EXTEND: 10,
    LedgerReason.DM_OPEN: 8,
    LedgerReason.DM_MESSAGE: 2,
    LedgerReason.ALBUM_REQUEST: 1,
    LedgerReason.VOICE_UNLOCK: 5,
    # Survived by default, never decided (D-231, D-250).
    LedgerReason.SUPER_LIKE: 5,
    LedgerReason.LIKED_YOU_REVEAL: 20,
}
THREAD_OPEN = LedgerReason.THREAD_OPEN


def _thread() -> Ref:
    return Ref(RefType.THREAD, uuid.uuid4())


async def _no_gender(db: AsyncSession) -> User:
    """Signed up, and not yet past the gender step."""
    phone = normalize_phone(f"+9196{secrets.randbelow(10**8):08d}")
    account = await users_service.create_account(db, phone, make_test_settings())
    assert account.user.gender is None
    return account.user


async def _set(db: AsyncSession, action: LedgerReason, **values: Any) -> None:
    assignments = ", ".join(f"{column} = :{column}" for column in values)
    await db.execute(
        text(f"update action_prices set {assignments} where action = :action"),
        {**values, "action": action.value},
    )


async def _entries(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta).where(
            LedgerEntry.user_id == user_id
        )
    )
    return sorted((str(reason), delta) for reason, delta in rows)


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int | None:
    balance: int | None = await db.scalar(
        select(Wallet.balance).where(Wallet.user_id == user_id)
    )
    return balance


# --- price_for(): who pays what --------------------------------------------------


@pytest.mark.parametrize(("action", "price"), PRICES.items())
async def test_a_man_pays_the_rows_price(
    db: AsyncSession, make_user: MakeUser, action: LedgerReason, price: int
) -> None:
    man, _ = await make_user(Gender.MALE)

    assert await service.price_for(db, man, action) == price


@pytest.mark.parametrize("action", PRICES)
async def test_a_woman_pays_nothing_for_any_action(
    db: AsyncSession, make_user: MakeUser, action: LedgerReason
) -> None:
    woman, _ = await make_user(Gender.FEMALE)

    assert await service.price_for(db, woman, action) == 0


async def test_the_rows_are_exactly_the_tested_actions(db: AsyncSession) -> None:
    """An action priced in the database and missing above would go untested."""
    rows = set(await db.scalars(text("select action from action_prices")))

    assert rows == {action.value for action in PRICES}


async def test_a_user_with_no_gender_is_never_priced(db: AsyncSession) -> None:
    person = await _no_gender(db)

    with pytest.raises(PricingMisuse, match="no gender yet"):
        await service.price_for(db, person, THREAD_OPEN)


async def test_a_gender_nobody_has_named_is_never_priced(db: AsyncSession) -> None:
    """The check is an allowlist, man or woman, so a value added to the enum
    later raises as surely as none does. Only a value nobody has listed can
    tell an allowlist from "not None": every case written with today's two
    passes either way (D-084's lesson)."""
    someone = cast(User, SimpleNamespace(id=uuid.uuid4(), gender="never-named-2031"))
    await db.connection()  # inside the caller's transaction, as a charge is

    with pytest.raises(PricingMisuse, match="no gender yet"):
        await service.price_for(db, someone, THREAD_OPEN)


@pytest.mark.parametrize("gender", [Gender.MALE, Gender.FEMALE])
async def test_an_inactive_action_is_not_allowed_for_anyone(
    db: AsyncSession, make_user: MakeUser, gender: Gender
) -> None:
    user, _ = await make_user(gender)
    await _set(db, THREAD_OPEN, active=False)

    with pytest.raises(AppError) as refused:
        await service.price_for(db, user, THREAD_OPEN)

    assert (refused.value.code, refused.value.status) == ("NOT_ALLOWED", 422)


@pytest.mark.parametrize("gender", [Gender.MALE, Gender.FEMALE])
async def test_an_action_with_no_row_is_a_500_never_0(
    db: AsyncSession, make_user: MakeUser, gender: Gender
) -> None:
    """A woman too: were she priced 0 before the row is read, a misspelt or
    deleted action would be free for her and silent for everyone."""
    user, _ = await make_user(gender)
    await db.execute(text("delete from action_prices where action = 'thread_open'"))

    with pytest.raises(PricingMisuse, match="thread_open has no price"):
        await service.price_for(db, user, THREAD_OPEN)
    # Gifts are priced in `gifts`, never here (T-8.9).
    with pytest.raises(PricingMisuse, match="gift has no price"):
        await service.price_for(db, user, LedgerReason.GIFT)
    # Not an AppError, so the client is told only "Something went wrong".
    assert not issubclass(PricingMisuse, AppError)


async def test_the_price_is_read_fresh_every_time(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(Gender.MALE)
    assert await service.price_for(db, man, THREAD_OPEN) == 5

    await _set(db, THREAD_OPEN, credits=7)

    assert await service.price_for(db, man, THREAD_OPEN) == 7


async def test_price_for_refuses_outside_a_transaction(
    test_engine: AsyncEngine,
) -> None:
    """Its read belongs to the transaction that debits, so the charge is the
    price as it is now (02-ARCHITECTURE §9)."""
    man = cast(User, SimpleNamespace(id=uuid.uuid4(), gender=Gender.MALE))
    async with AsyncSession(test_engine) as outside:
        with pytest.raises(PricingMisuse, match="inside its caller's transaction"):
            await service.price_for(outside, man, THREAD_OPEN)


# --- charge(): debit only above 0 ------------------------------------------------


async def test_a_man_is_charged_the_price_now(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(Gender.MALE, credits=20)

    first = await service.charge(db, man, THREAD_OPEN, ref=_thread())
    await _set(db, THREAD_OPEN, credits=6)
    second = await service.charge(db, man, THREAD_OPEN, ref=_thread())

    assert first is not None and first.applied
    assert second is not None and second.applied
    assert (first.entry.delta, second.entry.delta) == (-5, -6)
    assert await _balance(db, man.id) == 9


async def test_a_woman_is_charged_nothing_and_no_row_is_written(
    db: AsyncSession, make_user: MakeUser
) -> None:
    woman, _ = await make_user(Gender.FEMALE)

    for action in PRICES:
        assert await service.charge(db, woman, action, ref=_thread()) is None

    assert await _entries(db, woman.id) == []
    assert await _balance(db, woman.id) == 0


async def test_a_price_of_0_debits_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """A debit of 0 raises (T-5.1), so an action made free by its row is
    skipped, not debited."""
    man, _ = await make_user(Gender.MALE, credits=10)
    await _set(db, THREAD_OPEN, credits=0)

    assert await service.charge(db, man, THREAD_OPEN, ref=_thread()) is None
    assert await _entries(db, man.id) == [("admin_grant", 10)]
    assert await _balance(db, man.id) == 10


async def test_a_charge_beyond_the_balance_writes_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(Gender.MALE, credits=3)

    with pytest.raises(AppError) as refused:
        await service.charge(db, man, THREAD_OPEN, ref=_thread())

    assert (refused.value.code, refused.value.status) == ("INSUFFICIENT_CREDITS", 402)
    assert refused.value.details == {"required": 5, "balance": 3}
    assert await _entries(db, man.id) == [("admin_grant", 3)]


async def test_an_inactive_action_charges_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(Gender.MALE, credits=10)
    await _set(db, THREAD_OPEN, active=False)

    with pytest.raises(AppError, match="isn't available"):
        await service.charge(db, man, THREAD_OPEN, ref=_thread())

    assert await _balance(db, man.id) == 10


async def test_extend_can_be_bought_again_for_one_thread(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Ten Velas for another 24 hours, as often as he likes (D-250): the
    caller names each purchase, so one Thread takes many."""
    man, _ = await make_user(Gender.MALE, credits=30)
    thread = _thread()

    for event in ("extend-1", "extend-2"):
        result = await service.charge(
            db, man, LedgerReason.THREAD_EXTEND, ref=thread, event=event
        )
        assert result is not None and result.applied

    assert await _entries(db, man.id) == [
        ("admin_grant", 30),
        ("thread_extend", -10),
        ("thread_extend", -10),
    ]


async def test_a_private_message_is_charged_once(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Each private message after the first costs 2, once, by its own id
    (D-251): a retry finds the first charge."""
    man, _ = await make_user(Gender.MALE, credits=10)
    message = Ref(RefType.MESSAGE, uuid.uuid4())

    first = await service.charge(db, man, LedgerReason.DM_MESSAGE, ref=message)
    again = await service.charge(db, man, LedgerReason.DM_MESSAGE, ref=message)

    assert first is not None and first.applied
    assert again is not None and not again.applied
    assert await _balance(db, man.id) == 8
