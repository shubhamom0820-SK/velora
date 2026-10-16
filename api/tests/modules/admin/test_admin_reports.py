"""`GET /v1/admin/reports` and `POST /v1/admin/reports/{id}/resolve` (T-9.5,
D-921): the queue, oldest first, each with the day it has (P-761); `none`
dismisses, `warn` (recorded only), `freeze` and `ban` action, the last two as
the status changes they are, a ban an admin's alone. The note is kept in
`audit_log.meta`, never a column.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import ReportReason, ReportStatus, Role, UserStatus
from app.modules.auth import repository as auth_repository
from app.modules.safety.models import Report
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.admin.support import ADMIN, REASON, audits, auth, error, fresh, staff

pytestmark = pytest.mark.usefixtures("test_redis")

QUEUE = f"{ADMIN}/reports"


async def _report(
    db: AsyncSession, reporter: uuid.UUID, reported: uuid.UUID, *, minutes_ago: int = 0
) -> uuid.UUID:
    """A report, dated by hand: `created_at` is the test transaction's `now()`."""
    report = Report(
        reporter_id=reporter,
        reported_id=reported,
        reason=ReportReason.HARASS,
        details="Kept messaging after I said no.",
        created_at=clock.now() - timedelta(minutes=minutes_ago),
    )
    db.add(report)
    await db.flush()
    return report.id


async def _pair(make_user: MakeUser) -> tuple[uuid.UUID, uuid.UUID]:
    woman, _ = await make_user("female")
    man, _ = await make_user()
    return woman.id, man.id


async def _resolve(
    client: AsyncClient,
    token: str,
    report_id: uuid.UUID,
    action: str,
    note: str = REASON,
) -> Response:
    return await client.post(
        f"{QUEUE}/{report_id}/resolve",
        json={"action": action, "note": note},
        headers=auth(token),
    )


async def test_the_queue_is_open_reports_oldest_first_with_their_day_audited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman_id, man_id = await _pair(make_user)
    newer = await _report(db, woman_id, man_id, minutes_ago=5)
    older = await _report(db, woman_id, man_id, minutes_ago=50)

    first = await client.get(QUEUE, params={"limit": 1}, headers=auth(token))
    second = await client.get(
        QUEUE,
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
        headers=auth(token),
    )

    assert first.status_code == 200, first.text
    [item] = first.json()["items"]
    assert item["id"] == str(older)
    assert (item["reporter"]["id"], item["reported"]["id"]) == (
        str(woman_id),
        str(man_id),
    )
    assert item["status"] == "open" and item["action"] is None
    created = clock.now() - timedelta(minutes=50)
    assert item["due_at"][:16] == (created + timedelta(hours=24)).isoformat()[:16]
    assert [i["id"] for i in second.json()["items"]] == [str(newer)]
    assert second.json()["next_cursor"] is None
    listed = await audits(db, moderator_id, "reports.list")
    assert [entry.meta for entry in listed] == [{"status": "open"}] * 2


async def test_none_dismisses_with_the_note_in_the_audit_log(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman_id, man_id = await _pair(make_user)
    report_id = await _report(db, woman_id, man_id)

    response = await _resolve(client, token, report_id, "none")

    assert response.status_code == 204, response.text
    report = await fresh(db, Report, report_id)
    assert (report.status, report.action, report.resolved_by) == (
        ReportStatus.DISMISSED,
        "none",
        moderator_id,
    )
    assert report.resolved_at is not None
    [entry] = await audits(db, moderator_id, "report.resolve")
    assert (entry.target_type, entry.target_id) == ("report", report_id)
    assert entry.meta == {"action": "none", "note": REASON, "status_changed": False}
    assert (await fresh(db, User, man_id)).status is UserStatus.ACTIVE


async def test_a_warning_actions_it_and_changes_nothing_else(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)
    woman_id, man_id = await _pair(make_user)
    report_id = await _report(db, woman_id, man_id)

    response = await _resolve(client, token, report_id, "warn")

    assert response.status_code == 204, response.text
    report = await fresh(db, Report, report_id)
    assert (report.status, report.action) == (ReportStatus.ACTIONED, "warn")
    assert (await fresh(db, User, man_id)).status is UserStatus.ACTIVE


async def test_a_freeze_actions_it_and_freezes_the_reported(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman_id, man_id = await _pair(make_user)
    report_id = await _report(db, woman_id, man_id)

    response = await _resolve(client, token, report_id, "freeze")

    assert response.status_code == 204, response.text
    assert (await fresh(db, Report, report_id)).action == "freeze"
    assert (await fresh(db, User, man_id)).status is UserStatus.FROZEN
    [frozen] = await audits(db, moderator_id, "user.freeze")
    assert frozen.meta is not None and frozen.meta["report_id"] == str(report_id)
    [resolved] = await audits(db, moderator_id, "report.resolve")
    assert resolved.meta is not None and resolved.meta["status_changed"] is True


async def test_freezing_someone_already_frozen_resolves_and_leaves_them_frozen(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """T-9.2's three reports freeze at once; the report is still resolved."""
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman_id, man_id = await _pair(make_user)
    man = await fresh(db, User, man_id)
    man.status = UserStatus.FROZEN
    await db.flush()
    report_id = await _report(db, woman_id, man_id)

    response = await _resolve(client, token, report_id, "freeze")

    assert response.status_code == 204, response.text
    assert (await fresh(db, Report, report_id)).status is ReportStatus.ACTIONED
    assert await audits(db, moderator_id, "user.freeze") == []
    [resolved] = await audits(db, moderator_id, "report.resolve")
    assert resolved.meta is not None and resolved.meta["status_changed"] is False


async def test_a_moderator_never_bans_from_a_report(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman_id, man_id = await _pair(make_user)
    report_id = await _report(db, woman_id, man_id)

    response = await _resolve(client, token, report_id, "ban")

    assert response.status_code == 403
    assert error(response)["code"] == "FORBIDDEN"
    assert (await fresh(db, Report, report_id)).status is ReportStatus.OPEN
    assert (await fresh(db, User, man_id)).status is UserStatus.ACTIVE
    assert await audits(db, moderator_id) == []


async def test_an_admins_ban_actions_it_and_bans_the_number(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user)
    woman_id, man_id = await _pair(make_user)
    phone_hash = (await fresh(db, User, man_id)).phone_hash
    report_id = await _report(db, woman_id, man_id)

    response = await _resolve(client, token, report_id, "ban")

    assert response.status_code == 204, response.text
    assert (await fresh(db, Report, report_id)).action == "ban"
    assert (await fresh(db, User, man_id)).status is UserStatus.BANNED
    assert await auth_repository.is_banned(db, phone_hash)


async def test_a_report_is_resolved_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman_id, man_id = await _pair(make_user)
    report_id = await _report(db, woman_id, man_id)
    await _resolve(client, token, report_id, "none")

    again = await _resolve(client, token, report_id, "warn")

    assert again.status_code == 422
    assert error(again)["details"]["why"] == "resolved"
    assert (await fresh(db, Report, report_id)).action == "none"
    assert len(await audits(db, moderator_id, "report.resolve")) == 1


async def test_freezing_from_a_report_about_a_deleted_account_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-902: a freeze reaches who can sign in. Ban or dismiss it instead."""
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman_id, man_id = await _pair(make_user)
    man = await fresh(db, User, man_id)
    man.status = UserStatus.DELETED
    await db.flush()
    report_id = await _report(db, woman_id, man_id)

    response = await _resolve(client, token, report_id, "freeze")

    assert error(response)["details"]["why"] == "deleted"
    assert (await fresh(db, Report, report_id)).status is ReportStatus.OPEN
    assert await audits(db, moderator_id) == []


@pytest.mark.parametrize(
    "body",
    [
        {"action": "none"},
        {"action": "none", "note": "short"},
        {"action": "delete", "note": REASON},
    ],
    ids=["no note", "a short note", "an action nobody has"],
)
async def test_a_body_out_of_shape_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, body: dict[str, str]
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)

    response = await client.post(
        f"{QUEUE}/{uuid.uuid4()}/resolve", json=body, headers=auth(token)
    )

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_an_unknown_report_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)

    response = await _resolve(client, token, uuid.uuid4(), "none")

    assert response.status_code == 404
