"""A referral's reward (T-8.6): `referral_reward_velas` to each man on it, when
the referee's selfie matches or their first purchase is captured, whichever
comes first, once. Never a woman (D-076, D-690). A referrer who no longer
stands, or is past `referral_rewards_max`, gets nothing; the referee still
does (D-692, D-693). Both men's wallets are locked in `user_id` order, inside
the trigger's own transaction (D-077, P-63), so either order of ids works.

Every test runs in the `db` fixture's rolled-back transaction: a committed
ledger row could never be deleted (tests/committed.py). Two rewards at once
are forced inside it, T-8.11's way: the second runs whole while the first is
inside its own, at the point the guard under test protects."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, OnboardingStep, UserStatus
from app.core.providers import FakeProviders
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.core.queue import FakeQueue
from app.modules.referrals import service
from app.modules.users.models import User
from app.modules.verification import service as verification_service
from app.modules.wallet import service as wallet_service
from tests.conftest import CapturedLogs, MakeUser
from tests.modules.payments.support import captured, deliver, order
from tests.modules.photos.test_moderate import Sessions
from tests.modules.referrals.support import (
    REWARD,
    REWARDS_MAX,
    SETTINGS,
    ledger,
    purchase,
    refer,
    referral_of,
    rewards,
    selfie_matches,
    set_config,
    two_men,
)
from tests.modules.verification.support import at_selfie, face_photo, submitted

pytestmark = pytest.mark.usefixtures("test_redis")


def _paid(
    referee_id: uuid.UUID, user_id: uuid.UUID, amount: int = 5
) -> tuple[Any, ...]:
    """The one `referral_reward` entry a man on the referee's referral gets."""
    return (
        amount,
        "referral",
        referee_id,
        f"{user_id}:referral_reward:{referee_id}",
    )


async def _rewarded(db: AsyncSession, referee_id: uuid.UUID) -> bool:
    found = await referral_of(db, referee_id)
    assert found is not None
    return found["rewarded_at"] is not None


async def _status(db: AsyncSession, user_id: uuid.UUID, status: UserStatus) -> None:
    await db.execute(update(User).where(User.id == user_id).values(status=status))


# --- The selfie's match ------------------------------------------------------------


@pytest.mark.critical  # T-8.6, P-63: two men credited in one transaction
@pytest.mark.parametrize("referrer_below", [True, False], ids=["below", "above"])
async def test_a_mans_selfie_matching_pays_both_men_once(
    db: AsyncSession, make_user: MakeUser, referrer_below: bool
) -> None:
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    if (referrer.id < referee.id) is not referrer_below:
        referrer, _ = await make_user()
        while (referrer.id < referee.id) is not referrer_below:
            referrer, _ = await make_user()
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)

    assert await selfie_matches(db, referee) == "approved"

    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id)]
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]
    assert await _rewarded(db, referee_id)


async def test_a_womans_selfie_pays_her_referrer_and_never_her(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Every woman's selfie is matched (D-008), so this is the case "reward
    both" would have reached: she has no ledger row at all (D-076)."""
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.FEMALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)

    assert await selfie_matches(db, referee) == "approved"

    assert await ledger(db, referee_id) == []
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]
    assert await _rewarded(db, referee_id)


async def test_two_women_are_rewarded_with_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    referrer, _ = await make_user("female")
    referee, _ = await at_selfie(db, make_user, Gender.FEMALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)

    assert await selfie_matches(db, referee) == "approved"

    assert await ledger(db, referee_id) == await ledger(db, referrer_id) == []
    assert await _rewarded(db, referee_id)


async def test_a_selfie_that_doesnt_match_rewards_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:

    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    storage, facematch = FakeStorage(), FakeFaceMatch()
    await face_photo(db, storage, referee)
    verification, _ = await submitted(db, storage, referee)
    facematch.next = FaceMatch(model="fake", faces_in_selfie=1, similarities=(0.1,))

    assert (
        await verification_service.verify(
            Sessions(db),
            verification.id,
            storage=storage,
            facematch=facematch,
            queue=FakeQueue(),
            settings=SETTINGS,
            via="queue",
        )
        == "no_match"
    )

    assert await ledger(db, referee_id) == await ledger(db, referrer_id) == []
    assert not await _rewarded(db, referee_id)


# --- The first purchase -----------------------------------------------------------


@pytest.mark.critical  # T-8.6, P-63: inside the webhook's own transaction
@pytest.mark.parametrize("referrer_below", [True, False], ids=["below", "above"])
async def test_a_first_purchase_pays_both_men_inside_the_capture(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    referrer_below: bool,
) -> None:
    """The capture locks the buyer's wallet for his purchase; the reward runs
    first, so a referrer below him is locked before him, never after (a
    `WalletMisuse`, and a webhook Razorpay retries forever)."""
    (referee, token), (referrer, _) = await two_men(
        make_user, referrer_below=referrer_below
    )
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)

    response = await purchase(db, client, fake_providers, token)

    assert response.status_code == 200, response.text
    reasons = [row[0] for row in await ledger(db, referee_id)]
    assert sorted(reasons) == ["purchase", "purchase_bonus", "referral_reward"]
    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id)]
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]
    assert await _rewarded(db, referee_id)


async def test_a_man_referred_by_a_woman_is_paid_and_she_never_is(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    referrer, _ = await make_user("female")
    referee, token = await make_user()
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)

    assert (await purchase(db, client, fake_providers, token)).status_code == 200

    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id)]
    assert await ledger(db, referrer_id) == []


async def test_the_same_capture_delivered_again_pays_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:

    referrer, _ = await make_user()
    referee, token = await make_user()
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    our_id, order_id = await order(client, token)
    amount = await db.scalar(
        text("select amount_paise from payments where id = :p"), {"p": our_id}
    )
    body = captured(order_id, payment_id="pay_R1", amount=amount)

    for _ in range(5):
        assert (await deliver(client, fake_providers.payments, body)).status_code == 200

    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id)]
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]


@pytest.mark.critical  # T-8.6 "whichever first": never twice
async def test_a_selfie_then_a_purchase_rewards_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    referrer, _ = await make_user()
    referee, token = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    assert await selfie_matches(db, referee) == "approved"
    await db.execute(
        update(User)
        .where(User.id == referee_id)
        .values(onboarding_step=OnboardingStep.DONE)
    )

    assert (await purchase(db, client, fake_providers, token)).status_code == 200

    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id)]
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]


async def test_a_purchase_with_no_referral_is_only_a_purchase(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, token = await make_user()
    man_id = man.id

    assert (await purchase(db, client, fake_providers, token)).status_code == 200

    assert await rewards(db, man_id) == []


# --- How many: app_config ----------------------------------------------------------


async def test_tuned_it_pays_that_many(db: AsyncSession, make_user: MakeUser) -> None:
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    await set_config(db, REWARD, "8")

    await selfie_matches(db, referee)

    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id, 8)]
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id, 8)]


@pytest.mark.parametrize(
    ("value", "warning"),
    [("0", None), ("-5", "referrals.reward_config_negative")],
    ids=["zero", "negative"],
)
async def test_at_zero_or_below_it_is_rewarded_with_nothing(
    db: AsyncSession,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
    value: str,
    warning: str | None,
) -> None:
    """The setting at the moment of the event decides: 0 rewards it, with
    nothing, and a later trigger finds it done."""
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    await set_config(db, REWARD, value)

    assert await selfie_matches(db, referee) == "approved"

    assert await ledger(db, referee_id) == await ledger(db, referrer_id) == []
    assert await _rewarded(db, referee_id)
    lines = [e for e in captured_logs.events if e["log_level"] == "warning"]
    assert [e["event"] for e in lines] == ([warning] if warning else [])


@pytest.mark.parametrize("value", [None, '"five"'], ids=["no row", "not a number"])
async def test_a_missing_setting_skips_with_a_warning_and_a_later_trigger_pays(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
    value: str | None,
) -> None:
    """A lost row never fails the selfie's decision, says so at warning, and
    leaves the referral unrewarded for the next trigger, once the row is back."""
    referrer, _ = await make_user()
    referee, token = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    await set_config(db, REWARD, value)

    assert await selfie_matches(db, referee) == "approved"

    assert await ledger(db, referee_id) == await ledger(db, referrer_id) == []
    assert not await _rewarded(db, referee_id)
    [line] = [
        e
        for e in captured_logs.events
        if e["event"] == "referrals.reward_config_missing"
    ]
    assert line["log_level"] == "warning"
    assert (line["referee_id"], line["key"]) == (str(referee_id), REWARD)

    if value is None:
        await db.execute(
            text("insert into app_config (key, value) values (:k, '5'::jsonb)"),
            {"k": REWARD},
        )
    else:
        await set_config(db, REWARD, "5")
    await db.execute(
        update(User)
        .where(User.id == referee_id)
        .values(onboarding_step=OnboardingStep.DONE)
    )
    assert (await purchase(db, client, fake_providers, token)).status_code == 200
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]


# --- Who still stands (D-693) ----------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [UserStatus.BANNED, UserStatus.FROZEN, UserStatus.DELETED],
    ids=["banned", "frozen", "deleted"],
)
async def test_a_referrer_who_no_longer_stands_gets_nothing_and_the_referee_is_paid(
    db: AsyncSession, make_user: MakeUser, status: UserStatus
) -> None:
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    await _status(db, referrer_id, status)

    await selfie_matches(db, referee)

    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id)]
    assert await ledger(db, referrer_id) == []


async def test_a_paused_referrer_is_paid(db: AsyncSession, make_user: MakeUser) -> None:
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    await _status(db, referrer_id, UserStatus.PAUSED)

    await selfie_matches(db, referee)

    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]


@pytest.mark.parametrize("referrer_below", [True, False], ids=["below", "above"])
async def test_a_referee_who_no_longer_stands_gets_nothing_and_the_referrer_is_paid(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    referrer_below: bool,
) -> None:
    """A capture still arrives for a man frozen since he paid (D-077): his
    purchase is credited, the reward isn't. His wallet is still locked with the
    referrer's, in order, before his purchase locks it again: in either order
    of ids (P-63; found by this test with the referrer locked alone)."""
    (referee, token), (referrer, _) = await two_men(
        make_user, referrer_below=referrer_below
    )
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)

    our_id, order_id = await order(client, token)
    await _status(db, referee_id, UserStatus.FROZEN)
    amount = await db.scalar(
        text("select amount_paise from payments where id = :p"), {"p": our_id}
    )
    response = await deliver(
        client,
        fake_providers.payments,
        captured(order_id, payment_id="pay_R1", amount=amount),
    )

    assert response.status_code == 200
    assert await rewards(db, referee_id) == []
    assert "purchase" in [row[0] for row in await ledger(db, referee_id)]
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]


# --- The cap (D-692) ---------------------------------------------------------------


async def _referees_rewarded(
    db: AsyncSession, make_user: MakeUser, referrer: User, n: int
) -> None:
    for _ in range(n):
        referee, _ = await at_selfie(db, make_user, Gender.MALE)
        await refer(db, referee, referrer)
        assert await selfie_matches(db, referee) == "approved"


@pytest.mark.critical  # D-692: one referrer's farm stops at the cap
async def test_past_the_cap_the_referrer_gets_nothing_and_the_referee_is_paid(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    """At the migrated 10: ten referees pay him, the eleventh doesn't."""
    referrer, _ = await make_user()
    referrer_id = referrer.id
    await _referees_rewarded(db, make_user, referrer, 10)
    assert len(await rewards(db, referrer_id)) == 10
    eleventh, _ = await at_selfie(db, make_user, Gender.MALE)
    eleventh_id = eleventh.id
    await refer(db, eleventh, referrer)

    assert await selfie_matches(db, eleventh) == "approved"

    assert len(await rewards(db, referrer_id)) == 10
    assert await rewards(db, eleventh_id) == [_paid(eleventh_id, eleventh_id)]
    assert await _rewarded(db, eleventh_id)
    [line] = [
        e for e in captured_logs.events if e["event"] == "referrals.referrer_at_cap"
    ]
    assert (line["cap"], line["referrer_id"]) == (10, str(referrer_id))


async def test_his_own_reward_as_a_referee_never_counts_toward_his_cap(
    db: AsyncSession, make_user: MakeUser
) -> None:
    referrer, _ = await make_user()
    referrer_id = referrer.id
    his_referrer, _ = await make_user()
    referrer.onboarding_step = OnboardingStep.SELFIE
    await db.flush()
    await refer(db, referrer, his_referrer)
    await selfie_matches(db, referrer)
    assert len(await rewards(db, referrer_id)) == 1
    await set_config(db, REWARDS_MAX, "1")
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    referee_id = referee.id
    await refer(db, referee, referrer)

    await selfie_matches(db, referee)

    # One outer transaction, so one `created_at`: compared as a set.
    assert set(await rewards(db, referrer_id)) == {
        _paid(referrer_id, referrer_id),
        _paid(referee_id, referrer_id),
    }


async def test_a_missing_cap_pays_no_referrer_and_says_so(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    """A limit that fails open is no limit: no row, no referrer paid."""
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    await set_config(db, REWARDS_MAX, None)

    await selfie_matches(db, referee)

    assert await ledger(db, referrer_id) == []
    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id)]
    [line] = [
        e for e in captured_logs.events if e["event"] == "referrals.cap_config_missing"
    ]
    assert line["log_level"] == "warning"


@pytest.mark.critical  # D-692: the cap counted under his wallet's lock
async def test_two_rewards_at_once_one_short_of_the_cap_pay_him_once(
    db: AsyncSession,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forced: the first reward is about to lock the wallets when the second
    runs whole, paying him his last. The first then counts under the lock,
    sees it, and pays only its referee. Counted before the lock, it would see
    one short and pay him past the cap."""
    referrer, _ = await make_user()
    referrer_id = referrer.id
    await set_config(db, REWARDS_MAX, "2")
    await _referees_rewarded(db, make_user, referrer, 1)
    first, _ = await make_user()
    second, _ = await make_user()
    first_id, second_id = first.id, second.id
    await refer(db, first, referrer)
    await refer(db, second, referrer)
    real_lock = wallet_service.lock_wallets
    inner: list[None] = []

    async def overtaken(session: AsyncSession, user_ids: Any) -> None:
        if not inner:
            inner.append(None)
            await _beside(session, lambda s: service.reward(s, second_id, "purchase"))
        await real_lock(session, user_ids)

    monkeypatch.setattr(wallet_service, "lock_wallets", overtaken)

    await service.reward(db, first_id, "purchase")

    assert inner == [None]
    assert len(await rewards(db, referrer_id)) == 2
    assert {row[2] for row in await rewards(db, referrer_id)} >= {second_id}
    assert first_id not in {row[2] for row in await rewards(db, referrer_id)}
    assert await rewards(db, first_id) == [_paid(first_id, first_id)]
    assert await rewards(db, second_id) == [_paid(second_id, second_id)]


@pytest.mark.critical  # D-077: two triggers at once pay each man once
async def test_two_triggers_at_once_pay_each_man_once(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forced: the first has read the referral as unrewarded and is about to
    lock the wallets when the second runs whole and pays both. The first then
    credits the same keys: repeats (D-077), nothing paid twice."""
    referrer, _ = await make_user()
    referee, _ = await make_user()
    referee_id, referrer_id = referee.id, referrer.id
    await refer(db, referee, referrer)
    real_lock = wallet_service.lock_wallets
    inner: list[None] = []

    async def overtaken(session: AsyncSession, user_ids: Any) -> None:
        if not inner:
            inner.append(None)
            await _beside(session, lambda s: service.reward(s, referee_id, "selfie"))
        await real_lock(session, user_ids)

    monkeypatch.setattr(wallet_service, "lock_wallets", overtaken)

    await service.reward(db, referee_id, "purchase")

    assert inner == [None]
    assert await rewards(db, referee_id) == [_paid(referee_id, referee_id)]
    assert await rewards(db, referrer_id) == [_paid(referee_id, referrer_id)]


async def _beside(session: AsyncSession, work: Any) -> None:
    """`work` on a session of its own, in a transaction of its own, on the
    test's one connection, as a second worker would run it: committed there
    (a savepoint) before the first goes on."""
    second = AsyncSession(
        bind=await session.connection(),
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        async with second.begin():
            await work(second)
    finally:
        await second.close()
