"""What an action costs, and the one way a priced action is paid for (T-5.2).

Prices are data (D-004, D-098): a row of `action_prices`, keyed by the debit
reason it is charged under, and changed by a row, never a deploy. Men pay the
row's value; women pay nothing, anywhere (D-098). No charging path for women
exists: none enabled, and none disabled in the code.

`price_for()` reads the row fresh, inside the caller's transaction, the one
that debits, so a charge is always the price as it is now (02-ARCHITECTURE §9).
There is no cache: P-47 puts any cache on the app, and P-50 adds one only where
something is measured slow. In this order:

1. Refuse to run outside a transaction.
2. Know the user's gender, or raise: a user with none can't have reached a
   priced action, so pricing for them is a bug, never a 0.
3. Read the row. None is a 500: a price is never 0 by default, for a woman
   either, or a misspelt action would quietly be free.
4. An inactive row is `NOT_ALLOWED`: the action is switched off, for everyone.
5. A woman pays 0; a man pays the row's value.

`charge()` prices the action, refuses it with `PRICE_CHANGED` when the price
isn't the one the person was shown (P-56, D-600), and debits only above 0,
since a debit of 0 raises. The shown price is compared, never charged: what is
debited is always the row's price (rule 6). `shown` is a required argument, so
a new paid action can't forget to compare. It and gift sending (T-8.9, priced from `gifts`) are the only callers
of `wallet.service.debit()`, so no literal price can reach it;
tests/modules/pricing/test_debit_callers.py holds that, as an allowlist, and
`debit()` itself refuses any other caller when it runs (P-152, D-651).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, LedgerReason
from app.core.errors import AppError
from app.modules.pricing import repository
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref
from app.modules.wallet.service import LedgerResult


class PricingMisuse(Exception):
    """A caller broke pricing's contract, or a price row is missing: a bug,
    never the user's doing, so it reaches them as a 500."""


async def price_for(session: AsyncSession, user: User, action: LedgerReason) -> int:
    """What `action` costs `user` now, in Velas."""
    if not session.in_transaction():
        raise PricingMisuse(
            "price_for() reads inside its caller's transaction, the one that debits"
        )
    if user.gender not in (Gender.MALE, Gender.FEMALE):
        raise PricingMisuse("this user has no gender yet, so nothing has a price")
    row = await repository.price_row(session, action.value)
    if row is None:
        raise PricingMisuse(f"{action} has no price: never 0 by default (T-5.2)")
    credits, active = row
    if not active:
        raise AppError("NOT_ALLOWED", "This isn't available right now.", status=422)
    return credits if user.gender is Gender.MALE else 0


def price_changed(price: int) -> AppError:
    """The price isn't the one the screen showed: nothing was charged, and
    `details.price` is what it costs now, for the screen to show again."""
    return AppError(
        "PRICE_CHANGED",
        "The price changed. Check it and try again.",
        status=409,
        details={"price": price},
    )


async def charge(
    session: AsyncSession,
    user: User,
    action: LedgerReason,
    *,
    shown: int,
    ref: Ref | None = None,
    event: str | None = None,
) -> LedgerResult | None:
    """Pay for `action` at its price now, in the caller's transaction, if it is
    the price `user` was shown (`shown_price`, 0 when the request sent none).

    `PRICE_CHANGED` (409) when they differ, before anything is debited. None
    when the price is 0, a woman's always: nothing is debited, and no ledger
    row is written. Otherwise `wallet.service.debit()`'s result, or its
    `INSUFFICIENT_CREDITS` (402).
    """
    price = await price_for(session, user, action)
    if price != shown:
        raise price_changed(price)
    if price == 0:
        return None
    return await wallet_service.debit(
        session, user.id, price, action, ref=ref, event=event
    )


async def active_prices(session: AsyncSession) -> dict[str, int]:
    """Every active action's price for a man: `GET /prices`. Gifts aren't
    actions; they are priced in `gifts` (`GET /gifts`, T-8.9)."""
    return await repository.active_prices(session)
