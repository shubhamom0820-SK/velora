"""Users committed for real, for the tests that need separate connections
(06-TESTING, "Tests that commit rows").

A race needs two transactions on two connections, so it can't run inside the
`db` fixture's rolled-back one. From T-5.1 a committed ledger row can never be
deleted (the ledger refuses DELETE and TRUNCATE, and foreign keys into `users`
are RESTRICT), so these users are never deleted either. They last until the
run's slot is next taken, which recreates its database (P-55).

So every one is fresh: a man, never onboarded (no profile rows that a
migration's downgrade would have to clear), on a number neither `make_user`
(`+9198…`) nor the seed (`+9190000…`) ever generates. A test that makes them
scopes every assertion to their ids, never to a whole table.

Their numbers come from a counter the database keeps, never random digits: two
of fifty random numbers can collide, and a collision fails a test that must
never be flaky.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.core.enums import Gender, LedgerReason
from app.core.security import E164, decrypt_phone, normalize_phone
from app.modules.notifications.models import Notification, PushOutbox
from app.modules.payments.models import Payment, PaymentReversal, RefundRequest
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from tests.conftest import make_test_settings

# `+9197` and eight digits: a valid Indian mobile, in a block nothing else uses.
FRESH_PREFIX = "+9197"
FRESH_NUMBERS = 10**8

# The advisory lock's first key, meaning "a fresh man's number"; P-55's slots
# lock on 55 (tests/infra.py). Advisory locks are per database.
NUMBER_LOCK = 97


# Every fresh man this test committed, for `take_back_notifications` (T-9.4):
# a debit across `low_balance_velas` writes him a notification, which the
# autouse fixture in conftest.py deletes once the test ends.
COMMITTED_THIS_TEST: list[UUID] = []


async def fresh_man(engine: AsyncEngine, *, credits: int = 0) -> UUID:
    """A man, signed up and committed, with `credits` granted through the
    wallet (an `admin_grant`, as `make_user` does). Never deleted; what the
    app told him is (`take_back_notifications`)."""
    settings = make_test_settings()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            await lock_numbers(session)
            phone = await next_fresh_number(session, settings)
            account = await users_service.create_account(session, phone, settings)
            account.user.gender = Gender.MALE
            await session.flush()
            if credits:
                await wallet_service.credit(
                    session,
                    account.user.id,
                    credits,
                    LedgerReason.ADMIN_GRANT,
                    event="fresh_man",
                )
        COMMITTED_THIS_TEST.append(account.user.id)
        return account.user.id


async def take_back_notifications(
    engine: AsyncEngine, user_ids: Sequence[UUID]
) -> None:
    """Delete what the app told these committed men: in-app rows and waiting
    pushes (T-9.4). Neither is a record (rule 12), and both outlive a test
    that debits a fresh man across `low_balance_velas` (D-853)."""
    if not user_ids:
        return
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            delete(Notification).where(Notification.user_id.in_(user_ids))
        )
        await session.execute(
            delete(PushOutbox).where(PushOutbox.user_id.in_(user_ids))
        )


async def lock_numbers(session: AsyncSession) -> None:
    """One fresh man at a time on this database, until his transaction ends:
    men made at once, by one run or two pointed at the same database, never
    read the same highest number."""
    await session.execute(
        text("select pg_advisory_xact_lock(:lock, 0)"), {"lock": NUMBER_LOCK}
    )


async def next_fresh_number(session: AsyncSession, settings: Settings) -> E164:
    """One past the highest fresh man's number in this database.

    The database is the counter, not this process: a run pointed at a database
    of its own by `TEST_DATABASE_URL` keeps its men from earlier runs (no slot
    recreates it), so a count kept in memory would restart into their numbers.
    Numbers are stored encrypted (D-061), so each is read back. Under
    `lock_numbers`, and read-committed, so it sees the last holder's man.
    """
    taken = [
        int(phone.removeprefix(FRESH_PREFIX))
        # An erased account has no number left (D-500); its row is skipped.
        for token in await session.scalars(
            select(User.phone_enc).where(User.phone_enc.is_not(None))
        )
        if token is not None
        and (phone := decrypt_phone(token, settings)).startswith(FRESH_PREFIX)
    ]
    serial = max(taken, default=-1) + 1
    if serial >= FRESH_NUMBERS:
        # No number in the message: one we generate may still be someone's (D-064).
        raise RuntimeError(
            f"This database holds the last of the {FRESH_PREFIX} block. Point "
            "TEST_DATABASE_URL at a new database, or unset it to take a run slot (P-55)."
        )
    return normalize_phone(f"{FRESH_PREFIX}{serial:08d}")


async def take_back_payments(engine: AsyncEngine, payment_ids: Sequence[UUID]) -> None:
    """Delete the payments a race test committed (T-8.2), test code only, with
    the claims and reversal records that name them (T-8.3).

    Payments are never deleted (rule 12: `payments_no_delete`), nor are
    reversal records (`payment_reversals_no_update_delete`), but a committed
    one would outlive its test and break every downgrade test after it: it
    names its pack by a RESTRICT key, and the seed's and T-5.2's downgrades
    delete packs; T-8.3's downgrades refuse while a claim is resolved or a
    reversal recorded. So the triggers are switched off, as the owner the
    tests connect as, the rows deleted, and switched on again, in one
    transaction in this run's own database (P-55): a failure rolls it all
    back. The ledger rows those payments credited stay; they name no pack.
    """
    if not payment_ids:
        return
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            text(
                "alter table payment_reversals "
                "disable trigger payment_reversals_no_update_delete"
            )
        )
        await session.execute(
            delete(PaymentReversal).where(PaymentReversal.payment_id.in_(payment_ids))
        )
        await session.execute(
            text(
                "alter table payment_reversals "
                "enable trigger payment_reversals_no_update_delete"
            )
        )
        await session.execute(
            delete(RefundRequest).where(RefundRequest.payment_id.in_(payment_ids))
        )
        await session.execute(
            text("alter table payments disable trigger payments_no_delete")
        )
        await session.execute(delete(Payment).where(Payment.id.in_(payment_ids)))
        await session.execute(
            text("alter table payments enable trigger payments_no_delete")
        )
