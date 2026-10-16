"""A test's Velas, granted as anything is (rule 5): an `admin_grant` naming an
audit row, as every grant names its row since T-9.5 (D-923). `make_user`,
`fresh_man` and the tests that top a wallet up call it; a test of the wallet's
own rules calls `wallet.service.credit()`.

The row's actor is the man himself, never the system user (D-905): migration
4800f0e8d5a9 refuses to go down while the log names the system user, and the
migration tests take a man with Velas down past it.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LedgerReason
from app.modules.admin import service as admin_service
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType
from app.modules.wallet.service import LedgerResult

# The audit row's action, which no app code writes.
TEST_GRANT = "test.grant"


async def grant_audit(session: AsyncSession, user_id: UUID, credits: int) -> Ref:
    """The audit row a test's grant names, as its ref."""
    audit = await admin_service.audit(
        session,
        user_id,
        TEST_GRANT,
        {"credits": credits},
        target=("user", user_id),
    )
    return Ref(RefType.AUDIT_LOG, audit)


async def grant(
    session: AsyncSession, user_id: UUID, credits: int, *, event: str
) -> LedgerResult:
    """`credits` to a man, under `event`, naming a fresh audit row."""
    ref = await grant_audit(session, user_id, credits)
    return await wallet_service.credit(
        session, user_id, credits, LedgerReason.ADMIN_GRANT, ref=ref, event=event
    )
