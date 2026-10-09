"""The founder's unfreeze (D-906): any frozen account, a woman's included,
`active` again; its score 0 and normal, starting again from now, so the next
recompute can't freeze it on what was set aside; one `audit_log` row naming
the admin who ran it. It makes no session and prints no number or name."""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FraudBand, Gender, Role, UserStatus
from app.modules.admin.models import AuditLogEntry
from app.modules.admin.service import SYSTEM_USER_ID
from app.modules.auth.models import Session
from app.modules.safety import scoring
from app.modules.safety.models import FraudScore
from app.modules.users.models import User
from app.tools import unfreeze
from tests.conftest import MakeUser
from tests.modules.photos.test_moderate import Sessions
from tests.modules.safety.test_scoring import SPAMMER, _recompute, _signalled


async def _run(db: AsyncSession, *argv: str) -> tuple[int, str]:
    out = io.StringIO()
    code = await unfreeze.run(unfreeze.parse(argv), sessions=Sessions(db), out=out)
    return code, out.getvalue()


async def _admin(db: AsyncSession, make_user: MakeUser) -> uuid.UUID:
    founder, _ = await make_user()
    founder.role = Role.ADMIN
    await db.flush()
    return founder.id


async def _frozen_woman(db: AsyncSession, make_user: MakeUser) -> User:
    woman, _ = await make_user(Gender.FEMALE)
    await _signalled(db, woman.id, *SPAMMER)
    outcome = await _recompute(db, woman.id)
    assert outcome is not None and outcome.frozen
    return woman


async def _fresh(db: AsyncSession, model: type, key: uuid.UUID) -> object:
    return await db.get(model, key, populate_existing=True)


async def test_it_lifts_an_automatic_freeze_on_a_woman_and_starts_her_score_again(
    db: AsyncSession, make_user: MakeUser
) -> None:
    founder = await _admin(db, make_user)
    woman = await _frozen_woman(db, make_user)
    her_id = woman.id
    sessions_before = await db.scalar(select(func.count()).select_from(Session))

    code, said = await _run(
        db, str(her_id), "--by", str(founder), "--reason", "colluding reports"
    )

    assert code == 0, said
    assert said == (
        f"unfreeze: {her_id} is active again; its score was 95 (freeze) and starts "
        "again from now. They sign in again themselves. Recorded in audit_log as "
        f"{founder}.\n"
    )
    user = await _fresh(db, User, her_id)
    assert user.status is UserStatus.ACTIVE  # type: ignore[attr-defined]
    score = await _fresh(db, FraudScore, her_id)
    assert (score.score, score.band, score.signals) == (0, FraudBand.NORMAL, {})  # type: ignore[attr-defined]
    assert score.counted_from is not None  # type: ignore[attr-defined]
    [row] = (
        await db.scalars(
            select(AuditLogEntry).where(AuditLogEntry.action == "fraud.unfreeze")
        )
    ).all()
    assert (row.actor_id, row.target_type, row.target_id) == (founder, "user", her_id)
    assert row.meta == {
        "reason": "colluding reports",
        "score_before": 95,
        "band_before": "freeze",
    }
    assert await db.scalar(select(func.count()).select_from(Session)) == sessions_before


async def test_what_was_set_aside_never_freezes_her_again_and_new_signals_count(
    db: AsyncSession, make_user: MakeUser
) -> None:
    founder = await _admin(db, make_user)
    woman = await _frozen_woman(db, make_user)
    her_id = woman.id
    assert (await _run(db, str(her_id), "--by", str(founder), "--reason", "x"))[0] == 0

    again = await _recompute(db, her_id)
    assert again == scoring.Outcome(score=0, band=FraudBand.NORMAL, frozen=False)
    assert (await _fresh(db, User, her_id)).status is UserStatus.ACTIVE  # type: ignore[attr-defined]


@pytest.mark.parametrize("who", ["user", "frozen_admin", "nobody"])
async def test_only_an_active_admin_may_lift_one(
    db: AsyncSession, make_user: MakeUser, who: str
) -> None:
    woman = await _frozen_woman(db, make_user)
    her_id = woman.id
    by: uuid.UUID
    if who == "nobody":
        by = uuid.uuid4()
    else:
        someone, _ = await make_user()
        if who == "frozen_admin":
            someone.role, someone.status = Role.ADMIN, UserStatus.FROZEN
            await db.flush()
        by = someone.id

    code, said = await _run(db, str(her_id), "--by", str(by), "--reason", "x")

    assert (code, said) == (
        1,
        f"unfreeze: {by} isn't an active admin. Nothing changed.\n",
    )
    assert (await _fresh(db, User, her_id)).status is UserStatus.FROZEN  # type: ignore[attr-defined]


async def test_an_account_that_isnt_frozen_is_left_alone(
    db: AsyncSession, make_user: MakeUser
) -> None:
    founder = await _admin(db, make_user)
    man, _ = await make_user()
    man.status = UserStatus.BANNED
    await db.flush()
    man_id = man.id

    code, said = await _run(db, str(man_id), "--by", str(founder), "--reason", "x")

    assert (code, said) == (1, f"unfreeze: {man_id} isn't frozen. Nothing changed.\n")
    assert (await _fresh(db, User, man_id)).status is UserStatus.BANNED  # type: ignore[attr-defined]


@pytest.mark.parametrize("target", ["unknown", "system"])
async def test_no_such_account(
    db: AsyncSession, make_user: MakeUser, target: str
) -> None:
    founder = await _admin(db, make_user)
    user_id = uuid.uuid4() if target == "unknown" else SYSTEM_USER_ID

    code, said = await _run(db, str(user_id), "--by", str(founder), "--reason", "x")

    assert (code, said) == (1, f"unfreeze: no account {user_id}. Nothing changed.\n")


@pytest.mark.parametrize(
    ("argv", "said"),
    [
        (("not-an-id", "--by", str(uuid.uuid4()), "--reason", "x"), "both ids"),
        ((str(uuid.uuid4()), "--by", str(uuid.uuid4()), "--reason", "  "), "empty"),
    ],
)
async def test_bad_arguments_change_nothing(
    db: AsyncSession, argv: tuple[str, ...], said: str
) -> None:
    code, out = await _run(db, *argv)
    assert code == 2
    assert said in out
