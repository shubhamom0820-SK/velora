"""Rule 15 for the wallet: no idempotency key or event, no phone number or its
hash, no PIN hash and no token, in a log line, an error's message or a
response.

Logs are read from `captured_logs`, which proves it was listening (P-48). These
tests also pass in shuffled orders (`--shuffle-seed`), not only file order.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.enums import LedgerReason
from app.core.errors import AppError
from app.core.security import decrypt_phone
from app.modules.wallet import service
from app.modules.wallet.models import LedgerEntry
from app.modules.wallet.rules import Ref, RefType
from app.modules.wallet.service import WalletMisuse
from tests.conftest import CapturedLogs, MakeUser, make_test_settings

PIN_HASH = "$argon2id$v=19$m=65536,t=3,p=4$cnVsZTE1$a-pin-hash-never-logged"


async def test_the_wallets_logs_and_refusals_carry_nothing_secret(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    man, token = await make_user(credits=10)
    man.pin_hash = PIN_HASH
    await db.flush()
    assert man.phone_enc is not None
    phone = decrypt_phone(man.phone_enc, make_test_settings())
    grant_event, reopen_event = f"client-{uuid.uuid4()}", f"client-{uuid.uuid4()}"
    thread = Ref(RefType.THREAD, uuid.uuid4())

    await service.credit(db, man.id, 5, LedgerReason.ADMIN_GRANT, event=grant_event)
    await service.credit(db, man.id, 5, LedgerReason.ADMIN_GRANT, event=grant_event)
    await service.debit(
        db, man.id, 3, LedgerReason.THREAD_REOPEN, ref=thread, event=reopen_event
    )
    refusals: list[str] = []
    try:
        await service.credit(db, man.id, 6, LedgerReason.ADMIN_GRANT, event=grant_event)
    except WalletMisuse as misuse:
        refusals.append(str(misuse))
    try:
        await service.debit(db, man.id, 500, LedgerReason.THREAD_OPEN, ref=thread)
    except AppError as error:
        refusals.append(f"{error.message} {error.details}")

    keys = list(
        await db.scalars(
            select(LedgerEntry.idempotency_key).where(LedgerEntry.user_id == man.id)
        )
    )
    secrets = [
        phone,
        phone.removeprefix("+91"),
        man.phone_hash,
        PIN_HASH,
        token,
        grant_event,
        reopen_event,
        *keys,
    ]
    logged = captured_logs.text
    assert len(refusals) == 2 and len(keys) == 3
    for secret in secrets:
        assert secret not in logged
        assert all(secret not in refusal for refusal in refusals)
    names = {event["event"] for event in captured_logs.events}
    assert {"wallet.applied", "wallet.repeated"} <= names  # it heard the wallet
    captured_logs.assert_listening()


async def test_an_insufficient_balance_answers_with_its_code_and_two_numbers(
    app: FastAPI, client: AsyncClient, make_user: MakeUser
) -> None:
    """The whole body, compared exactly: nothing in it but the code, a message
    naming no unit, and what was required against what there was."""
    man, _ = await make_user(credits=5)

    @app.post("/v1/_test/debit")
    async def _debit(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, bool]:
        async with session.begin():
            await service.debit(
                session,
                man.id,
                6,
                LedgerReason.THREAD_OPEN,
                ref=Ref(RefType.THREAD, uuid.uuid4()),
            )
        return {"ok": True}

    response = await client.post("/v1/_test/debit")

    assert response.status_code == 402
    assert response.json() == {
        "error": {
            "code": "INSUFFICIENT_CREDITS",
            "message": "Your balance is too low for this.",
            "details": {"required": 6, "balance": 5},
        }
    }
