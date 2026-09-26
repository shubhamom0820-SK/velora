"""`wallets`, `ledger_entries`, `action_prices` — 03-SCHEMA.md §6.

CLAUDE.md rule 5: every credit change goes through `wallet.service.debit()` /
`credit()`, which lock the wallet row with `SELECT … FOR UPDATE` and append a
ledger entry in the same transaction. Nothing else writes `wallets.balance`.

The database backs that up: the balance can never go negative, and the ledger
refuses UPDATE, DELETE and TRUNCATE (migration T-1.12) — append-only is enforced,
not just intended. Credits are integers (D-029); there are no floats here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    Text,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, pg_enum, uuid_fk, uuid_pk
from app.core.enums import LedgerReason


class Wallet(Timestamps, Base):
    """Created with the user (T-3.3). Written only by wallet.service."""

    __tablename__ = "wallets"

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    balance: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    __table_args__ = (CheckConstraint("balance >= 0", name="balance_non_negative"),)


class LedgerEntry(CreatedAt, Base):
    """Append-only. `balance == sum(delta)` per user is reconciled by T-9.9."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[LedgerReason] = mapped_column(pg_enum(LedgerReason), nullable=False)
    # What the entry is for, e.g. `thread` or `payment`. Polymorphic, so ref_id
    # cannot carry a foreign key.
    ref_type: Mapped[str | None] = mapped_column(Text)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # A retried debit or credit is applied once.
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    __table_args__ = (
        CheckConstraint("delta <> 0", name="delta_non_zero"),
        CheckConstraint("balance_after >= 0", name="balance_after_non_negative"),
        CheckConstraint("(ref_type IS NULL) = (ref_id IS NULL)", name="ref_complete"),
        Index(
            "ix_ledger_entries_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
    )


class ActionPrice(Timestamps, Base):
    """Prices are data, not code (D-004): tunable without a deploy.

    Read through `price_for()`; never a literal in a service.
    """

    __tablename__ = "action_prices"

    action: Mapped[str] = mapped_column(Text, primary_key=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())

    __table_args__ = (CheckConstraint("credits >= 0", name="credits_non_negative"),)
