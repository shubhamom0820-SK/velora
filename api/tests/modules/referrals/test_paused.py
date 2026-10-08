"""Referrals paused (P-740, D-840): `referral_reward_velas` at 0, as the
migrated database holds it. `POST /referrals/apply` is refused,
`NOT_ALLOWED` with `details.why` `referrals_paused`, before anything is
written, so the number's one referee slot (D-691) is still there when
referrals run again; a missing setting is paused too. At 0 the selfie and the
capture pay no reward (D-692), and the capture still credits the purchase
(T-8.2). At 5 the same apply is taken and paid: the control."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.core.providers import FakeProviders
from tests.conftest import CapturedLogs, MakeUser
from tests.modules.referrals.support import (
    REWARD,
    RUNNING,
    apply,
    error,
    ledger,
    purchase,
    refer,
    referral_of,
    rewards,
    selfie_matches,
    set_config,
    two_men,
)
from tests.modules.verification.support import at_selfie

pytestmark = pytest.mark.usefixtures("test_redis")

PAUSED = {
    "code": "NOT_ALLOWED",
    "message": "Referral codes are paused for now.",
    "details": {"why": "referrals_paused"},
}


@pytest.mark.critical  # D-840: no slot spent on a referral that pays nothing
@pytest.mark.parametrize("value", ["0", "-5", None], ids=["zero", "negative", "no row"])
async def test_while_paused_apply_is_refused_and_the_slot_is_kept(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, value: str | None
) -> None:
    referrer, _ = await make_user()
    code = referrer.referral_code
    referee, token = await make_user(onboarded=False)
    referee_id = referee.id
    await set_config(db, REWARD, value)

    response = await apply(client, token, code)

    assert response.status_code == 422, response.text
    assert error(response) == PAUSED
    assert await referral_of(db, referee_id) is None

    # Running again, the same number applies: the refusal took nothing.
    if value is None:
        await db.execute(
            text("insert into app_config (key, value) values (:k, '5'::jsonb)"),
            {"k": REWARD},
        )
    else:
        await set_config(db, REWARD, str(RUNNING))
    assert (await apply(client, token, code)).status_code == 204
    assert await referral_of(db, referee_id) is not None


async def test_a_missing_setting_is_paused_with_a_warning(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
) -> None:
    referrer, _ = await make_user()
    _, token = await make_user(onboarded=False)
    await set_config(db, REWARD, None)

    assert (await apply(client, token, referrer.referral_code)).status_code == 422

    warnings = [e for e in captured_logs.events if e["log_level"] == "warning"]
    assert [(e["event"], e["key"]) for e in warnings] == [
        ("referrals.apply_config_missing", REWARD)
    ]


async def test_paused_is_said_before_anything_else(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Even a code nobody has, or one's own, is told only that referrals are
    paused: nothing about the code is read while nothing can pay."""
    me, token = await make_user(onboarded=False)
    await set_config(db, REWARD, "0")

    for code in ("NOBODYHASTHIS", me.referral_code):
        response = await apply(client, token, code)
        assert response.status_code == 422, response.text
        assert error(response) == PAUSED


@pytest.mark.critical  # D-840's control: at 5, apply is taken and paid
async def test_at_five_apply_is_taken_and_the_selfie_pays_both_men(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    referrer, _ = await make_user()
    referee, token = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await set_config(db, REWARD, str(RUNNING))

    assert (await apply(client, token, referrer.referral_code)).status_code == 204
    assert await selfie_matches(db, referee) == "approved"

    assert [row[0] for row in await rewards(db, referee_id)] == [RUNNING]
    assert [row[0] for row in await rewards(db, referrer_id)] == [RUNNING]


@pytest.mark.critical  # D-840: nothing paid while paused, by either trigger
async def test_at_zero_a_selfie_pays_no_reward(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """A referral made before the pause: its trigger closes it with nothing."""
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    await set_config(db, REWARD, "0")

    assert await selfie_matches(db, referee) == "approved"

    assert await ledger(db, referee_id) == await ledger(db, referrer_id) == []
    found: dict[str, Any] | None = await referral_of(db, referee_id)
    assert found is not None and found["rewarded_at"] is not None


@pytest.mark.critical  # D-840 and T-8.2: the purchase is credited, no reward
async def test_at_zero_a_capture_credits_the_purchase_and_no_reward(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    (referee, token), (referrer, _) = await two_men(make_user, referrer_below=True)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    await set_config(db, REWARD, "0")

    response = await purchase(db, client, fake_providers, token)

    assert response.status_code == 200, response.text
    reasons = sorted(row[0] for row in await ledger(db, referee_id))
    assert reasons == ["purchase", "purchase_bonus"]
    assert await rewards(db, referee_id) == await rewards(db, referrer_id) == []
