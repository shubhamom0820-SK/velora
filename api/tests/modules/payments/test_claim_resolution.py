"""The admin's claims (T-8.3, D-580): `GET /v1/admin/refund-requests` and
`POST /v1/admin/refund-requests/{id}/resolve`. What can be done is what the
gateway says (the fake's `order_payments`), never the claim's kind:

- **grant:** the capture the webhook never brought, through the webhook's own
  path: `purchase` and `purchase_bonus` under its key, never `admin_grant`
  (D-077); the webhook arriving later is a repeat.
- **refund:** only a charge no Velas can stand against (D-076 rule 3); the
  record is the claim's, and the credited payment's row is never touched.
- **reject:** with a note.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LedgerReason, PaymentStatus, Role
from app.core.providers import FakeProviders
from app.core.providers.payments import FakePayments, PaymentsUnavailable
from app.modules.admin.models import AuditLogEntry
from app.modules.payments import service
from app.modules.payments.models import Payment, RefundRequest
from app.modules.payments.rules import financial_year_of
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import MakeUser
from tests.modules.payments.support import auth, deliver, order, refund

pytestmark = pytest.mark.usefixtures("test_redis")

CLAIMS = "/v1/refund-requests"
FILED = datetime(2026, 10, 8, 6, 0, tzinfo=UTC)
QUEUE = "/v1/admin/refund-requests"


def _resolve_path(claim_id: str) -> str:
    return f"{QUEUE}/{claim_id}/resolve"


async def _admin(make_user: MakeUser, role: Role = Role.ADMIN) -> tuple[uuid.UUID, str]:
    admin, token = await make_user()
    admin.role = role
    return admin.id, token


async def _claim(
    client: AsyncClient, token: str, payment_id: uuid.UUID, reason: str
) -> str:
    response = await client.post(
        CLAIMS,
        json={"payment_id": str(payment_id), "reason": reason},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    claim_id: str = response.json()["id"]
    return claim_id


async def _resolve(
    client: AsyncClient, token: str, claim_id: str, action: str, note: str | None = None
) -> Response:
    body: dict[str, Any] = {"action": action}
    if note is not None:
        body["note"] = note
    return await client.post(_resolve_path(claim_id), json=body, headers=auth(token))


async def _row(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    row = await db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def _stored_claim(db: AsyncSession, claim_id: str) -> RefundRequest:
    claim = await db.scalar(
        select(RefundRequest)
        .where(RefundRequest.id == uuid.UUID(claim_id))
        .execution_options(populate_existing=True)
    )
    assert claim is not None
    return claim


async def _ledger(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[Any, ...]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta, LedgerEntry.ref_id)
        .where(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.reason)
    )
    return [tuple(row) for row in rows]


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    balance = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return int(balance or 0)


async def _audits(db: AsyncSession, actor_id: uuid.UUID) -> list[AuditLogEntry]:
    return list(
        (
            await db.scalars(
                select(AuditLogEntry).where(AuditLogEntry.actor_id == actor_id)
            )
        ).all()
    )


def _error(response: Response) -> dict[str, Any]:
    error: dict[str, Any] = response.json()["error"]
    return error


async def _never_arrived(
    client: AsyncClient, make_user: MakeUser, payments: FakePayments
) -> tuple[User, str, uuid.UUID, str]:
    """A man's pack-30, captured at the gateway, the webhook never delivered."""
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    payments.capture(order_id)
    return man, token, payment_id, order_id


async def _charged_twice(
    client: AsyncClient, make_user: MakeUser, payments: FakePayments
) -> tuple[User, str, uuid.UUID, str]:
    """A man's pack-30, credited, and a second payment captured on its order:
    the webhook for it credited nothing (D-523)."""
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    for signed in (payments.capture(order_id), payments.capture(order_id)):
        assert (
            await client.post(
                "/v1/payments/webhook",
                content=signed.body,
                headers={
                    "Content-Type": "application/json",
                    "X-Razorpay-Signature": signed.signature,
                },
            )
        ).status_code == 200
    return man, token, payment_id, order_id


# --- Grant ------------------------------------------------------------------------------


@pytest.mark.critical
async def test_a_grant_credits_the_purchase_under_the_webhooks_own_key(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """The webhook never came. The grant is `purchase` 30 and the first
    `purchase_bonus` 6, each naming the payment, never `admin_grant`. When the
    webhook does come, it is a repeat: nothing is credited twice."""
    gateway = fake_providers.payments
    man, token, payment_id, order_id = await _never_arrived(client, make_user, gateway)
    man_id = man.id
    [held] = gateway.payments[order_id]
    claim_id = await _claim(client, token, payment_id, "missing_velas")
    admin_id, admin_token = await _admin(make_user)

    response = await _resolve(client, admin_token, claim_id, "grant")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (
        body["status"],
        body["provider_payment_id"],
        body["provider_refund_id"],
    ) == (
        "granted",
        held.id,
        None,
    )
    assert body["payment_status"] == "paid"
    assert await _balance(db, man_id) == 36
    assert await _ledger(db, man_id) == [
        (LedgerReason.PURCHASE, 30, payment_id),
        (LedgerReason.PURCHASE_BONUS, 6, payment_id),
    ]
    row = await _row(db, payment_id)
    assert (row.status, row.provider_payment_id) == (PaymentStatus.PAID, held.id)
    # The gateway's payment, allowlisted (D-524): none of the payer's fields.
    assert row.raw_webhook == {
        "event": "refund_request.granted",
        "payment": {
            "id": held.id,
            "order_id": order_id,
            "amount": 150_000,
            "currency": "INR",
            "status": "captured",
        },
    }
    claim = await _stored_claim(db, claim_id)
    assert claim.resolved_at is not None

    late = gateway.sign(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": held.id,
                        "order_id": order_id,
                        "amount": 150_000,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            },
        }
    )
    await client.post(
        "/v1/payments/webhook",
        content=late.body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": late.signature,
        },
    )

    assert await _balance(db, man_id) == 36
    assert len(await _ledger(db, man_id)) == 2
    [audit] = await _audits(db, admin_id)
    assert audit.action == "refund_requests.resolve"
    assert audit.meta == {
        "refund_request_id": claim_id,
        "action": "grant",
        "status": "granted",
        "provider_payment_id": held.id,
        "provider_refund_id": None,
    }


async def test_a_grant_on_a_credited_payment_is_not_allowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, token, payment_id, _ = await _charged_twice(
        client, make_user, fake_providers.payments
    )
    man_id = man.id
    claim_id = await _claim(client, token, payment_id, "duplicate_charge")
    _, admin_token = await _admin(make_user)

    response = await _resolve(client, admin_token, claim_id, "grant")

    assert response.status_code == 422
    assert (_error(response)["code"], _error(response)["details"]) == (
        "NOT_ALLOWED",
        {"why": "credited"},
    )
    assert await _balance(db, man_id) == 36
    assert (await _stored_claim(db, claim_id)).status == "open"


@pytest.mark.parametrize("gateway_holds", ["nothing", "a failure", "another amount"])
async def test_a_grant_with_no_matching_capture_at_the_gateway_is_not_allowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    gateway_holds: str,
) -> None:
    """The claim's word is never evidence: no captured payment for the order's
    amount, no Velas."""
    gateway = fake_providers.payments
    man, token = await make_user()
    man_id = man.id
    payment_id, order_id = await order(client, token)
    if gateway_holds == "a failure":
        gateway.fail(order_id)
    elif gateway_holds == "another amount":
        gateway.capture(order_id, amount_paise=100)
    claim_id = await _claim(client, token, payment_id, "missing_velas")
    _, admin_token = await _admin(make_user)

    response = await _resolve(client, admin_token, claim_id, "grant")

    assert response.status_code == 422
    assert _error(response)["details"] == {"why": "nothing_to_grant"}
    assert await _ledger(db, man_id) == []
    assert (await _row(db, payment_id)).status is PaymentStatus.CREATED


# --- Refund ----------------------------------------------------------------------------


@pytest.mark.critical
async def test_a_duplicate_charge_is_refunded_and_recorded_on_the_claim(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """The second payment is returned in full, receipt the claim's id. No
    Velas move, the credited row stays `paid` and in turnover (D-483), and the
    refund's own webhook then takes nothing."""
    gateway = fake_providers.payments
    man, token, payment_id, order_id = await _charged_twice(client, make_user, gateway)
    man_id = man.id
    credited, second = gateway.payments[order_id]
    claim_id = await _claim(client, token, payment_id, "duplicate_charge")
    _, admin_token = await _admin(make_user)
    ledger_before = await _ledger(db, man_id)
    paid_at = (await _row(db, payment_id)).paid_at
    assert paid_at is not None
    year = financial_year_of(paid_at)
    turnover_before = await service.turnover(db, year)

    response = await _resolve(client, admin_token, claim_id, "refund")

    assert response.status_code == 200, response.text
    [made] = gateway.refunds
    assert (made.payment_id, made.amount_paise) == (second.id, 150_000)
    assert gateway.receipts == {claim_id}
    body = response.json()
    assert (
        body["status"],
        body["provider_payment_id"],
        body["provider_refund_id"],
    ) == (
        "refunded",
        second.id,
        made.id,
    )
    row = await _row(db, payment_id)
    assert (row.status, row.provider_payment_id) == (PaymentStatus.PAID, credited.id)
    assert await _ledger(db, man_id) == ledger_before
    assert await service.turnover(db, year) == turnover_before

    await deliver(
        client,
        gateway,
        refund("refund.created", order_id, refund_id=made.id, payment_id=second.id),
    )

    assert await _balance(db, man_id) == 36


async def test_the_credited_payment_is_never_refunded(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """One payment, credited: its Velas stand, so its money can't go back
    (D-076 rule 3), whatever the claim says."""
    gateway = fake_providers.payments
    _, token = await make_user()
    payment_id, order_id = await order(client, token)
    signed = gateway.capture(order_id)
    await client.post(
        "/v1/payments/webhook",
        content=signed.body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signed.signature,
        },
    )
    claim_id = await _claim(client, token, payment_id, "duplicate_charge")
    _, admin_token = await _admin(make_user)

    response = await _resolve(client, admin_token, claim_id, "refund")

    assert response.status_code == 422
    assert _error(response)["details"] == {"why": "nothing_to_refund"}
    assert gateway.refunds == []


@pytest.mark.critical
async def test_a_payment_a_grant_could_credit_is_never_refunded(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """The webhook never came: the fix is the grant (D-050), never money back
    for a payment that could still be credited."""
    gateway = fake_providers.payments
    _, token, payment_id, _ = await _never_arrived(client, make_user, gateway)
    claim_id = await _claim(client, token, payment_id, "missing_velas")
    _, admin_token = await _admin(make_user)

    response = await _resolve(client, admin_token, claim_id, "refund")

    assert response.status_code == 422
    assert _error(response)["details"] == {"why": "nothing_to_refund"}
    assert gateway.refunds == []


async def test_a_charge_for_the_wrong_amount_is_refunded(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """The gateway captured an amount that isn't the order's: the webhook
    failed the row and credited nothing (T-8.2), so the money goes back."""
    gateway = fake_providers.payments
    man, token = await make_user()
    man_id = man.id
    payment_id, order_id = await order(client, token)
    signed = gateway.capture(order_id, amount_paise=100)
    await client.post(
        "/v1/payments/webhook",
        content=signed.body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signed.signature,
        },
    )
    claim_id = await _claim(client, token, payment_id, "missing_velas")
    _, admin_token = await _admin(make_user)

    response = await _resolve(client, admin_token, claim_id, "refund")

    assert response.status_code == 200, response.text
    [made] = gateway.refunds
    assert made.amount_paise == 100
    assert response.json()["payment_status"] == "failed"
    assert await _ledger(db, man_id) == []


@pytest.mark.parametrize("call", ["order_payments", "refund"])
async def test_a_gateway_that_doesnt_answer_leaves_the_claim_open(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
    call: str,
) -> None:
    gateway = fake_providers.payments
    _, token, payment_id, _ = await _charged_twice(client, make_user, gateway)
    claim_id = await _claim(client, token, payment_id, "duplicate_charge")
    admin_id, admin_token = await _admin(make_user)

    async def down(*args: object, **kwargs: object) -> None:
        raise PaymentsUnavailable("Razorpay didn't answer: ConnectTimeout")

    monkeypatch.setattr(gateway, call, down)

    response = await _resolve(client, admin_token, claim_id, "refund")

    assert response.status_code == 503
    assert _error(response)["code"] == "PROVIDER_UNAVAILABLE"
    claim = await _stored_claim(db, claim_id)
    assert (claim.status, claim.resolved_at) == ("open", None)
    assert await _audits(db, admin_id) == []


# --- Reject, and what any resolution needs ------------------------------------------------


async def test_a_rejection_says_why(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """Two orders, both credited, are rejected: both purchases completed
    (D-230). Without a note, or with only spaces, a rejection is refused."""
    _, token = await make_user()
    payment_id, _ = await order(client, token)
    claim_id = await _claim(client, token, payment_id, "duplicate_charge")
    _, admin_token = await _admin(make_user)

    bare = await _resolve(client, admin_token, claim_id, "reject")
    blank = await _resolve(client, admin_token, claim_id, "reject", note="   ")
    said = await _resolve(
        client, admin_token, claim_id, "reject", note="Two orders, both credited."
    )

    assert [bare.status_code, blank.status_code] == [400, 400]
    assert {_error(bare)["code"], _error(blank)["code"]} == {"VALIDATION_ERROR"}
    assert said.status_code == 200
    assert (said.json()["status"], said.json()["note"]) == (
        "rejected",
        "Two orders, both credited.",
    )


async def test_a_resolved_claim_is_never_resolved_again(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    gateway = fake_providers.payments
    _, token, payment_id, _ = await _charged_twice(client, make_user, gateway)
    claim_id = await _claim(client, token, payment_id, "duplicate_charge")
    _, admin_token = await _admin(make_user)
    assert (await _resolve(client, admin_token, claim_id, "refund")).status_code == 200

    again = [
        await _resolve(client, admin_token, claim_id, action, note="n")
        for action in ("refund", "grant", "reject")
    ]

    assert {r.status_code for r in again} == {422}
    assert {_error(r)["details"]["why"] for r in again} == {"resolved"}
    assert len(gateway.refunds) == 1


async def test_an_unknown_claim_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, admin_token = await _admin(make_user)

    response = await _resolve(client, admin_token, str(uuid.uuid4()), "reject", "n")

    assert response.status_code == 404
    assert _error(response)["code"] == "NOT_FOUND"


@pytest.mark.parametrize("role", [Role.USER, Role.MODERATOR])
async def test_anyone_but_an_admin_is_forbidden(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    role: Role,
) -> None:
    """A claim moves Velas or money: not a moderator's (D-580)."""
    _, token, payment_id, _ = await _charged_twice(
        client, make_user, fake_providers.payments
    )
    claim_id = await _claim(client, token, payment_id, "duplicate_charge")
    user_id, user_token = await _admin(make_user, role)

    listed = await client.get(QUEUE, headers=auth(user_token))
    resolved = await _resolve(client, user_token, claim_id, "refund")

    assert [listed.status_code, resolved.status_code] == [403, 403]
    assert {_error(listed)["code"], _error(resolved)["code"]} == {"FORBIDDEN"}
    assert fake_providers.payments.refunds == []
    assert await _audits(db, user_id) == []


# --- The queue ---------------------------------------------------------------------------


async def test_the_queue_is_open_claims_oldest_first_a_page_at_a_time_audited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """`created_at` is the transaction's `now()`, one for the whole test, so
    each claim is dated by hand, a minute apart."""
    _, token = await make_user()
    claims = []
    for minute in range(3):
        payment_id, order_id = await order(client, token)
        claim_id = await _claim(client, token, payment_id, "missing_velas")
        await db.execute(
            update(RefundRequest)
            .where(RefundRequest.id == uuid.UUID(claim_id))
            .values(created_at=FILED + timedelta(minutes=minute))
        )
        claims.append((claim_id, order_id))
    admin_id, admin_token = await _admin(make_user)
    await _resolve(client, admin_token, claims[1][0], "reject", note="n")

    first = await client.get(f"{QUEUE}?limit=1", headers=auth(admin_token))
    second = await client.get(
        f"{QUEUE}?limit=1&cursor={first.json()['next_cursor']}",
        headers=auth(admin_token),
    )
    rejected = await client.get(f"{QUEUE}?status=rejected", headers=auth(admin_token))

    assert first.status_code == 200, first.text
    [one] = first.json()["items"]
    assert (one["id"], one["order_id"], one["status"]) == (
        claims[0][0],
        claims[0][1],
        "open",
    )
    assert [c["id"] for c in second.json()["items"]] == [claims[2][0]]
    assert second.json()["next_cursor"] is None
    assert [c["id"] for c in rejected.json()["items"]] == [claims[1][0]]
    lists = [
        a for a in await _audits(db, admin_id) if a.action == "refund_requests.list"
    ]
    assert [a.meta for a in lists] == [
        {"status": "open"},
        {"status": "open"},
        {"status": "rejected"},
    ]
