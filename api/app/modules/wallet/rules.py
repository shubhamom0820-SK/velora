"""The ledger's rules: each reason's direction and ref, and the key (D-077).

Each reason has one direction, and `gift` is a debit (D-076). Each reason has
exactly one `ref_type`: the kind of row that justifies the entry. Every reason
needs its ref but `admin_grant`, whose ref is optional while its only callers
are the seed and `make_user`.

The key is `{user_id}:{reason}:{event}`, built here and never by a caller. The
event is the ref's id, so a webhook's retry, a concurrent delivery and a manual
repair all compute the same key. Two reasons legitimately repeat for one ref
(`admin_grant`, `thread_reopen`), so for them the caller names the event: a
client's `Idempotency-Key` only ever fills that part.

The database pins the same directions and ref types (migration 97ddae55f597,
`ck_ledger_entries_*`), and `tests/modules/wallet/test_guards.py` proves the two
agree, reason by reason. Change one, change both.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.core.enums import LedgerReason


class Direction(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"


class RefType(StrEnum):
    """What a ledger entry's `ref_id` names."""

    PAYMENT = "payment"
    REFERRAL = "referral"  # `referrals` is keyed by the referee
    AUDIT_LOG = "audit_log"
    LEDGER_ENTRY = "ledger_entry"
    ALBUM_REQUEST = "album_request"
    GIFT_SEND = "gift_send"
    THREAD = "thread"
    MESSAGE = "message"
    # The other person: `swipes` and `liked_you_reveals` key on the pair, with
    # no id of their own. So a man super-likes a woman, and reveals one, once
    # ever (one swipe per pair; the founder, 3 October 2026).
    USER = "user"


@dataclass(frozen=True)
class Rule:
    direction: Direction
    ref_type: RefType
    ref_required: bool = True
    # The event in the key is the ref's id, unless the reason repeats for one
    # ref; then the caller names it, and the per-event index leaves it out.
    caller_names_event: bool = False


CREDIT, DEBIT = Direction.CREDIT, Direction.DEBIT

RULES: dict[LedgerReason, Rule] = {
    LedgerReason.PURCHASE: Rule(CREDIT, RefType.PAYMENT),
    LedgerReason.PURCHASE_BONUS: Rule(CREDIT, RefType.PAYMENT),
    LedgerReason.REFERRAL_REWARD: Rule(CREDIT, RefType.REFERRAL),
    LedgerReason.ADMIN_GRANT: Rule(
        CREDIT, RefType.AUDIT_LOG, ref_required=False, caller_names_event=True
    ),
    LedgerReason.REFUND: Rule(CREDIT, RefType.LEDGER_ENTRY),
    # The original debit (D-077).
    LedgerReason.REFUND_BANNED_PARTNER: Rule(CREDIT, RefType.LEDGER_ENTRY),
    LedgerReason.REFUND_ALBUM_DECLINED: Rule(CREDIT, RefType.ALBUM_REQUEST),
    # A service the man buys from us; nothing ever credits its recipient (D-076).
    LedgerReason.GIFT: Rule(DEBIT, RefType.GIFT_SEND),
    LedgerReason.THREAD_OPEN: Rule(DEBIT, RefType.THREAD),
    LedgerReason.DM_OPEN: Rule(DEBIT, RefType.THREAD),
    LedgerReason.THREAD_REOPEN: Rule(DEBIT, RefType.THREAD, caller_names_event=True),
    LedgerReason.VOICE_UNLOCK: Rule(DEBIT, RefType.MESSAGE),
    LedgerReason.ALBUM_REQUEST: Rule(DEBIT, RefType.ALBUM_REQUEST),
    LedgerReason.SUPER_LIKE: Rule(DEBIT, RefType.USER),
    LedgerReason.LIKED_YOU_REVEAL: Rule(DEBIT, RefType.USER),
}

# Nothing writes it until a task gives it a meaning, and its name reads as
# money. Refused here only: its worst case is a confusingly named credit, which
# the direction CHECK already keeps a credit (D-077).
REFUSED = frozenset({LedgerReason.REFUND})

EVENT_MAX_LENGTH = 200


@dataclass(frozen=True)
class Ref:
    """The row that justifies an entry: `Ref(RefType.PAYMENT, payment.id)`."""

    type: RefType
    id: UUID


def entry_problem(
    reason: LedgerReason, direction: Direction, ref: Ref | None, event: str | None
) -> str | None:
    """Why an entry can't be written as asked, or None."""
    if reason in REFUSED:
        return "has no meaning yet, so nothing writes it (D-077)"
    rule = RULES[reason]
    if direction is not rule.direction:
        return f"is a {rule.direction}, never a {direction} (D-077)"
    if ref is None:
        if rule.ref_required:
            return f"needs its ref, of type {rule.ref_type} (D-077)"
    elif ref.type != rule.ref_type:
        return f"refs type {rule.ref_type}, never {ref.type} (D-077)"
    if not rule.caller_names_event:
        if event is not None:
            return "takes no event: the event is the ref's id (D-077)"
    elif not isinstance(event, str) or not 1 <= len(event) <= EVENT_MAX_LENGTH:
        return (
            "repeats, so needs an event its caller names, 1 to "
            f"{EVENT_MAX_LENGTH} characters (D-077)"
        )
    return None


def event_for(reason: LedgerReason, ref: Ref | None, event: str | None) -> str:
    """The event part of the key, for an entry `entry_problem` passed."""
    if RULES[reason].caller_names_event:
        assert event is not None
        return event
    assert ref is not None
    return str(ref.id)


def key_for(user_id: UUID, reason: LedgerReason, event: str) -> str:
    return f"{user_id}:{reason.value}:{event}"
