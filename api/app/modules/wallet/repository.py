"""The wallet's SQL. Only `wallet.service` calls it: nothing else writes a
balance or the ledger (CLAUDE.md rule 5)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Row, insert, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, LedgerReason
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet


async def lock_wallet(
    session: AsyncSession, user_id: UUID
) -> tuple[int, Gender | None] | None:
    """The wallet's balance and its owner's gender, the wallet row locked until
    the transaction ends; None if the user has no wallet.

    Columns, not the `Wallet` entity: an entity already in the session's
    identity map would come back with the balance it was loaded with, not the
    one the lock was granted on.
    """
    row = (
        await session.execute(
            select(Wallet.balance, User.gender)
            .join(User, User.id == Wallet.user_id)
            .where(Wallet.user_id == user_id)
            .with_for_update(of=Wallet)
        )
    ).one_or_none()
    return None if row is None else (row.balance, row.gender)


async def entry_by_key(session: AsyncSession, key: str) -> LedgerEntry | None:
    entry: LedgerEntry | None = await session.scalar(
        select(LedgerEntry).where(LedgerEntry.idempotency_key == key)
    )
    return entry


async def set_balance(session: AsyncSession, user_id: UUID, balance: int) -> None:
    await session.execute(
        update(Wallet).where(Wallet.user_id == user_id).values(balance=balance)
    )


async def add_entry(
    session: AsyncSession,
    *,
    user_id: UUID,
    delta: int,
    balance_after: int,
    reason: LedgerReason,
    ref_type: str | None,
    ref_id: UUID | None,
    key: str,
) -> LedgerEntry:
    entry = await session.scalar(
        insert(LedgerEntry)
        .values(
            user_id=user_id,
            delta=delta,
            balance_after=balance_after,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=key,
        )
        .returning(LedgerEntry)
    )
    assert entry is not None
    return entry


# --- Reads (T-5.3) -------------------------------------------------------------


async def balance_of(session: AsyncSession, user_id: UUID) -> int:
    balance = await session.scalar(
        select(Wallet.balance).where(Wallet.user_id == user_id)
    )
    if balance is None:
        raise LookupError("a user without a wallet: signup creates both")
    return balance


async def ledger_page(
    session: AsyncSession,
    user_id: UUID,
    *,
    after: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[Row[tuple[UUID, int, int, LedgerReason, datetime]]]:
    """Up to `limit` of the user's entries, newest first by `(created_at, id)`,
    from just after `after`. Entries from one transaction share `created_at`,
    so `id` orders them: stable, though not the order they were written.

    Only the columns the owner sees: the ref and the key never leave here.
    """
    query = (
        select(
            LedgerEntry.id,
            LedgerEntry.delta,
            LedgerEntry.balance_after,
            LedgerEntry.reason,
            LedgerEntry.created_at,
        )
        .where(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(limit)
    )
    if after is not None:
        # A plain tuple, so each bind takes its column's type: timestamptz, uuid.
        query = query.where(tuple_(LedgerEntry.created_at, LedgerEntry.id) < after)
    return (await session.execute(query)).all()
