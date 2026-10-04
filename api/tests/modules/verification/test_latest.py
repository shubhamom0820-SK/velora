"""`GET /v1/verification/latest` (T-4.5): how the newest one went, a reason
named only from a list (D-263)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import ReviewStatus
from app.core.providers import FakeProviders
from tests.conftest import MakeUser
from tests.modules.verification.support import at_selfie, error, latest, submitted

pytestmark = pytest.mark.usefixtures("test_redis")


async def test_with_none_it_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await at_selfie(db, make_user)

    response = await latest(client, token)

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"


async def test_it_is_the_newest(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await at_selfie(db, make_user)
    old, _ = await submitted(
        db,
        fake_providers.storage,
        user,
        created_at=clock.now() - timedelta(hours=1),
    )
    old.status = ReviewStatus.REJECTED
    new, _ = await submitted(db, fake_providers.storage, user)
    await db.flush()

    body = (await latest(client, token)).json()

    assert (body["id"], body["status"], body["submitted"]) == (
        str(new.id),
        "pending",
        True,
    )
    assert body["attempts_left"] == 3


@pytest.mark.parametrize(
    ("stored", "told"),
    [
        ("no_face", "no_face"),
        ("many_faces", "many_faces"),
        ("no_match", "no_match"),
        ("no_photos", "no_photos"),
        ("unreadable", "unreadable"),
        ("unavailable", "unavailable"),
        ("something_added_later", "other"),
    ],
)
async def test_a_rejection_names_its_reason_only_from_the_list(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    stored: str,
    told: str,
) -> None:
    user, token = await at_selfie(db, make_user)
    verification, selfie = await submitted(db, fake_providers.storage, user)
    verification.status = selfie.status = ReviewStatus.REJECTED
    selfie.reject_reason = stored
    await db.flush()

    body = (await latest(client, token)).json()

    assert (body["status"], body["reject_reason"]) == ("rejected", told)


async def test_someone_elses_is_never_theirs(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    other, _ = await at_selfie(db, make_user)
    await submitted(db, fake_providers.storage, other)
    _, token = await at_selfie(db, make_user)

    assert (await latest(client, token)).status_code == 404
