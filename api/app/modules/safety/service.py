"""Safety records (T-4.4 starts it): signals about a person, never verdicts.

`fraud_events` holds signals for T-9.2's scoring and T-9.5's queue. A signal is
what something observed, and is recorded as exactly that.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.safety import repository
from app.modules.safety.models import FraudEvent

# D-093: a model's score that one photo may show a minor. The name and the
# record say so; nothing downstream may read it as a fact about the person.
POSSIBLE_MINOR_SCORE: Final = "possible_minor_photo_score"
POSSIBLE_MINOR_NOTE: Final = (
    "A model's score for one photo, not a finding about the person (D-093)."
)
# Counts for nothing until T-9.2 says how much a signal like this may count;
# repeated flags go to a human, never to an automatic action (D-093, P-72).
POSSIBLE_MINOR_WEIGHT: Final = 0


def record_possible_minor(
    session: AsyncSession, user_id: UUID, *, score: float, model: str
) -> None:
    """D-093's minimal record, in the caller's transaction: who, when (the
    row's `created_at`), the score and the model. Never the image, nor which
    photo: the image is deleted, and the record outlives it."""
    repository.add_fraud_event(
        session,
        FraudEvent(
            user_id=user_id,
            signal=POSSIBLE_MINOR_SCORE,
            weight=POSSIBLE_MINOR_WEIGHT,
            meta={"what": POSSIBLE_MINOR_NOTE, "model": model, "score": score},
        ),
    )


# D-520: a chargeback whose Velas were spent before they could be taken back.
# What happened to the money, not a judgement of him: a dispute may be his
# bank's mistake, and freezing is a moderation decision, never automatic.
CHARGEBACK_SHORTFALL: Final = "chargeback_shortfall"
CHARGEBACK_SHORTFALL_NOTE: Final = (
    "A dispute took back money whose Velas were spent: the Velas it couldn't "
    "take back (D-520)."
)
# Counts for nothing until T-9.2 says what it may count for (D-520).
CHARGEBACK_SHORTFALL_WEIGHT: Final = 0


def record_chargeback_shortfall(
    session: AsyncSession, user_id: UUID, *, payment_id: UUID, shortfall: int
) -> None:
    """In the caller's transaction: our payment's id and the Velas short."""
    repository.add_fraud_event(
        session,
        FraudEvent(
            user_id=user_id,
            signal=CHARGEBACK_SHORTFALL,
            weight=CHARGEBACK_SHORTFALL_WEIGHT,
            meta={
                "what": CHARGEBACK_SHORTFALL_NOTE,
                "payment_id": str(payment_id),
                "shortfall": shortfall,
            },
        ),
    )
