"""`POST /v1/verification/{id}/submit` (T-4.5): the selfie attached, the
comparison queued, and then the worker woken (D-261)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, OnboardingStep, ReviewStatus
from app.core.providers import FakeProviders
from app.core.queue import VERIFY_SELFIE, FakeQueue
from app.modules.verification import rules
from app.modules.verification.models import Verification
from tests.conftest import MakeUser
from tests.modules.verification.support import (
    approved_photo,
    at_selfie,
    bearer,
    error,
    fresh,
    selfie,
    start,
    submit,
    submitted,
)

pytestmark = pytest.mark.usefixtures("test_redis")


async def _started(client: AsyncClient, token: str) -> str:
    response = await start(client, token)
    assert response.status_code == 200, response.text
    verification_id: str = response.json()["id"]
    return verification_id


async def test_it_queues_the_comparison_then_wakes_the_worker_after_the_commit(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    """The wake must find what it was woken for: sent once the transaction
    that attached the selfie has ended, never inside it."""
    user, token = await at_selfie(db, make_user)
    photo = await selfie(db, fake_providers.storage, user)
    verification_id = await _started(client, token)
    in_transaction: list[bool] = []
    fake_queue.on_wake = lambda: in_transaction.append(db.in_transaction())

    response = await submit(client, token, verification_id, photo.id)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": verification_id,
        "status": "pending",
        "submitted": True,
        "reject_reason": None,
        "attempts_left": 4,
    }
    [job] = fake_queue.named(VERIFY_SELFIE)
    assert (job.job_id, job.kwargs) == (
        f"verify_selfie:{verification_id}",
        {"verification_id": verification_id},
    )
    assert fake_queue.woken == [(VERIFY_SELFIE, verification_id)]
    assert in_transaction == [False]
    row = await fresh(db, Verification, uuid.UUID(verification_id))
    assert row.selfie_photo_id == photo.id


async def test_sending_the_same_selfie_twice_is_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    user, token = await at_selfie(db, make_user)
    photo = await selfie(db, fake_providers.storage, user)
    verification_id = await _started(client, token)

    first = await submit(client, token, verification_id, photo.id)
    again = await submit(client, token, verification_id, photo.id)

    assert again.status_code == 200
    assert again.json() == first.json()
    assert len(fake_queue.named(VERIFY_SELFIE)) == 1
    assert len(fake_queue.woken) == 1


async def test_another_selfie_for_one_already_sent_is_not_allowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    verification, _ = await submitted(db, fake_providers.storage, user)
    other = await selfie(db, fake_providers.storage, user)

    response = await submit(client, token, verification.id, other.id)

    assert error(response)["code"] == "NOT_ALLOWED"


async def test_someone_elses_verification_or_none_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    _, other_token = await at_selfie(db, make_user)
    theirs = await _started(client, other_token)
    photo_id = (await selfie(db, fake_providers.storage, user)).id

    for verification_id in (theirs, uuid.uuid4()):
        response = await submit(client, token, verification_id, photo_id)
        assert response.status_code == 404
        assert error(response)["code"] == "NOT_FOUND"


async def test_someone_elses_selfie_or_a_public_photo_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    other, _ = await at_selfie(db, make_user)
    verification_id = await _started(client, token)
    theirs = await selfie(db, fake_providers.storage, other)
    public = await approved_photo(db, fake_providers.storage, user)

    # Read before any request: a refused one rolls back, expiring them.
    for photo_id in [theirs.id, public.id, uuid.uuid4()]:
        response = await submit(client, token, verification_id, photo_id)
        assert error(response)["code"] == "NOT_FOUND"


async def test_a_selfie_already_decided_or_held_elsewhere_is_not_allowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    old, held = await submitted(db, fake_providers.storage, user)
    old.status = ReviewStatus.REJECTED
    await db.flush()
    rejected = await selfie(db, fake_providers.storage, user)
    rejected.status = ReviewStatus.REJECTED
    await db.flush()
    photo_ids = [held.id, rejected.id]
    verification_id = await _started(client, token)

    for photo_id in photo_ids:
        response = await submit(client, token, verification_id, photo_id)
        assert error(response)["code"] == "NOT_ALLOWED"


async def test_a_selfie_never_uploaded_is_not_allowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_queue: FakeQueue,
) -> None:
    user, token = await at_selfie(db, make_user)
    photo = await selfie(db, None, user)
    verification_id = await _started(client, token)

    response = await submit(client, token, verification_id, photo.id)

    assert error(response)["code"] == "NOT_ALLOWED"
    assert fake_queue.jobs == [] and fake_queue.woken == []


async def test_before_the_selfie_step_it_names_the_step(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    photo = await selfie(db, fake_providers.storage, user)
    verification_id = await _started(client, token)
    user.onboarding_step = (
        OnboardingStep.PIN
    )  # as no request could; the rule still holds
    await db.flush()

    response = await submit(client, token, verification_id, photo.id)

    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"
    assert error(response)["details"] == {"step": "pin"}


@pytest.mark.parametrize(
    "body",
    [{}, {"photo_id": "not-an-id"}, {"photo_id": str(uuid.uuid4()), "pose": "left"}],
    ids=["nothing", "not-an-id", "an-unknown-field"],
)
async def test_a_body_that_isnt_a_selfie_id_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    body: dict[str, str],
) -> None:
    _, token = await at_selfie(db, make_user)
    verification_id = await _started(client, token)

    response = await client.post(
        f"/v1/verification/{verification_id}/submit", json=body, headers=bearer(token)
    )

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_the_sixth_selfie_in_a_day_is_refused_at_submit_too(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    """Started while four had been sent, and a fifth sent meanwhile (another
    tab): the submit, not only the start, keeps the count."""
    user, token = await at_selfie(db, make_user)
    for _ in range(rules.ATTEMPTS - 1):
        verification, _ = await submitted(db, fake_providers.storage, user)
        verification.status = ReviewStatus.REJECTED
    await db.flush()
    verification_id = await _started(client, token)
    fifth, _ = await submitted(db, fake_providers.storage, user)
    fifth.status = ReviewStatus.REJECTED
    await db.flush()
    photo = await selfie(db, fake_providers.storage, user)

    response = await submit(client, token, verification_id, photo.id)

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"
    assert fake_queue.woken == []


async def test_a_queue_that_refuses_fails_the_submit_and_changes_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    user, token = await at_selfie(db, make_user)
    photo = await selfie(db, fake_providers.storage, user)
    verification_id = await _started(client, token)
    fake_queue.fail = True

    response = await submit(client, token, verification_id, photo.id)

    assert response.status_code == 500
    assert error(response)["code"] == "INTERNAL"
    row = await fresh(db, Verification, uuid.UUID(verification_id))
    assert row.selfie_photo_id is None
    assert fake_queue.woken == []


async def test_a_man_may_send_one_too(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user, Gender.MALE)
    photo = await selfie(db, fake_providers.storage, user)
    verification_id = await _started(client, token)

    assert (await submit(client, token, verification_id, photo.id)).status_code == 200
