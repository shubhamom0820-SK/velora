"""Referrals (T-8.6, D-690 to D-693): a code applied during onboarding, and a
reward when the referee's selfie matches or their first purchase is captured,
whichever comes first.

**Apply** (`POST /referrals/apply`), with the user's row locked, so two at once
take turns: first, only while referrals run, the reward read fresh and above 0,
a missing row counting as paused (D-840), so no number's slot goes on a referral
that pays nothing; before `done`; once per phone number, ever (D-691), read from the
referrals every account on the number ever had, which the erasure keeps; a code
whose owner has finished onboarding and stands (D-693), never the user's own. A
referral can exist before `dob`: an under-18 refusal deletes it, as referee or
referrer (D-078, `UNDERAGE_DELETES`). No reward can, since both triggers come
after `dob`.

**The reward** (`reward()`), in the trigger's own transaction: the webhook's
capture (T-8.2) and the selfie's decision (T-4.5). In this order: the referral
locked, unrewarded, or nothing happens; `referral_reward_velas`; each side
paid only if a man who still stands (D-076, D-690, D-693); **both wallets
locked in `user_id` order**, whoever is paid, before either is credited and
before the webhook's purchase locks the referee's again (D-077, P-63); the
referrer's count read under his lock, and nothing for him past
`referral_rewards_max` (D-692); each man credited `referral_reward`, keyed on
the referee (D-077), so a second trigger can't pay twice even past the
referral's lock; then `rewarded_at`. Nothing about it ever fails its trigger: a
missing setting skips it with a warning and leaves it to the next trigger, and
0 rewards it with nothing.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import LedgerReason, OnboardingStep
from app.core.errors import AppError
from app.modules.admin import service as admin_service
from app.modules.referrals import repository, rules
from app.modules.referrals.schemas import ReferralsMe
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType

log = structlog.get_logger(__name__)

Trigger = Literal["selfie", "purchase"]


async def apply(session: AsyncSession, user: User, code: str) -> None:
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        if not await _running(session):
            raise AppError(
                "NOT_ALLOWED",
                "Referral codes are paused for now.",
                status=422,
                details={"why": "referrals_paused"},
            )
        if user.onboarding_step is OnboardingStep.DONE:
            raise AppError(
                "NOT_ALLOWED",
                "A code can only be added while you sign up.",
                status=422,
                details={"why": "onboarding_done"},
            )
        if await repository.number_was_referred(session, user.phone_hash):
            raise AppError(
                "ALREADY_EXISTS", "This number has already used a code.", status=409
            )
        owner = await repository.owner_of(session, code)
        if owner is not None and owner.id == user.id:
            raise AppError(
                "NOT_ALLOWED",
                "That's your own code.",
                status=422,
                details={"why": "own_code"},
            )
        if owner is None or not rules.code_works(owner.onboarding_step, owner.status):
            raise AppError("NOT_FOUND", "No one has that code.", status=404)
        await repository.add(session, referee_id=user.id, referrer_id=owner.id)
    log.info("referrals.applied", referee_id=str(user.id), referrer_id=str(owner.id))


async def _running(session: AsyncSession) -> bool:
    """Whether a code may be applied now (D-840), read fresh, never cached, so
    a pause applies at once. A missing setting is paused, with a warning: a
    slot spent while nothing can pay is never given back."""
    try:
        amount = await admin_service.config_int(session, rules.REWARD_KEY)
    except admin_service.MissingConfig:
        log.warning("referrals.apply_config_missing", key=rules.REWARD_KEY)
        return False
    return rules.running(amount)


async def me(session: AsyncSession, user: User) -> ReferralsMe:
    async with session.begin():
        invited, rewarded = await repository.counts(session, user.id)
    return ReferralsMe(code=user.referral_code, invited=invited, rewarded=rewarded)


async def reward(session: AsyncSession, referee_id: UUID, trigger: Trigger) -> None:
    """Reward the referee's referral, if it has one not yet rewarded, in the
    caller's transaction. The caller holds no wallet yet: both are locked here,
    in order, before either is credited, and before the webhook's purchase
    locks the referee's again."""
    referral = await repository.pending_for_update(session, referee_id)
    if referral is None:
        return
    fields = {
        "referee_id": str(referee_id),
        "referrer_id": str(referral.referrer_id),
        "trigger": trigger,
    }
    try:
        # Fresh, never cached: a reward is rare, and a change applies at once.
        amount = await admin_service.config_int(session, rules.REWARD_KEY)
    except admin_service.MissingConfig:
        log.warning("referrals.reward_config_missing", key=rules.REWARD_KEY, **fields)
        return
    if amount < 0:
        log.warning("referrals.reward_config_negative", key=rules.REWARD_KEY, **fields)
        amount = 0

    referrer_id = referral.referrer_id
    # Both wallets, in `user_id` order, whoever is paid: the webhook's capture
    # locks the referee's next, for his purchase, and must find it held
    # already, never below a referrer locked alone (P-63).
    await wallet_service.lock_wallets(session, [referee_id, referrer_id])
    paid: list[UUID] = []
    if amount > 0:
        standing = await repository.standing_of(session, [referee_id, referrer_id])
        paid = [
            user_id
            for user_id in (referee_id, referrer_id)
            if user_id in standing
            and rules.is_credited(standing[user_id].gender, standing[user_id].status)
        ]
    if referrer_id in paid and not await _under_the_cap(session, referrer_id, fields):
        paid.remove(referrer_id)
    ref = Ref(RefType.REFERRAL, referee_id)
    for user_id in paid:
        await wallet_service.credit(
            session, user_id, amount, LedgerReason.REFERRAL_REWARD, ref=ref
        )
    referral.rewarded_at = clock.now()
    log.info(
        "referrals.rewarded",
        amount=amount,
        referee_paid=referee_id in paid,
        referrer_paid=referrer_id in paid,
        **fields,
    )


async def _under_the_cap(
    session: AsyncSession, referrer_id: UUID, fields: dict[str, str]
) -> bool:
    """Whether the referrer may be paid for one more (D-692): read under his
    wallet's lock. A missing cap pays him nothing, with a warning: a limit
    that fails open is no limit."""
    try:
        cap = await admin_service.config_int(session, rules.REWARDS_MAX_KEY)
    except admin_service.MissingConfig:
        log.warning("referrals.cap_config_missing", key=rules.REWARDS_MAX_KEY, **fields)
        return False
    if await wallet_service.referral_rewards_paid(session, referrer_id) < cap:
        return True
    log.info("referrals.referrer_at_cap", cap=cap, **fields)
    return False
