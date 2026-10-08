"""What a referral decides (T-8.6, D-690 to D-693). No I/O: the service reads,
these decide.

- **Whose code works** (D-693): an owner who has finished onboarding and is
  `active` or `paused`. Anyone else's code is the same `NOT_FOUND` as a code
  nobody has, so a code says nothing about its owner's account.
- **Who is credited** (D-076, D-690): men only, an allowlist. A woman is never
  given Velas, as referrer or referee, and nothing else stands in for them; her
  referrals are counted in `GET /referrals/me` and that is all.
- **Who still counts at the reward** (D-693): `active` or `paused` again, read
  when the reward is paid. A man banned, frozen or deleted since gets nothing;
  the other side still gets theirs.
- **The cap** (D-692): a referrer is paid for `referral_rewards_max` referrals,
  ever, counted under his wallet's lock; past it, the referee is still paid.
- **Paused** (D-840): while `referral_reward_velas` isn't above 0, no code is
  applied, so no number spends its one referee slot (D-691) on nothing.
"""

from __future__ import annotations

from typing import Final

from app.core.enums import Gender, OnboardingStep, UserStatus

REWARD_KEY: Final = "referral_reward_velas"
REWARDS_MAX_KEY: Final = "referral_rewards_max"

CREDITED_GENDERS: Final = frozenset({Gender.MALE})
STANDING: Final = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})


def code_works(step: OnboardingStep, status: UserStatus) -> bool:
    """Whether a code's owner may refer anyone (D-693)."""
    return step is OnboardingStep.DONE and status in STANDING


def running(reward_velas: int) -> bool:
    """Whether a code may be applied now (D-840): only while it pays."""
    return reward_velas > 0


def is_credited(gender: Gender | None, status: UserStatus) -> bool:
    """Whether this side of a referral is paid in Velas when it is rewarded."""
    return gender in CREDITED_GENDERS and status in STANDING
