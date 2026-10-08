"""`GET /v1/referrals/me` (T-8.6): the user's own code, how many applied it, and
how many of those were rewarded; a woman's counted the same way, though she is
never paid (D-690)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.modules.referrals.models import Referral
from tests.conftest import MakeUser
from tests.modules.referrals.support import bearer, error, refer

pytestmark = pytest.mark.usefixtures("test_redis")
ME = "/v1/referrals/me"


@pytest.mark.parametrize("gender", ["male", "female"])
async def test_it_counts_who_applied_the_code_and_who_was_rewarded(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, gender: str
) -> None:
    referrer, token = await make_user(gender)
    code = referrer.referral_code
    referees = [(await make_user(onboarded=False))[0] for _ in range(3)]
    for referee in referees:
        await refer(db, referee, referrer)
    await db.execute(
        update(Referral)
        .where(Referral.referee_id == referees[0].id)
        .values(rewarded_at=clock.now())
    )
    # Someone else's referral is never counted.
    other, _ = await make_user()
    await refer(db, (await make_user(onboarded=False))[0], other)

    response = await client.get(ME, headers=bearer(token))

    assert response.status_code == 200, response.text
    assert response.json() == {"code": code, "invited": 3, "rewarded": 1}


async def test_nobody_yet_is_zero(client: AsyncClient, make_user: MakeUser) -> None:
    man, token = await make_user()

    response = await client.get(ME, headers=bearer(token))

    assert response.json() == {"code": man.referral_code, "invited": 0, "rewarded": 0}


async def test_before_onboarding_is_done_it_is_onboarding_incomplete(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await client.get(ME, headers=bearer(token))

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"


async def test_without_a_token_it_is_401(db: AsyncSession, client: AsyncClient) -> None:
    assert (await client.get(ME)).status_code == 401
