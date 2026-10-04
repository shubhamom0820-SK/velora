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
