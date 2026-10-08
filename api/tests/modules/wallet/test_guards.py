"""What the database holds on its own, for a writer that skips `wallet.service`
(a migration, a repair script, an admin tool): D-076's two triggers and D-077's
ledger shape. Every rule is tested as "exactly these", never "at least these":
an inclusion check can't find an unwanted extra.

Each refusal is identified by the constraint that made it, never by SQLSTATE
alone: the gender triggers and the CHECKs share 23514.
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.enums import Gender, LedgerReason
from app.core.security import normalize_phone
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from app.modules.wallet.models import LedgerEntry, Wallet
from app.modules.wallet.rules import RULES, Direction, RefType
from app.modules.wallet.service import WalletMisuse
from tests.conftest import make_test_settings
from tests.infra import API_DIR

LEDGER_ONLY_MEN = "ledger_entries_only_men"
WALLETS_ONLY_MEN = "wallets_only_men"
# Every gender there is, and none: the allowlist must refuse a value added to
# the enum later as surely as it refuses no gender at all.
GENDERS: list[Gender | None] = [*Gender, None]

D077 = "97ddae55f597"  # the ledger's shape
D076 = "190d7bebf133"  # only men hold credits


# --- Helpers ---------------------------------------------------------------------


async def _person(db: AsyncSession, gender: Gender | None) -> User:
    """Signed up through signup's own service, so with a wallet at 0."""
    phone = normalize_phone(f"+9196{secrets.randbelow(10**8):08d}")
    account = await users_service.create_account(db, phone, make_test_settings())
    account.user.gender = gender
    await db.flush()
    return account.user


async def _without_wallet(db: AsyncSession, gender: Gender | None) -> User:
    tag = uuid.uuid4().hex[:12]
    user = User(
        phone_hash=f"hash-{tag}",
        phone_enc=b"enc",
        referral_code=f"ref{tag}",
        gender=gender,
    )
    db.add(user)
    await db.flush()
    return user


async def _attempt(db: AsyncSession, sql: str, params: dict[str, Any]) -> str | None:
    """Run `sql` in a savepoint: None if the database took it, otherwise the
    constraint that refused it (or the SQLSTATE, if none was named)."""
    try:
        async with db.begin_nested():
            await db.execute(text(sql), params)
    except IntegrityError as error:
        cause = error.orig.__cause__ if error.orig is not None else None
        name = getattr(cause, "constraint_name", None)
        return str(name or getattr(cause, "sqlstate", "unnamed"))
    return None


LEDGER_INSERT = (
    "insert into ledger_entries (user_id, delta, balance_after, reason, ref_type, "
    "ref_id, idempotency_key) "
    "values (:u, :delta, :after, :reason, :ref_type, :ref_id, :key)"
)


def _row(
    user_id: uuid.UUID,
    reason: LedgerReason,
    *,
    delta: int | None = None,
    ref_type: str | None = "pinned",
    ref_id: uuid.UUID | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    """A ledger row that D-077 takes, unless told otherwise: the reason's own
    sign, its pinned ref type and a fresh ref, and a key of its own."""
    rule = RULES[reason]
    if delta is None:
        delta = 5 if rule.direction is Direction.CREDIT else -5
    if ref_type == "pinned":
        ref_type = str(rule.ref_type)
    if ref_type is not None and ref_id is None:
        ref_id = uuid.uuid4()
    return {
        "u": user_id,
        "delta": delta,
        "after": max(delta, 0),
        "reason": reason.value,
        "ref_type": ref_type,
        "ref_id": ref_id,
        "key": key or f"guard-{uuid.uuid4()}",
    }


# --- D-076: only men hold credits --------------------------------------------------


async def _ledger_row(db: AsyncSession, user: User) -> str | None:
    return await _attempt(
        db, LEDGER_INSERT, _row(user.id, LedgerReason.ADMIN_GRANT, ref_type=None)
    )


async def _balance_set(db: AsyncSession, user: User) -> str | None:
    return await _attempt(
        db, "update wallets set balance = 5 where user_id = :u", {"u": user.id}
    )


async def _wallet_with_balance(db: AsyncSession, gender: Gender | None) -> str | None:
    user = await _without_wallet(db, gender)
    return await _attempt(
        db, "insert into wallets (user_id, balance) values (:u, 5)", {"u": user.id}
    )


async def _wallet_moved(db: AsyncSession, gender: Gender | None) -> str | None:
    """A man's balance handed to someone else by changing the wallet's owner."""
    man = await _person(db, Gender.MALE)
    assert await _balance_set(db, man) is None
    other = await _without_wallet(db, gender)
    return await _attempt(
        db,
        "update wallets set user_id = :other where user_id = :man",
        {"other": other.id, "man": man.id},
    )


WRITES: dict[str, tuple[Callable[[AsyncSession, Gender | None], Any], str]] = {
    "a ledger row": (
        lambda db, gender: _with_person(db, gender, _ledger_row),
        LEDGER_ONLY_MEN,
    ),
    "a balance set": (
        lambda db, gender: _with_person(db, gender, _balance_set),
        WALLETS_ONLY_MEN,
    ),
    "a wallet inserted with a balance": (_wallet_with_balance, WALLETS_ONLY_MEN),
    "a wallet moved to them": (_wallet_moved, WALLETS_ONLY_MEN),
}


async def _with_person(
    db: AsyncSession,
    gender: Gender | None,
    write: Callable[[AsyncSession, User], Any],
) -> str | None:
    refused: str | None = await write(db, await _person(db, gender))
    return refused


@pytest.mark.critical  # 06-TESTING.md #6c
@pytest.mark.parametrize("write", list(WRITES))
async def test_only_a_man_may_hold_credits(db: AsyncSession, write: str) -> None:
    """Every gender and none: the database takes the write for a man only, and
    each refusal is the trigger's own."""
    attempt, trigger = WRITES[write]
    refusals = {gender: await attempt(db, gender) for gender in GENDERS}

    assert {g for g, refused in refusals.items() if refused is None} == {Gender.MALE}
    assert {refused for g, refused in refusals.items() if g is not Gender.MALE} == {
        trigger
    }


@pytest.mark.critical  # 06-TESTING.md #6c: the case that made it an allowlist
async def test_no_gender_yet_is_refused_so_choosing_female_holds_nothing(
    db: AsyncSession,
) -> None:
    """T-1.9 stops a gender changing once set, not a first choice made after a
    credit. So someone with no gender yet holds nothing, and after choosing
    female still holds nothing."""
    user = await _person(db, None)

    with pytest.raises(WalletMisuse, match=r"only a man may hold credits \(D-076\)"):
        await wallet_service.credit(
            db, user.id, 5, LedgerReason.ADMIN_GRANT, event="before-gender"
        )
    assert await _ledger_row(db, user) == LEDGER_ONLY_MEN
    assert await _balance_set(db, user) == WALLETS_ONLY_MEN

    await db.execute(
        text("update users set gender = 'female' where id = :u"), {"u": user.id}
    )

    assert await _held(db, user.id) == (0, 0)
    assert await _ledger_row(db, user) == LEDGER_ONLY_MEN
    assert await _balance_set(db, user) == WALLETS_ONLY_MEN
    with pytest.raises(WalletMisuse, match=r"only a man may hold credits \(D-076\)"):
        await wallet_service.credit(
            db, user.id, 5, LedgerReason.ADMIN_GRANT, event="after-gender"
        )
    assert await _held(db, user.id) == (0, 0)


async def _held(db: AsyncSession, user_id: uuid.UUID) -> tuple[int, int]:
    """(ledger rows, balance)."""
    rows = await db.scalar(
        select(func.count())
        .select_from(LedgerEntry)
        .where(LedgerEntry.user_id == user_id)
    )
    balance = await db.scalar(select(Wallet.balance).where(Wallet.user_id == user_id))
    return int(rows or 0), int(balance or 0)


# The migration asserts what the triggers can't see: rows from before them.


async def _alembic(db: AsyncSession, run: Callable[..., object], revision: str) -> None:
    """Run an Alembic command on the test's own connection, inside its
    transaction: Alembic sees one already open and leaves it to us."""
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        run(config, revision)

    await connection.run_sync(_run)


@pytest.mark.critical  # 06-TESTING.md #6c
@pytest.mark.parametrize(
    ("held", "found"),
    [
        ("a ledger row", "but 1 ledger rows and 0 wallets with a balance"),
        ("a balance", "but 0 ledger rows and 1 wallets with a balance"),
    ],
)
async def test_the_migration_refuses_to_guard_what_someone_else_holds(
    db: AsyncSession, held: str, found: str
) -> None:
    """Back to before the triggers, a woman given something, then forward: the
    upgrade fails saying what it found. Rolled back, triggers and all."""
    woman = await _person(db, Gender.FEMALE)

    with pytest.raises(DBAPIError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, D077)
            if held == "a ledger row":
                assert await _ledger_row(db, woman) is None
            else:
                assert await _balance_set(db, woman) is None
            await _alembic(db, command.upgrade, D076)

    assert f"only a man may hold credits (D-076), {found}" in str(refused.value)
    triggers = await db.scalar(
        text(
            "select count(*) from pg_trigger "
            "where tgname in ('ledger_entries_only_men', 'wallets_only_men')"
        )
    )
    assert triggers == 2  # the downgrade was rolled back with the rest


# --- D-077: the ledger's shape -----------------------------------------------------


def test_the_rules_cover_every_reason_and_nothing_else() -> None:
    assert set(RULES) == set(LedgerReason)


async def test_the_debit_reasons_are_the_priced_actions_and_gift(
    db: AsyncSession,
) -> None:
    """action_prices name every paid action, D-004's and T-5.2's two (D-098,
    D-251); `gift` is priced by the gifts table (D-016), and is a debit too
    (D-076). `purchase_reversal` is no purchase: it takes back a payment's
    Velas when its money goes back, at no price (T-8.2, D-521)."""
    priced = set(await db.scalars(text("select action from action_prices")))
    debits = {r.value for r, rule in RULES.items() if rule.direction is Direction.DEBIT}

    assert debits == priced | {"gift", "purchase_reversal"}


async def test_each_reason_has_one_direction_in_the_database(db: AsyncSession) -> None:
    man = await _person(db, Gender.MALE)
    taken: set[tuple[LedgerReason, Direction]] = set()
    refusals: set[str] = set()

    for reason in LedgerReason:
        for delta in (5, -5):
            refused = await _attempt(
                db, LEDGER_INSERT, _row(man.id, reason, delta=delta)
            )
            if refused is None:
                taken.add((reason, Direction.CREDIT if delta > 0 else Direction.DEBIT))
            else:
                refusals.add(refused)

    assert taken == {(reason, rule.direction) for reason, rule in RULES.items()}
    assert refusals == {"ck_ledger_entries_reason_direction"}


async def test_each_reason_has_exactly_one_ref_type_in_the_database(
    db: AsyncSession,
) -> None:
    """Every reason against every ref type there is, none, and one that isn't:
    the database takes exactly the pinned one, and no ref only for
    `admin_grant`."""
    man = await _person(db, Gender.MALE)
    candidates: list[str | None] = [None, *(t.value for t in RefType), "bogus"]
    outcomes: dict[tuple[LedgerReason, str | None], str | None] = {}

    for reason in LedgerReason:
        for ref_type in candidates:
            outcomes[reason, ref_type] = await _attempt(
                db, LEDGER_INSERT, _row(man.id, reason, ref_type=ref_type)
            )

    expected: dict[tuple[LedgerReason, str | None], str | None] = {}
    for reason, rule in RULES.items():
        for ref_type in candidates:
            if ref_type == rule.ref_type:
                expected[reason, ref_type] = None
            elif ref_type is None:
                expected[reason, ref_type] = (
                    "ck_ledger_entries_ref_required" if rule.ref_required else None
                )
            else:
                expected[reason, ref_type] = "ck_ledger_entries_reason_ref_type"
    assert outcomes == expected


async def test_one_entry_per_event_except_the_reasons_that_repeat(
    db: AsyncSession,
) -> None:
    """One event under two keys, as two code paths might spell it: refused by
    the per-event index for every reason but the five that repeat for one ref
    (Extend since T-5.2, D-250; a payment's reversals and restores since T-8.2,
    one per refund or dispute, D-521)."""
    man = await _person(db, Gender.MALE)
    repeated: set[LedgerReason] = set()

    for reason in LedgerReason:
        ref = uuid.uuid4()
        assert (
            await _attempt(db, LEDGER_INSERT, _row(man.id, reason, ref_id=ref)) is None
        )
        again = await _attempt(db, LEDGER_INSERT, _row(man.id, reason, ref_id=ref))
        if again is None:
            repeated.add(reason)
        else:
            assert again == "uq_ledger_entries_one_per_event", reason

    assert repeated == {
        LedgerReason.ADMIN_GRANT,
        LedgerReason.THREAD_REOPEN,
        LedgerReason.THREAD_EXTEND,
        LedgerReason.PURCHASE_REVERSAL,
        LedgerReason.PURCHASE_RESTORED,
    }
    assert repeated == {r for r, rule in RULES.items() if rule.caller_names_event}


async def test_one_payment_credited_under_two_keys_is_refused(db: AsyncSession) -> None:
    man = await _person(db, Gender.MALE)
    payment = uuid.uuid4()
    first = _row(man.id, LedgerReason.PURCHASE, ref_id=payment, key="webhook-key")
    second = _row(man.id, LedgerReason.PURCHASE, ref_id=payment, key="repair-key")

    assert await _attempt(db, LEDGER_INSERT, first) is None
    assert (
        await _attempt(db, LEDGER_INSERT, second) == "uq_ledger_entries_one_per_event"
    )


async def test_two_people_may_each_have_an_entry_for_one_event(
    db: AsyncSession,
) -> None:
    """The index is per user: one referral rewards both people in it (T-8.6),
    each with an entry of their own."""
    referrer, referee = await _person(db, Gender.MALE), await _person(db, Gender.MALE)

    for man in (referrer, referee):
        row = _row(man.id, LedgerReason.REFERRAL_REWARD, ref_id=referee.id)
        assert await _attempt(db, LEDGER_INSERT, row) is None
