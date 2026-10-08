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

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.core.enums import Gender, LedgerReason
from app.core.security import E164, decrypt_phone, normalize_phone
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


async def fresh_man(engine: AsyncEngine, *, credits: int = 0) -> UUID:
    """A man, signed up and committed, with `credits` granted through the
    wallet (an `admin_grant`, as `make_user` does). Never deleted."""
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
        return account.user.id


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
