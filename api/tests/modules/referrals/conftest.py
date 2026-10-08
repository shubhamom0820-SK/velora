"""Referrals' tests run with referrals running, as T-8.6 built them: the
migrated database has them paused (D-840, `referral_reward_velas` 0), so every
test here starts at T-8.6's 5, in the `db` fixture's rolled-back transaction.
`test_paused.py` sets 0 itself. A test on committed connections can't see it,
and patches the pause check instead."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.modules.referrals.support import REWARD, RUNNING, set_config


@pytest.fixture(autouse=True)
async def referrals_running(db: AsyncSession) -> None:
    await set_config(db, REWARD, str(RUNNING))
