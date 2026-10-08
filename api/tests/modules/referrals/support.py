"""What T-8.6's tests share: accounts at a step, the apply request, a referral
written as apply leaves one, the two triggers (a selfie that matches, a
purchase captured), and what the ledger and `app_config` hold."""

from __future__ import annotations

import itertools
import uuid
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import OnboardingStep
from app.core.providers import FakeProviders
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.core.queue import FakeQueue
from app.core.security import make_access_token, normalize_phone
from app.modules.referrals.models import Referral
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.verification import service as verification_service
from tests.conftest import MakeUser, make_test_settings
from tests.modules.payments.support import captured, deliver, order
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import face_photo, submitted

SETTINGS = make_test_settings()
APPLY = "/v1/referrals/apply"
REWARD = "referral_reward_velas"
REWARDS_MAX = "referral_rewards_max"

# `+9196` and eight digits: a block neither `make_user` (`+9198…`), the seed
# (`+9190000…`) nor tests/committed.py (`+9197…`) uses.
_serial = itertools.count(1)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def error(response: Response) -> dict[str, Any]:
    found: dict[str, Any] = response.json()["error"]
    return found


def token_for(user: User) -> str:
    return make_access_token(user.id, user.role, SETTINGS, auth_time=clock.now())


async def at_dob(db: AsyncSession) -> tuple[User, str]:
    """An account as sign-in leaves it: at the dob step, no gender, no dob."""
    phone = normalize_phone(f"+9196{next(_serial):08d}")
    account = await users_service.create_account(db, phone, SETTINGS)
    assert account.user.onboarding_step is OnboardingStep.DOB
    await db.flush()
    return account.user, token_for(account.user)


async def apply(client: AsyncClient, token: str, code: str) -> Response:
    return await client.post(APPLY, json={"code": code}, headers=bearer(token))


async def refer(db: AsyncSession, referee: User, referrer: User) -> None:
    """A referral as apply leaves one, without its route."""
    db.add(Referral(referee_id=referee.id, referrer_id=referrer.id))
    await db.flush()


async def referral_of(db: AsyncSession, referee_id: uuid.UUID) -> dict[str, Any] | None:
    """The referee's referral as the database holds it, or None."""
    row = (
        await db.execute(
            text("select * from referrals where referee_id = :u"), {"u": referee_id}
        )
    ).one_or_none()
    return None if row is None else dict(row._mapping)


async def ledger(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """(reason, delta, ref_type, ref_id, key) for each of the user's entries."""
    rows = await db.execute(
        text(
            "select reason::text, delta, ref_type, ref_id, idempotency_key "
            "from ledger_entries where user_id = :u order by created_at, id"
        ),
        {"u": user_id},
    )
    return [tuple(row) for row in rows]


async def rewards(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """The user's `referral_reward` entries: (delta, ref_type, ref_id, key)."""
    return [row[1:] for row in await ledger(db, user_id) if row[0] == "referral_reward"]


async def set_config(db: AsyncSession, key: str, value: str | None) -> None:
    """`app_config.<key>` as JSON text, or no row at all."""
    if value is None:
        await db.execute(text("delete from app_config where key = :k"), {"k": key})
    else:
        await db.execute(
            text("update app_config set value = cast(:v as jsonb) where key = :k"),
            {"k": key, "v": value},
        )


async def two_men(
    make_user: MakeUser, *, referrer_below: bool
) -> tuple[tuple[User, str], tuple[User, str]]:
    """(referee, referrer), both men done, the referrer's id below or above
    the referee's: the order the two wallets must be locked in (P-63)."""
    a = await make_user()
    b = await make_user()
    low, high = sorted((a, b), key=lambda made: made[0].id)
    return (high, low) if referrer_below else (low, high)


# --- The two triggers ------------------------------------------------------------


async def selfie_matches(db: AsyncSession, user: User) -> str:
    """The user's selfie compared and matched, as the `verify_selfie` job
    decides it (T-4.5): from the selfie step, with a face photo."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    await face_photo(db, storage, user)
    verification, _ = await submitted(db, storage, user)
    facematch.next = FaceMatch(model="fake", faces_in_selfie=1, similarities=(0.71,))
    return await verification_service.verify(
        Sessions(db),
        verification.id,
        storage=storage,
        facematch=facematch,
        queue=FakeQueue(),
        settings=SETTINGS,
        via="queue",
    )


async def purchase(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    token: str,
    *,
    payment_id: str = "pay_R1",
) -> Response:
    """A real order, then its capture delivered as Razorpay would."""
    our_id, order_id = await order(client, token)
    amount = await db.scalar(
        text("select amount_paise from payments where id = :p"), {"p": our_id}
    )
    return await deliver(
        client,
        fake_providers.payments,
        captured(order_id, payment_id=payment_id, amount=amount),
    )
