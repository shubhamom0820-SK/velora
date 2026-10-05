"""`GET /v1/wallet` and `GET /v1/wallet/ledger` — the responses (04-API.md, T-5.3)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import LedgerReason
from app.core.pagination import Page


class Wallet(BaseModel):
    """`{balance}`, in Velas. A woman's is 0, always (D-076)."""

    balance: int


class LedgerEntry(BaseModel):
    """One change to the balance, as its owner sees it. Never its ref or its
    key: what an entry was for is named by `reason`, which the web turns into
    words (D-033, P-26)."""

    id: UUID
    delta: int
    balance_after: int
    reason: LedgerReason
    created_at: datetime


class LedgerEntryPage(Page[LedgerEntry]):
    """`Page<LedgerEntry>`: newest first by `(created_at, id)`."""
