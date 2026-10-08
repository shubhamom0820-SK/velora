"""`GET /v1/packs` (T-8.1): a man's store, by his price-test variant, never
empty (D-480); refused to a woman (D-076)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentStatus
from app.modules.payments import rules
from app.modules.payments.models import CreditPack
from tests.conftest import CapturedLogs, MakeUser
from tests.modules.payments.support import LADDER, add_payment, auth, man_in

pytestmark = pytest.mark.usefixtures("test_redis")


def _store(response_json: list[dict[str, Any]]) -> list[tuple[str, int, int, int]]:
    return [
        (p["id"], p["credits"], p["price_paise"], p["bonus_credits"])
        for p in response_json
    ]


@pytest.mark.parametrize("variant", ["A", "B"])
async def test_each_variant_sees_d099s_four_with_the_first_purchase_bonus(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, variant: str
) -> None:
    """B is shown A's packs until T-10.4 (D-480; P-23: B sees four packs).
    Retired packs, `entry-25` included, never appear."""
    _, token = await man_in(make_user, variant)

    response = await client.get("/v1/packs", headers=auth(token))

    assert response.status_code == 200
    assert _store(response.json()) == LADDER


async def test_after_a_purchase_the_bonus_is_gone(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user()
    await add_payment(db, man.id, status=PaymentStatus.PAID)

    response = await client.get("/v1/packs", headers=auth(token))

    assert [p["bonus_credits"] for p in response.json()] == [0, 0, 0, 0]


async def test_a_refunded_purchase_was_still_a_purchase(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user()
    await add_payment(db, man.id, status=PaymentStatus.REFUNDED)

    response = await client.get("/v1/packs", headers=auth(token))

    assert [p["bonus_credits"] for p in response.json()] == [0, 0, 0, 0]


async def test_orders_that_never_paid_leave_the_bonus(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user()
    await add_payment(db, man.id, status=PaymentStatus.CREATED)
    await add_payment(db, man.id, status=PaymentStatus.FAILED)

    response = await client.get("/v1/packs", headers=auth(token))

    assert [p["bonus_credits"] for p in response.json()] == [6, 20, 50, 90]


def test_the_variant_is_stable_and_splits_men() -> None:
    """The same id, the same variant, always; and both variants are used."""
    ids = [uuid.UUID(int=n * 7919) for n in range(1, 401)]

    first = [rules.variant_of(i) for i in ids]
    again = [rules.variant_of(uuid.UUID(str(i))) for i in ids]

    assert first == again
    assert 150 < first.count("B") < 250


def test_every_variant_a_man_can_be_in_is_shown_packs_that_exist() -> None:
    """No variant is shown a variant that has no packs: today, only A has any
    (D-250), so every variant's store is A's."""
    assert {rules.SHOWN_AS.get(v, v) for v in rules.VARIANTS} == {"A"}


async def test_no_man_is_ever_shown_an_empty_store(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Twenty men, whichever variants they land in: four packs each."""
    variants = set()
    for _ in range(20):
        man, token = await make_user()
        variants.add(rules.variant_of(man.id))
        response = await client.get("/v1/packs", headers=auth(token))
        assert response.status_code == 200
        assert len(response.json()) == 4
    assert variants == {"A", "B"}


async def test_a_store_with_no_active_pack_is_a_500_and_an_error_never_a_blank(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
) -> None:
    _, token = await make_user()
    await db.execute(update(CreditPack).values(active=False))

    response = await client.get("/v1/packs", headers=auth(token))

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    [line] = [e for e in captured_logs.events if e["event"] == "payments.store_empty"]
    assert line["log_level"] == "error"
    assert line["variant"] == "A"


async def test_a_woman_is_refused_the_store(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """She can never hold a Vela (D-076), so the server never hands her a store:
    a web bug that opens one fails loudly."""
    _, token = await make_user("female")

    response = await client.get("/v1/packs", headers=auth(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NOT_ALLOWED"


async def test_signed_out_and_unfinished_are_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, unfinished = await make_user(onboarded=False)

    signed_out = await client.get("/v1/packs")
    midway = await client.get("/v1/packs", headers=auth(unfinished))

    assert signed_out.status_code == 401
    assert signed_out.json()["error"]["code"] == "AUTH_REQUIRED"
    assert midway.status_code == 403
    assert midway.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"
