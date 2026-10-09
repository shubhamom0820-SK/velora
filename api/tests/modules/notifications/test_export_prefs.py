"""A copy of your own data (T-9.6, D-502) carries every notification setting
there is: `Prefs`' fields, so a setting added later (T-9.4's `gift` and
`album` were nearly missed) fails here until the export names it."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers.storage import FakeStorage
from app.modules.account.service import export_document
from app.modules.notifications.models import NotificationPrefs
from app.modules.notifications.schemas import Prefs
from tests.conftest import MakeUser, make_test_settings


async def test_the_export_carries_every_notification_setting(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    await db.execute(
        update(NotificationPrefs)
        .where(NotificationPrefs.user_id == user.id)
        .values(gift=False, album=False, generic_text=True)
    )

    document = await export_document(db, user, FakeStorage(), make_test_settings())

    settings = document["notification_settings"]
    assert set(settings) == set(Prefs.model_fields)
    assert (settings["gift"], settings["album"], settings["generic_text"]) == (
        False,
        False,
        True,
    )
