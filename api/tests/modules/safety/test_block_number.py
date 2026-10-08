"""A block holds against the blocked person's number (T-9.1, D-861, P-400):
the worst case is a harasser someone blocked deleting their account, waiting
out the 29 days, signing up again on the same number and reaching her as a
stranger. Their number's hash survives on the erased row (D-500), and the
erasure keeps other people's blocks of them (D-503), so her block of the old
account holds against the new one, both ways, everywhere. Nobody is told:
her list still shows the one block she made, and lifting it lets him through."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.core.providers import FakeProviders
from app.core.providers.storage import FakeStorage
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, north, person
from tests.modules.safety.support import again_on, blocked, erased, phone_of, unblocked
from tests.modules.safety.test_block_effects import EVERYWHERE, NOWHERE, Side, _seen

pytestmark = [pytest.mark.usefixtures("test_redis"), pytest.mark.critical]


async def _returned(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    storage: FakeStorage,
) -> tuple[str, str, Side, Side]:
    """She blocks him; he is erased and signs up again on his number. Her
    token, his new token, and each one's side towards the other, a Thread
    between the new pair to ask about."""
    woman, woman_token = await person(
        db, make_user, Gender.FEMALE, at=north(1), username="num_her"
    )
    man, _ = await person(db, make_user, Gender.MALE, username="num_him")
    phone, old_id = phone_of(man), man.id
    await blocked(client, woman_token, old_id)
    await erased(db, man, storage)

    again, again_token = await again_on(db, phone, Gender.MALE, username="num_again")
    assert again.id != old_id and again.phone_hash == man.phone_hash
    thread = await make_thread(again, woman, messages=1)
    his = Side(again_token, woman.id, "num_her", thread.id)
    hers = Side(woman_token, again.id, "num_again", thread.id)
    return woman_token, again_token, his, hers


async def test_a_new_account_on_a_blocked_number_is_blocked_both_ways_everywhere(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    _, _, his, hers = await _returned(
        db, client, make_user, make_thread, fake_providers.storage
    )

    assert await _seen(client, his) == NOWHERE
    assert await _seen(client, hers) == NOWHERE


async def test_nobody_is_told_and_lifting_her_one_block_lets_him_through(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    """Her list holds the block she made, of the account she blocked, shown
    deleted: never the new account, which she was never told of."""
    woman_token, _, his, hers = await _returned(
        db, client, make_user, make_thread, fake_providers.storage
    )
    response = await client.get("/v1/blocks", headers=bearer(woman_token))
    [item] = response.json()["items"]
    assert item["user"]["deleted"] is True
    assert item["user"]["id"] != str(hers.other_id)

    await unblocked(client, woman_token, item["user"]["id"])

    assert await _seen(client, his) == EVERYWHERE
    assert await _seen(client, hers) == EVERYWHERE


async def test_a_blocker_who_is_erased_leaves_no_block_behind(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    """D-503 erases a person's own blocks: their choices go with them, and a
    new account on their number starts with none."""
    woman, woman_token = await person(
        db, make_user, Gender.FEMALE, at=north(1), username="gone_her"
    )
    man, man_token = await person(db, make_user, Gender.MALE, username="gone_him")
    phone = phone_of(man)
    await blocked(client, man_token, woman.id)
    await erased(db, man, fake_providers.storage)

    again, again_token = await again_on(db, phone, Gender.MALE, username="gone_again")
    thread = await make_thread(again, woman, messages=1)

    assert await _seen(client, Side(again_token, woman.id, "gone_her", thread.id)) == (
        EVERYWHERE
    )
    assert await _seen(
        client, Side(woman_token, again.id, "gone_again", thread.id)
    ) == (EVERYWHERE)
