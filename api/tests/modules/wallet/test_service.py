"""`wallet.service.debit()` and `credit()` (T-5.1, D-076, D-077), each check in
the order the service makes it. Every refusal is the service's own
`WalletMisuse`, asserted by its message: the database refuses most of these
too, so a test that accepted any error would pass with the service's check
removed.

The race between two connections is in test_race.py; the database's own
guards in test_guards.py.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import events
from app.core.enums import Gender, LedgerReason
from app.core.errors import AppError
from app.core.security import normalize_phone
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet import service
from app.modules.wallet.models import LedgerEntry, Wallet
from app.modules.wallet.rules import RULES, Direction, Ref, RefType
from app.modules.wallet.service import LedgerResult, WalletMisuse
from tests.conftest import MakeUser, make_test_settings

ADMIN_GRANT = LedgerReason.ADMIN_GRANT
THREAD_OPEN = LedgerReason.THREAD_OPEN
THREAD_REOPEN = LedgerReason.THREAD_REOPEN
PURCHASE = LedgerReason.PURCHASE


def _ref(type_: RefType) -> Ref:
    return Ref(type_, uuid.uuid4())


def _valid(reason: LedgerReason) -> dict[str, Any]:
    """The ref and event `reason` takes."""
    rule = RULES[reason]
    return {
        "ref": _ref(rule.ref_type),
        "event": f"event-{uuid.uuid4()}" if rule.caller_names_event else None,
    }


async def _entries(db: AsyncSession, user_id: uuid.UUID) -> set[tuple[Any, ...]]:
    """A set: entries from one transaction share `created_at`, so the table
    has no order to compare (D-077)."""
    rows = await db.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user_id))
    return {(e.reason, e.delta, e.balance_after, e.ref_type, e.ref_id) for e in rows}


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    balance = await db.scalar(select(Wallet.balance).where(Wallet.user_id == user_id))
    assert balance is not None
    return balance


async def _committed_events(db: AsyncSession) -> list[events.Event]:
    """What the test's transaction queued, as a request would publish it. It
    commits, so what follows opens a transaction of its own, as a service does."""
    await db.commit()
    return events.take_committed(db)


# --- What an applied entry is ------------------------------------------------------


async def test_a_credit_applies_once_with_its_key(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    payment = _ref(RefType.PAYMENT)

    result = await service.credit(db, man.id, 25, PURCHASE, ref=payment)

    assert result.applied is True
    entry = result.entry
    assert (entry.user_id, entry.reason, entry.delta, entry.balance_after) == (
        man.id,
        PURCHASE,
        25,
        25,
    )
    assert (entry.ref_type, entry.ref_id) == ("payment", payment.id)
    assert entry.idempotency_key == f"{man.id}:purchase:{payment.id}"
    assert await _balance(db, man.id) == 25
    assert await _committed_events(db) == [
        events.Event(man.id, "wallet.updated", {"balance": 25})
    ]


async def test_a_debit_takes_from_the_balance(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(credits=10)
    thread = _ref(RefType.THREAD)

    result = await service.debit(db, man.id, 4, THREAD_OPEN, ref=thread)

    assert result.applied is True
    assert (result.entry.delta, result.entry.balance_after) == (-4, 6)
    assert result.entry.idempotency_key == f"{man.id}:thread_open:{thread.id}"
    assert await _balance(db, man.id) == 6
    entries = await _entries(db, man.id)
    # make_user's grant names an audit row of its own (D-923).
    assert {entry[:4] for entry in entries} == {
        (ADMIN_GRANT, 10, 10, "audit_log"),
        (THREAD_OPEN, -4, 6, "thread"),
    }
    assert (THREAD_OPEN, -4, 6, "thread", thread.id) in entries


async def test_a_debit_may_take_the_whole_balance(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(credits=5)

    await service.debit(db, man.id, 5, THREAD_OPEN, ref=_ref(RefType.THREAD))

    assert await _balance(db, man.id) == 0


# --- 1. Inside a transaction only -----------------------------------------------------


async def test_outside_a_transaction_is_refused(
    test_engine: AsyncEngine, make_user: MakeUser
) -> None:
    """A session with nothing begun: refused before it touches the database."""
    man, _ = await make_user()
    async with AsyncSession(test_engine) as session:
        for move in (service.credit, service.debit):
            with pytest.raises(
                WalletMisuse, match=r"runs only inside its caller's transaction"
            ):
                await move(session, man.id, 5, THREAD_OPEN, ref=_ref(RefType.THREAD))
        assert not session.in_transaction()


# --- 2. The amount ----------------------------------------------------------------


@pytest.mark.parametrize("amount", [0, -5, True, False, 5.0, "5", None], ids=repr)
async def test_the_amount_is_a_whole_number_above_zero(
    db: AsyncSession, make_user: MakeUser, amount: Any
) -> None:
    man, _ = await make_user(credits=10)

    for move, reason in ((service.credit, ADMIN_GRANT), (service.debit, THREAD_OPEN)):
        with pytest.raises(WalletMisuse, match="the amount must be a whole number"):
            await move(db, man.id, amount, reason, **_valid(reason))

    assert await _balance(db, man.id) == 10


# --- 3. The reason, its direction, its ref and its event ----------------------------


async def test_each_reason_is_taken_in_its_own_direction_only(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Every reason through both functions: exactly the rules' directions are
    taken, but for bare `refund`, refused in the service (D-077)."""
    man, _ = await make_user(credits=1000)
    taken: set[tuple[LedgerReason, Direction]] = set()

    for reason in LedgerReason:
        for direction, move in (
            (Direction.CREDIT, service.credit),
            (Direction.DEBIT, service.debit),
        ):
            try:
                await move(db, man.id, 5, reason, **_valid(reason))
            except WalletMisuse as refused:
                expected = (
                    "refund has no meaning yet"
                    if reason is LedgerReason.REFUND
                    else f"{reason} is a {RULES[reason].direction}, never a {direction}"
                )
                assert str(refused).startswith(expected), (reason, direction)
            else:
                taken.add((reason, direction))

    assert taken == {
        (reason, rule.direction)
        for reason, rule in RULES.items()
        if reason is not LedgerReason.REFUND
    }


async def test_bare_refund_is_refused_and_writes_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(credits=5)

    with pytest.raises(WalletMisuse, match=r"^refund has no meaning yet"):
        await service.credit(
            db, man.id, 5, LedgerReason.REFUND, ref=_ref(RefType.LEDGER_ENTRY)
        )

    assert await _balance(db, man.id) == 5
    assert len(await _entries(db, man.id)) == 1


@pytest.mark.parametrize(
    ("reason", "kwargs", "refusal"),
    [
        (PURCHASE, {}, "purchase needs its ref, of type payment"),
        (
            PURCHASE,
            {"ref": _ref(RefType.THREAD)},
            "purchase refs type payment, never thread",
        ),
        (
            PURCHASE,
            {"ref": _ref(RefType.PAYMENT), "event": "client-key"},
            "purchase takes no event: the event is the ref's id",
        ),
        (
            ADMIN_GRANT,
            {"event": "grant"},
            "admin_grant needs its ref, of type audit_log",
        ),
        (
            LedgerReason.ADMIN_CORRECTION,
            {"event": "correction"},
            "admin_correction needs its ref, of type audit_log",
        ),
        (
            ADMIN_GRANT,
            {"ref": _ref(RefType.AUDIT_LOG)},
            "admin_grant repeats, so needs an event its caller names",
        ),
        (
            ADMIN_GRANT,
            {"event": "", "ref": _ref(RefType.AUDIT_LOG)},
            "admin_grant repeats, so needs an event its caller names",
        ),
        (
            ADMIN_GRANT,
            {"event": "x" * 201, "ref": _ref(RefType.AUDIT_LOG)},
            "admin_grant repeats, so needs an event its caller names, 1 to 200",
        ),
        (
            ADMIN_GRANT,
            {"event": "grant", "ref": _ref(RefType.PAYMENT)},
            "admin_grant refs type audit_log, never payment",
        ),
        (
            THREAD_REOPEN,
            {"event": "client-key"},
            "thread_reopen needs its ref, of type thread",
        ),
        (
            THREAD_REOPEN,
            {"ref": _ref(RefType.THREAD)},
            "thread_reopen repeats, so needs an event its caller names",
        ),
    ],
    ids=[
        "no ref",
        "another ref type",
        "an event where the ref is the event",
        "admin_grant with no ref",
        "admin_correction with no ref",
        "admin_grant with no event",
        "an empty event",
        "an event too long",
        "admin_grant naming a payment",
        "thread_reopen with no ref",
        "thread_reopen with no event",
    ],
)
async def test_the_ref_and_event_must_be_the_reasons_own(
    db: AsyncSession,
    make_user: MakeUser,
    reason: LedgerReason,
    kwargs: dict[str, Any],
    refusal: str,
) -> None:
    man, _ = await make_user(credits=10)
    move = (
        service.credit if RULES[reason].direction is Direction.CREDIT else service.debit
    )

    with pytest.raises(WalletMisuse) as refused:
        await move(db, man.id, 5, reason, **kwargs)

    assert str(refused.value).startswith(refusal)
    assert await _balance(db, man.id) == 10


@pytest.mark.parametrize("length", [1, 200])
async def test_an_event_of_1_to_200_characters_is_taken(
    db: AsyncSession, make_user: MakeUser, length: int
) -> None:
    man, _ = await make_user()

    result = await service.credit(
        db, man.id, 5, ADMIN_GRANT, ref=_ref(RefType.AUDIT_LOG), event="e" * length
    )

    assert result.entry.idempotency_key == f"{man.id}:admin_grant:{'e' * length}"


async def test_an_admin_grant_names_its_audit_entry(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    audit = _ref(RefType.AUDIT_LOG)

    result = await service.credit(db, man.id, 5, ADMIN_GRANT, ref=audit, event="g1")

    assert (result.entry.ref_type, result.entry.ref_id) == ("audit_log", audit.id)


# --- 4. A man's wallet, locked --------------------------------------------------------


@pytest.mark.parametrize("gender", [Gender.FEMALE, None], ids=["a woman", "no gender"])
async def test_anyone_but_a_man_is_refused_by_the_service(
    db: AsyncSession, gender: Gender | None
) -> None:
    """The service's own refusal, before the database's (D-076): a clear
    error, not an IntegrityError from the trigger."""
    account = await users_service.create_account(
        db,
        normalize_phone(f"+9196{uuid.uuid4().int % 10**8:08d}"),
        make_test_settings(),
    )
    account.user.gender = gender
    await db.flush()

    for move, reason in ((service.credit, ADMIN_GRANT), (service.debit, THREAD_OPEN)):
        with pytest.raises(
            WalletMisuse, match=r"^only a man may hold credits \(D-076\)$"
        ):
            await move(db, account.user.id, 5, reason, **_valid(reason))

    assert await _entries(db, account.user.id) == set()
    assert await _balance(db, account.user.id) == 0


async def test_a_user_with_no_wallet_is_refused(db: AsyncSession) -> None:
    tag = uuid.uuid4().hex[:12]
    user = User(
        phone_hash=f"hash-{tag}",
        phone_enc=b"enc",
        referral_code=f"ref{tag}",
        gender=Gender.MALE,
    )
    db.add(user)
    await db.flush()

    with pytest.raises(WalletMisuse, match=r"^this user has no wallet"):
        await service.credit(
            db, user.id, 5, ADMIN_GRANT, ref=_ref(RefType.AUDIT_LOG), event="g"
        )


# --- 5. Repeats ------------------------------------------------------------------


async def test_a_repeat_returns_the_entry_and_changes_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(credits=10)
    thread = _ref(RefType.THREAD)
    first = await service.debit(db, man.id, 5, THREAD_OPEN, ref=thread)
    await _committed_events(db)

    async with db.begin():
        again = await service.debit(db, man.id, 5, THREAD_OPEN, ref=thread)

    assert again == LedgerResult(first.entry, applied=False)
    assert await _balance(db, man.id) == 5
    assert len(await _entries(db, man.id)) == 2
    assert await _committed_events(db) == []


async def test_a_repeat_is_returned_even_when_the_balance_has_gone(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """The repeat check comes before the balance check: a retried debit that
    took the last of the balance is answered, not refused."""
    man, _ = await make_user(credits=5)
    thread = _ref(RefType.THREAD)
    await service.debit(db, man.id, 5, THREAD_OPEN, ref=thread)

    again = await service.debit(db, man.id, 5, THREAD_OPEN, ref=thread)

    assert again.applied is False


@pytest.mark.parametrize(
    "change",
    ["another amount", "another ref"],
)
async def test_one_key_with_other_details_raises_and_writes_nothing(
    db: AsyncSession, make_user: MakeUser, change: str
) -> None:
    """Returning the earlier entry would hide the bug that reused the key."""
    man, _ = await make_user()
    audit = _ref(RefType.AUDIT_LOG)
    await service.credit(db, man.id, 5, ADMIN_GRANT, ref=audit, event="grant-1")
    changes: dict[str, dict[str, Any]] = {
        "another amount": {"amount": 6, "ref": audit},
        "another ref": {"amount": 5, "ref": _ref(RefType.AUDIT_LOG)},
    }
    second = changes[change]

    with pytest.raises(WalletMisuse) as refused:
        await service.credit(
            db,
            man.id,
            second["amount"],
            ADMIN_GRANT,
            ref=second["ref"],
            event="grant-1",
        )

    assert str(refused.value) == (
        "admin_grant: this event is in the ledger already, with other details; "
        "a key is never reused (D-077)"
    )
    assert await _balance(db, man.id) == 5
    assert len(await _entries(db, man.id)) == 1


@pytest.mark.parametrize(
    ("reason", "ref_type"),
    [(ADMIN_GRANT, RefType.AUDIT_LOG), (THREAD_REOPEN, RefType.THREAD)],
)
async def test_the_two_reasons_that_repeat_apply_once_per_named_event(
    db: AsyncSession, make_user: MakeUser, reason: LedgerReason, ref_type: RefType
) -> None:
    """One thread reopened twice, one audit entry granting twice: each event
    its caller names is its own entry."""
    man, _ = await make_user(credits=20)
    ref = _ref(ref_type)
    move = service.credit if reason is ADMIN_GRANT else service.debit

    first = await move(db, man.id, 3, reason, ref=ref, event="first")
    second = await move(db, man.id, 3, reason, ref=ref, event="second")
    first_again = await move(db, man.id, 3, reason, ref=ref, event="first")

    assert (first.applied, second.applied, first_again.applied) == (True, True, False)
    assert first_again.entry.id == first.entry.id
    assert len(await _entries(db, man.id)) == 3


@pytest.mark.parametrize(
    ("reason", "shared"),
    [
        (ADMIN_GRANT, {"event": "shared-event", "ref": _ref(RefType.AUDIT_LOG)}),
        (THREAD_REOPEN, {"event": "client-key-1", "ref": _ref(RefType.THREAD)}),
        (LedgerReason.REFERRAL_REWARD, {"ref": _ref(RefType.REFERRAL)}),
    ],
    ids=["admin_grant", "thread_reopen", "referral_reward"],
)
async def test_two_people_with_one_event_both_apply(
    db: AsyncSession,
    make_user: MakeUser,
    reason: LedgerReason,
    shared: dict[str, Any],
) -> None:
    """P-19: the key is the user's own, so a client key or event two people
    share is never one person's entry refusing the other's."""
    first, _ = await make_user(credits=10)
    second, _ = await make_user(credits=10)
    move = (
        service.credit if RULES[reason].direction is Direction.CREDIT else service.debit
    )

    # Two men in one transaction: locked in `user_id` order first (P-63).
    await service.lock_wallets(db, [first.id, second.id])
    results = [await move(db, man.id, 3, reason, **shared) for man in (first, second)]

    assert [r.applied for r in results] == [True, True]
    assert {r.entry.user_id for r in results} == {first.id, second.id}
    assert results[0].entry.idempotency_key != results[1].entry.idempotency_key


# --- 6. INSUFFICIENT_CREDITS -------------------------------------------------------


async def test_a_debit_beyond_the_balance_is_refused_and_writes_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Refused inside a transaction that then commits: so anything the service
    wrote or queued before refusing would be there to see."""
    man, _ = await make_user(credits=5)
    await _committed_events(db)

    async with db.begin():
        with pytest.raises(AppError) as refused:
            await service.debit(db, man.id, 6, THREAD_OPEN, ref=_ref(RefType.THREAD))

    error = refused.value
    assert (error.code, error.status) == ("INSUFFICIENT_CREDITS", 402)
    assert error.details == {"required": 6, "balance": 5}
    # No unit: the copy names Velas, and Vela follows the brand (rule 17).
    assert error.message == "Your balance is too low for this."
    assert await _balance(db, man.id) == 5
    assert len(await _entries(db, man.id)) == 1
    assert events.take_committed(db) == []


# --- reverse(): a payment's Velas taken back (T-8.2, D-520) ----------------------

REVERSAL = LedgerReason.PURCHASE_REVERSAL


async def test_a_reversal_takes_the_amount_when_the_balance_holds_it(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(credits=40)
    payment = _ref(RefType.PAYMENT)

    reversal = await service.reverse(
        db, man.id, 36, REVERSAL, ref=payment, event="rfnd_1"
    )

    assert (reversal.taken, reversal.shortfall, reversal.applied) == (36, 0, True)
    assert reversal.entry is not None
    assert reversal.entry.idempotency_key == f"{man.id}:purchase_reversal:rfnd_1"
    assert await _balance(db, man.id) == 4
    assert (REVERSAL, -36, 4, "payment", payment.id) in await _entries(db, man.id)


@pytest.mark.critical
async def test_a_reversal_takes_at_most_the_balance_and_never_refuses(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """He spent some: what is left is taken, down to 0, and the rest is the
    shortfall. Never INSUFFICIENT_CREDITS, never below 0 (D-520)."""
    man, _ = await make_user(credits=10)

    reversal = await service.reverse(
        db, man.id, 36, REVERSAL, ref=_ref(RefType.PAYMENT), event="rfnd_1"
    )

    assert (reversal.taken, reversal.shortfall, reversal.applied) == (10, 26, True)
    assert await _balance(db, man.id) == 0


async def test_at_a_balance_of_zero_a_reversal_writes_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()

    reversal = await service.reverse(
        db, man.id, 36, REVERSAL, ref=_ref(RefType.PAYMENT), event="rfnd_1"
    )

    assert reversal == service.Reversal(
        entry=None, taken=0, shortfall=36, applied=False
    )
    assert await _entries(db, man.id) == set()
    assert await _committed_events(db) == []


async def test_the_same_reversal_twice_takes_once(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Partly taken, then asked again for the same event: the first entry,
    whatever the balance holds now."""
    man, _ = await make_user(credits=10)
    payment = _ref(RefType.PAYMENT)
    first = await service.reverse(db, man.id, 36, REVERSAL, ref=payment, event="rfnd_1")
    await service.credit(
        db, man.id, 50, ADMIN_GRANT, ref=_ref(RefType.AUDIT_LOG), event="later"
    )

    again = await service.reverse(db, man.id, 36, REVERSAL, ref=payment, event="rfnd_1")

    assert again == service.Reversal(first.entry, 10, 26, applied=False)
    assert await _balance(db, man.id) == 50


async def test_reverse_refuses_outside_a_transaction(
    test_engine: AsyncEngine, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    async with AsyncSession(test_engine) as session:
        with pytest.raises(
            WalletMisuse, match=r"runs only inside its caller's transaction"
        ):
            await service.reverse(
                session, man.id, 5, REVERSAL, ref=_ref(RefType.PAYMENT), event="r"
            )


async def test_reverse_refuses_a_woman(db: AsyncSession, make_user: MakeUser) -> None:
    woman, _ = await make_user(Gender.FEMALE)

    with pytest.raises(WalletMisuse, match=r"^only a man may hold credits \(D-076\)$"):
        await service.reverse(
            db, woman.id, 5, REVERSAL, ref=_ref(RefType.PAYMENT), event="r"
        )


@pytest.mark.parametrize(
    "reason", [r for r in LedgerReason if r is not REVERSAL], ids=str
)
async def test_reverse_takes_only_a_purchase_reversal(
    db: AsyncSession, make_user: MakeUser, reason: LedgerReason
) -> None:
    """Anything else that spends is priced, and refused on a low balance."""
    man, _ = await make_user(credits=10)

    with pytest.raises(WalletMisuse, match=r"is never taken by reverse\(\)"):
        await service.reverse(db, man.id, 5, reason, **_valid(reason))

    assert await _balance(db, man.id) == 10
