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
"""

from __future__ import annotations

import secrets
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import Gender, LedgerReason
from app.core.security import normalize_phone
from app.modules.users import service as users_service
from app.modules.wallet import service as wallet_service
from tests.conftest import make_test_settings

# `+9197` and eight digits: a valid Indian mobile, in a block nothing else uses.
FRESH_PREFIX = "+9197"


async def fresh_man(engine: AsyncEngine, *, credits: int = 0) -> UUID:
    """A man, signed up and committed, with `credits` granted through the
    wallet (an `admin_grant`, as `make_user` does). Never deleted."""
    phone = normalize_phone(f"{FRESH_PREFIX}{secrets.randbelow(10**8):08d}")
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            account = await users_service.create_account(
                session, phone, make_test_settings()
            )
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
