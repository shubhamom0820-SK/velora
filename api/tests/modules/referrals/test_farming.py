"""One number, one referee, ever (D-691): checked at apply, from the referrals
every account on the number ever had. T-9.6's erasure keeps both what that
reads, the old account's `phone_hash` (D-051) and its referral (D-503), so
deleting an account and signing up again on its number can't apply a second
code and farm a second reward. Through the real erasure, as T-8.11's welcome
test runs it.

What this doesn't stop, accepted (D-692): a fresh number per account. The cap
on what one referrer is paid is what bounds that (test_rewards.py)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import ModuleType

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import IST
from app.core.enums import OnboardingStep
from app.core.providers.storage import FakeStorage
from app.core.security import decrypt_phone
from app.modules.account import service as account_service
from app.modules.users import service as users_service
from tests.conftest import MakeUser
from tests.modules.photos.test_moderate import Sessions
from tests.modules.referrals.support import (
    SETTINGS,
    apply,
    bearer,
    error,
    referral_of,
    token_for,
)

pytestmark = pytest.mark.usefixtures("test_redis")

NOW = datetime(2026, 10, 8, 6, 30, tzinfo=IST)


@pytest.mark.critical  # D-691: deleting and signing up again is no second referee
async def test_apply_delete_wait_out_the_erasure_sign_up_again_is_already_exists(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOW - timedelta(days=30))
    referrer, _ = await make_user()
    another, _ = await make_user()
    code, another_code = referrer.referral_code, another.referral_code
    first, token = await make_user(onboarded=False)
    first_id = first.id
    assert first.phone_enc is not None
    phone = decrypt_phone(first.phone_enc, SETTINGS)
    assert (await apply(client, token, code)).status_code == 204
    first.onboarding_step = OnboardingStep.DONE
    await db.flush()
    deleted = await client.delete("/v1/me", headers=bearer(token))
    assert deleted.status_code == 202, deleted.text

    clock.freeze(NOW)
    erased = await account_service.erase_due_accounts(
        Sessions(db),
        storage=FakeStorage(),
        settings=SETTINGS,
    )
    assert erased == 1
    assert await db.scalar(
        text("select anonymised_at is not null from users where id = :u"),
        {"u": first_id},
    )
    # The erasure kept the referral (D-503).
    assert await referral_of(db, first_id) is not None

    again, created = await users_service.find_or_create_account(db, phone, SETTINGS)
    assert created and again.id != first_id
    again_id = again.id
    response = await apply(client, token_for(again), another_code)

    assert response.status_code == 409
    assert error(response)["code"] == "ALREADY_EXISTS"
    assert await referral_of(db, again_id) is None


async def test_a_number_never_referred_may_apply_after_an_erasure(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """The control: the same path without the first apply, so the refusal
    above is the referral's, not the erasure's."""
    clock.freeze(NOW - timedelta(days=30))
    referrer, _ = await make_user()
    code = referrer.referral_code
    first, token = await make_user()
    first_id = first.id
    assert first.phone_enc is not None
    phone = decrypt_phone(first.phone_enc, SETTINGS)
    assert (await client.delete("/v1/me", headers=bearer(token))).status_code == 202

    clock.freeze(NOW)
    await account_service.erase_due_accounts(
        Sessions(db),
        storage=FakeStorage(),
        settings=SETTINGS,
    )
    again, created = await users_service.find_or_create_account(db, phone, SETTINGS)
    assert created and again.id != first_id

    assert (await apply(client, token_for(again), code)).status_code == 204
