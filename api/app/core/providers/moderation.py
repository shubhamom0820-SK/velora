"""Photo moderation: nudity, minors, no face, text overlays (T-4.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, get_args

ModerationReason = Literal[
    "nudity", "minor_suspected", "no_face", "text_overlay", "other"
]
MODERATION_REASONS: frozenset[str] = frozenset(get_args(ModerationReason))


@dataclass(frozen=True)
class ModerationResult:
    approved: bool
    reason: ModerationReason | None = None


APPROVED = ModerationResult(approved=True)


class ModerationProvider(Protocol):
    async def check(self, image: bytes) -> ModerationResult:
        """Judge a re-encoded JPEG: approved, or rejected with a reason."""
        ...


class FakeModeration:
    """Approves everything, unless a test sets `next` (06-TESTING).

    `next = "reject:nudity"` makes the next check reject for that reason; the
    check after it approves again.
    """

    def __init__(self) -> None:
        self.next = "approve"
        self.checked: list[bytes] = []

    async def check(self, image: bytes) -> ModerationResult:
        self.checked.append(image)
        outcome, self.next = self.next, "approve"
        if outcome == "approve":
            return APPROVED
        kind, _, reason = outcome.partition(":")
        if kind != "reject" or reason not in MODERATION_REASONS:
            raise ValueError(
                f"FakeModeration.next must be 'approve' or 'reject:<reason>' with a reason "
                f"from {sorted(MODERATION_REASONS)}, not {outcome!r}"
            )
        return ModerationResult(approved=False, reason=reason)  # type: ignore[arg-type]


class SightengineModeration:
    """Sightengine over httpx. Not built yet."""

    async def check(self, image: bytes) -> ModerationResult:
        raise NotImplementedError("Sightengine moderation arrives with T-4.4.")
