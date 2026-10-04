"""`POST /v1/verification/start` (T-4.5): a verification waiting for its
selfie. No pose is asked (D-263): the `challenge` column says `none`."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, OnboardingStep, ReviewStatus
from app.core.providers import FakeProviders
from app.modules.verification import rules
from app.modules.verification.models import Verification
from tests.conftest import MakeUser
from tests.modules.verification.support import (
    at_selfie,
    error,
    fresh,
    start,
    submitted,
)

pytestmark = pytest.mark.usefixtures("test_redis")


async def test_it_opens_a_verification_waiting_for_its_selfie(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await at_selfie(db, make_user)

    response = await start(client, token)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "id": body["id"],
        "status": "pending",
        "submitted": False,
        "reject_reason": None,
        "attempts_left": 5,
    }
    row = await fresh(db, Verification, uuid.UUID(body["id"]))
    assert (row.challenge, row.liveness_ok, row.similarity, row.selfie_photo_id) == (
        "none",
        None,
        None,
        None,
    )


async def test_starting_again_is_the_same_verification(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await at_selfie(db, make_user)

    first = (await start(client, token)).json()
    again = (await start(client, token)).json()

    assert again == first


async def test_before_the_selfie_step_it_names_the_step(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await at_selfie(db, make_user)
    user.onboarding_step = OnboardingStep.PIN
    await db.flush()

    response = await start(client, token)

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"
    assert error(response)["details"] == {"step": "pin"}


async def test_after_onboarding_an_unverified_man_may_start(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Men may skip the selfie (T-4.7) and come back to it: D-068's "at the
    step or after"."""
    _, token = await make_user(Gender.MALE, verified=False)

    assert (await start(client, token)).status_code == 200


async def test_without_a_token_it_is_refused(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.post("/v1/verification/start")

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


async def test_once_the_selfie_has_matched_there_is_nothing_to_start(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(Gender.FEMALE)  # onboarded, so matched (D-008)

    response = await start(client, token)

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"


async def test_not_while_a_selfie_is_being_compared(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    await submitted(db, fake_providers.storage, user)

    response = await start(client, token)

    assert error(response)["code"] == "NOT_ALLOWED"


async def test_after_a_rejection_a_new_one_starts(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    old, _ = await submitted(db, fake_providers.storage, user)
    old.status = ReviewStatus.REJECTED
    await db.flush()

    body = (await start(client, token)).json()

    assert body["id"] != str(old.id)
    assert (body["status"], body["attempts_left"]) == ("pending", 4)


async def test_five_selfies_in_24_hours_and_the_sixth_waits(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """Five sent in the last 24 hours, each rejected: no sixth until the oldest
    of them is 24 hours old. One sent 25 hours ago no longer counts."""
    user, token = await at_selfie(db, make_user)
    now = clock.now()
    for hours_ago in (25, 20, 10, 5, 2, 1):
        verification, _ = await submitted(
            db,
            fake_providers.storage,
            user,
            created_at=now - timedelta(hours=hours_ago),
        )
        verification.status = ReviewStatus.REJECTED
    await db.flush()

    response = await start(client, token)

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"
    # The oldest of the five, 20 hours ago, leaves the window in 4 hours.
    wait = error(response)["details"]["retry_after_s"]
    assert 4 * 3600 - 60 < wait <= 4 * 3600


async def test_four_selfies_in_24_hours_leave_one(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    for _ in range(rules.ATTEMPTS - 1):
        verification, _ = await submitted(db, fake_providers.storage, user)
        verification.status = ReviewStatus.REJECTED
    await db.flush()

    response = await start(client, token)

    assert response.status_code == 200
    assert response.json()["attempts_left"] == 1


async def test_selfies_sent_over_24_hours_ago_no_longer_count(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """The window is a rolling 24 hours: five sent yesterday, each over a day
    ago, leave all five for today. (Found by breaking the window: every other
    test stayed green, since none sent only old selfies.)"""
    user, token = await at_selfie(db, make_user)
    now = clock.now()
    for minutes_over in (1, 30, 60, 120, 240):
        verification, _ = await submitted(
            db,
            fake_providers.storage,
            user,
            created_at=now - timedelta(hours=24, minutes=minutes_over),
        )
        verification.status = ReviewStatus.REJECTED
    await db.flush()

    response = await start(client, token)

    assert response.status_code == 200, response.text
    assert response.json()["attempts_left"] == 5
