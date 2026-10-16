"""The panel's record and dashboard (T-9.5): `GET /v1/admin/audit` (the system
user named as such, D-905), `GET /v1/admin/freezes` (the accounts frozen now,
automatic ones marked, P-800, D-928), and `GET /v1/admin/metrics` (counts for
staff, revenue an admin's alone, D-926). Each read is audited itself.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import PaymentStatus, Role, UserStatus
from app.modules.admin import service as admin_service
from app.modules.admin.models import AuditLogEntry
from app.modules.safety import scoring
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.admin.support import ADMIN, REASON, audits, auth, fresh, staff
from tests.modules.payments.support import add_payment

pytestmark = pytest.mark.usefixtures("test_redis")


# --- The audit log ---------------------------------------------------------------------


async def test_the_log_is_newest_first_names_the_system_user_and_filters_by_action(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id
    db.add(
        AuditLogEntry(
            actor_id=admin_service.SYSTEM_USER_ID,
            action="fraud.freeze",
            target_type="user",
            target_id=man_id,
            meta={"rule": "score", "score": 85},
            created_at=clock.now() - timedelta(minutes=5),
        )
    )
    await db.flush()

    everything = await client.get(f"{ADMIN}/audit", headers=auth(token))
    freezes = await client.get(
        f"{ADMIN}/audit", params={"action": "fraud.freeze"}, headers=auth(token)
    )

    assert everything.status_code == 200, everything.text
    # Other tests in the run may have committed freezes of their own.
    assert {item["action"] for item in freezes.json()["items"]} == {"fraud.freeze"}
    [frozen] = [
        item for item in freezes.json()["items"] if item["target_id"] == str(man_id)
    ]
    assert (frozen["actor_is_system"], frozen["target_id"], frozen["meta"]) == (
        True,
        str(man_id),
        {"rule": "score", "score": 85},
    )
    times = [item["created_at"] for item in everything.json()["items"]]
    assert times == sorted(times, reverse=True)
    reads = await audits(db, admin_id, "audit.read")
    # One transaction's rows share `created_at`, so compare without order.
    assert sorted(str(entry.meta) for entry in reads) == sorted(
        [str({"action": None}), str({"action": "fraud.freeze"})]
    )


# --- Freezes (P-800) -------------------------------------------------------------------


async def test_the_accounts_frozen_now_automatic_ones_marked_newest_first(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    by_score, _ = await make_user()
    by_staff, _ = await make_user()
    lifted, _ = await make_user()
    by_score_id, by_staff_id = by_score.id, by_staff.id
    by_score.status = by_staff.status = UserStatus.FROZEN
    db.add_all(
        [
            AuditLogEntry(
                actor_id=admin_service.SYSTEM_USER_ID,
                action=scoring.FREEZE,
                target_type="user",
                target_id=by_score_id,
                meta={"rule": "reports", "score": 81},
                created_at=clock.now() - timedelta(hours=2),
            ),
            AuditLogEntry(
                actor_id=moderator_id,
                action="user.freeze",
                target_type="user",
                target_id=by_staff_id,
                meta={"reason": REASON},
                created_at=clock.now() - timedelta(hours=1),
            ),
            # Frozen once and lifted: not frozen now, so not listed.
            AuditLogEntry(
                actor_id=admin_service.SYSTEM_USER_ID,
                action=scoring.FREEZE,
                target_type="user",
                target_id=lifted.id,
                meta={"rule": "score", "score": 90},
            ),
        ]
    )
    await db.flush()

    response = await client.get(f"{ADMIN}/freezes", headers=auth(token))

    assert response.status_code == 200, response.text
    assert [
        (i["user"]["id"], i["automatic"], i["rule"], i["score"])
        for i in response.json()["items"]
    ] == [
        (str(by_staff_id), False, None, None),
        (str(by_score_id), True, "reports", 81),
    ]
    assert len(await audits(db, moderator_id, "freezes.list")) == 1


# --- The dashboard ---------------------------------------------------------------------


async def test_staff_see_counts_and_only_an_admin_sees_revenue(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, admin_token = await staff(make_user)
    moderator_id, moderator_token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    frozen, _ = await make_user()
    frozen.status = UserStatus.FROZEN
    frozen_id = frozen.id
    await add_payment(
        db,
        man.id,
        status=PaymentStatus.PAID,
        amount_paise=49_900,
        paid_at=clock.now() - timedelta(hours=1),
    )
    await db.flush()

    as_admin = await client.get(f"{ADMIN}/metrics", headers=auth(admin_token))
    as_moderator = await client.get(f"{ADMIN}/metrics", headers=auth(moderator_token))

    assert as_admin.status_code == 200, as_admin.text
    figures = as_admin.json()
    assert figures["frozen"] >= 1 and figures["users_by_status"]["frozen"] >= 1
    assert figures["signups_24h"] >= 4
    assert figures["revenue"]["last_7_days_paise"] >= 49_900
    assert figures["revenue"]["financial_year_paise"] >= 49_900
    assert as_moderator.json()["revenue"] is None
    assert [e.meta for e in await audits(db, admin_id, "metrics.read")] == [
        {"revenue": True}
    ]
    assert [e.meta for e in await audits(db, moderator_id, "metrics.read")] == [
        {"revenue": False}
    ]
    assert (await fresh(db, User, frozen_id)).status is UserStatus.FROZEN
