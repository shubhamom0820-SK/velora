"""Breaking runs: each guard weakened on purpose, one at a time, to prove a
test goes red when it is gone (the proof standard; T-5.1, T-5.4).

    uv run python -m tests.break_guards --list
    uv run python -m tests.break_guards                       # every case, once
    uv run python -m tests.break_guards t54- --repeat 3       # cases by id prefix

Each case edits files as a careless change would, runs its task's tests,
and puts the files back byte for byte, proved by SHA-256 per file before the
next case. Runs write no bytecode (a `.pyc` can outlive a same-length edit)
and never set `TEST_DATABASE_URL`, so every run takes a fresh slot database
(P-55) and a weakened migration can't outlive its case.

A case is red only when the run failed and every test it names failed with
it; a run in which Postgres refused the fifty connections is inconclusive,
never red. A red that depends on the scheduler (P-58) is reported as red in
N of N, so run those cases with `--repeat`.

If the process is killed mid-case, the weakened file stays: `git status`
shows it, and `git checkout -- <file>` restores it. Pytest doesn't collect
this module; `tests/test_break_guards.py` keeps its cases' anchors honest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


from typing import Any, TypedDict

API = Path(__file__).resolve().parent.parent


class Case(TypedDict):
    id: str
    what: str
    edits: list[tuple[str, str, str]]  # (file under api/, old text, new text)
    expect: list[str]  # tests that must fail, matched within node ids


T51_SELECTION = [
    "tests/modules/wallet",
    "--ignore=tests/modules/wallet/test_concurrency.py",
    "tests/core/test_events.py",
    "tests/test_schema.py",
    "tests/seed/test_seed.py",
    "tests/test_harness.py",
    "tests/test_app_role.py",
    "tests/test_migrations.py",
]
T54_SELECTION = [
    "tests/modules/wallet/test_concurrency.py",
    "tests/modules/wallet/test_race.py",
]
CONCURRENCY = "tests/modules/wallet/test_concurrency.py"

# --- T-5.1: D-077's six layers, D-076's triggers, the service, events, the seed --

MONEY = "alembic/versions/20260926_60978dcfef93_money.py"
SHAPE = "alembic/versions/20261003_97ddae55f597_ledger_shape.py"
MEN = "alembic/versions/20261003_190d7bebf133_only_men_hold_credits.py"
SERVICE = "app/modules/wallet/service.py"
RULES = "app/modules/wallet/rules.py"
REPO = "app/modules/wallet/repository.py"
WALLET_MODELS = "app/modules/wallet/models.py"
PAYMENT_MODELS = "app/modules/payments/models.py"
EVENTS = "app/core/events.py"
DB = "app/core/db.py"
SEED = "seed/run.py"
CONFTEST = "tests/conftest.py"
RACES = "tests/modules/wallet/races.py"

GENDER_CHECK = (
    "if (select gender from users where id = new.user_id) is distinct from 'male' then"
)


def blacklist_on(table: str) -> str:
    return (
        f"if (tg_table_name = '{table}' and (select gender from users where id = new.user_id) = 'female')\n"
        f"        or (tg_table_name <> '{table}' and (select gender from users where id = new.user_id) is distinct from 'male') then"
    )


T51: list[Case] = [
    # --- D-077's six layers ---------------------------------------------------
    Case(
        id="t51-L1-unique-key",
        what="D-077 layer 1: ledger_entries.idempotency_key no longer UNIQUE (migration and model)",
        edits=[
            (
                MONEY,
                """        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_ledger_entries_idempotency_key")
        ),
""",
                "",
            ),
            (
                WALLET_MODELS,
                "idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)",
                "idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)",
            ),
        ],
        expect=["test_schema.py::test_idempotency_key_applies_once"],
    ),
    Case(
        id="t51-L2-key-per-user",
        what="D-077 layer 2: the key loses its user, `{reason}:{event}` (P-19's collision)",
        edits=[
            (
                RULES,
                'return f"{user_id}:{reason.value}:{event}"',
                'return f"{reason.value}:{event}"',
            )
        ],
        expect=["test_two_people_with_one_event_both_apply"],
    ),
    Case(
        id="t51-L3a-per-event-index",
        what="D-077 layer 3: the per-event index no longer unique (migration and model)",
        edits=[
            (
                SHAPE,
                """        ["user_id", "reason", "ref_type", "ref_id"],
        unique=True,""",
                """        ["user_id", "reason", "ref_type", "ref_id"],
        unique=False,""",
            ),
            (
                WALLET_MODELS,
                """            "ref_id",
            unique=True,""",
                """            "ref_id",
            unique=False,""",
            ),
        ],
        expect=[
            "test_one_entry_per_event_except_the_two_reasons_that_repeat",
            "test_one_payment_credited_under_two_keys_is_refused",
        ],
    ),
    Case(
        id="t51-L3b-ref-required",
        what="D-077 layer 3: ck_ledger_entries_ref_required made vacuous",
        edits=[
            (
                SHAPE,
                '''REF_REQUIRED = f"reason = '{REF_OPTIONAL}' OR ref_id IS NOT NULL"''',
                '''REF_REQUIRED = "true"''',
            )
        ],
        expect=["test_each_reason_has_exactly_one_ref_type_in_the_database"],
    ),
    Case(
        id="t51-L3c-ref-type-pin",
        what="D-077 layer 3: ck_ledger_entries_reason_ref_type made vacuous (ref type unpinned)",
        edits=[
            (
                SHAPE,
                """REF_TYPE = "ref_type IS NULL OR (reason, ref_type) IN ({})".format(""",
                """REF_TYPE = "true OR (reason, ref_type) IN ({})".format(""",
            )
        ],
        expect=["test_each_reason_has_exactly_one_ref_type_in_the_database"],
    ),
    Case(
        id="t51-L4a-for-update",
        what="D-077 layer 4: the wallet read without FOR UPDATE",
        edits=[(REPO, "            .with_for_update(of=Wallet)\n", "")],
        expect=[
            "test_two_debits_of_the_whole_balance_take_turns",
            "test_two_credits_of_one_payment_at_once_apply_once",
        ],
    ),
    Case(
        id="t51-L4b-repeat-before-lock",
        what="D-077 layer 4: the repeat check made before the lock is granted",
        edits=[
            (
                SERVICE,
                """    locked = await repository.lock_wallet(session, user_id)
    if locked is None:
        raise WalletMisuse("this user has no wallet; signup creates one (T-3.3)")
    balance, gender = locked
    if gender is not Gender.MALE:
        raise WalletMisuse("only a man may hold credits (D-076)")

    existing = await repository.entry_by_key(session, key)
""",
                """    existing = await repository.entry_by_key(session, key)
    locked = await repository.lock_wallet(session, user_id)
    if locked is None:
        raise WalletMisuse("this user has no wallet; signup creates one (T-3.3)")
    balance, gender = locked
    if gender is not Gender.MALE:
        raise WalletMisuse("only a man may hold credits (D-076)")

""",
            )
        ],
        expect=["test_two_credits_of_one_payment_at_once_apply_once"],
    ),
    Case(
        id="t51-L4c-other-details-returned",
        what="D-077 layer 4: a key reused with other details returns the earlier entry silently",
        edits=[
            (
                SERVICE,
                """        if _details(existing) != details:
            raise WalletMisuse(""",
                """        if _details(existing) != details and False:
            raise WalletMisuse(""",
            )
        ],
        expect=[
            "test_one_key_with_other_details_raises_and_writes_nothing",
            "test_a_grant_is_never_changed_by_a_later_seed",
        ],
    ),
    Case(
        id="t51-L5a-payment-anchor-unique",
        what="D-077 layer 5: payments.provider_payment_id no longer UNIQUE (migration and model)",
        edits=[
            (
                MONEY,
                """        sa.UniqueConstraint(
            "provider_payment_id", name=op.f("uq_payments_provider_payment_id")
        ),
""",
                "",
            ),
            (
                PAYMENT_MODELS,
                "provider_payment_id: Mapped[str | None] = mapped_column(Text, unique=True)",
                "provider_payment_id: Mapped[str | None] = mapped_column(Text)",
            ),
        ],
        expect=["test_provider_ids_are_unique[provider_payment_id]"],
    ),
    Case(
        id="t51-L5b-paid-has-anchor",
        what="D-077 layer 5: ck_payments_paid_has_anchor made vacuous",
        edits=[
            (
                MONEY,
                """            "status NOT IN ('paid', 'refunded') OR (provider_payment_id IS NOT NULL AND paid_at IS NOT NULL)",""",
                """            "true",""",
            )
        ],
        expect=["test_money_moved_means_an_anchor_exists"],
    ),
    Case(
        id="t51-L6-forced-overlap",
        what="D-077 layer 6: the race test's forced overlap removed (no wait for both to be open)",
        edits=[
            (
                RACES,
                "                        await asyncio.wait_for(self.all_open.wait(), OPEN_WAIT_S)\n",
                "",
            )
        ],
        expect=[
            "test_two_debits_of_the_whole_balance_take_turns",
            "test_two_credits_of_one_payment_at_once_apply_once",
        ],
    ),
    Case(
        id="t51-L-direction-check",
        what="D-077: ck_ledger_entries_reason_direction made a bare non-zero check",
        edits=[
            (
                SHAPE,
                """DIRECTION = (
    f"(reason IN ({_sql_list(CREDITS)}) AND delta > 0) "
    f"OR (reason IN ({_sql_list(DEBITS)}) AND delta < 0)"
)""",
                '''DIRECTION = "delta <> 0"''',
            )
        ],
        expect=["test_each_reason_has_one_direction_in_the_database"],
    ),
    # --- D-076's two triggers --------------------------------------------------
    Case(
        id="t51-G1-ledger-trigger-removed",
        what="D-076: ledger_entries_only_men never created",
        edits=[
            (
                MEN,
                """    ("ledger_entries_only_men", "before insert", "ledger_entries", None),
""",
                "",
            )
        ],
        expect=[
            "test_only_a_man_may_hold_credits[a ledger row]",
            "test_no_gender_yet_is_refused_so_choosing_female_holds_nothing",
        ],
    ),
    Case(
        id="t51-G2-wallet-trigger-removed",
        what="D-076: wallets_only_men never created",
        edits=[
            (
                MEN,
                """    ("wallets_only_men", "before insert or update", "wallets", "new.balance <> 0"),
""",
                "",
            )
        ],
        expect=[
            "test_only_a_man_may_hold_credits[a balance set]",
            "test_only_a_man_may_hold_credits[a wallet inserted with a balance]",
            "test_only_a_man_may_hold_credits[a wallet moved to them]",
            "test_no_gender_yet_is_refused_so_choosing_female_holds_nothing",
        ],
    ),
    Case(
        id="t51-G3-ledger-trigger-blacklist",
        what="D-076: the ledger trigger a blacklist (refuses gender = 'female' only)",
        edits=[(MEN, GENDER_CHECK, blacklist_on("ledger_entries"))],
        expect=[
            "test_only_a_man_may_hold_credits[a ledger row]",
            "test_no_gender_yet_is_refused_so_choosing_female_holds_nothing",
        ],
    ),
    Case(
        id="t51-G4-wallet-trigger-blacklist",
        what="D-076: the wallet trigger a blacklist (refuses gender = 'female' only)",
        edits=[(MEN, GENDER_CHECK, blacklist_on("wallets"))],
        expect=[
            "test_only_a_man_may_hold_credits[a balance set]",
            "test_no_gender_yet_is_refused_so_choosing_female_holds_nothing",
        ],
    ),
    Case(
        id="t51-G5-migration-precheck",
        what="D-076: the migration no longer counts what someone else already holds",
        edits=[(MEN, "    op.execute(sa.text(REQUIRE_NOTHING_HELD))\n", "")],
        expect=[
            "test_the_migration_refuses_to_guard_what_someone_else_holds[a ledger row",
            "test_the_migration_refuses_to_guard_what_someone_else_holds[a balance",
        ],
    ),
    # --- The service's checks --------------------------------------------------
    Case(
        id="t51-S1-transaction",
        what="service: runs outside a transaction",
        edits=[(SERVICE, "    if not session.in_transaction():\n", "    if False:\n")],
        expect=["test_outside_a_transaction_is_refused"],
    ),
    Case(
        id="t51-S2-bool-amount",
        what="service: a bool taken as an amount",
        edits=[
            (
                SERVICE,
                "    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:",
                "    if not isinstance(amount, int) or amount <= 0:",
            )
        ],
        expect=["test_the_amount_is_a_whole_number_above_zero[True]"],
    ),
    Case(
        id="t51-S3-amount-above-zero",
        what="service: an amount of 0 or less taken",
        edits=[
            (
                SERVICE,
                "    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:",
                "    if isinstance(amount, bool) or not isinstance(amount, int):",
            )
        ],
        expect=[
            "test_the_amount_is_a_whole_number_above_zero[0]",
            "test_the_amount_is_a_whole_number_above_zero[-5]",
        ],
    ),
    Case(
        id="t51-S4-direction",
        what="service: a reason taken in either direction",
        edits=[(RULES, "    if direction is not rule.direction:\n", "    if False:\n")],
        expect=["test_each_reason_is_taken_in_its_own_direction_only"],
    ),
    Case(
        id="t51-S5-ref-match",
        what="service: any ref type taken for any reason",
        edits=[(RULES, "    elif ref.type != rule.ref_type:\n", "    elif False:\n")],
        expect=[
            "test_the_ref_and_event_must_be_the_reasons_own[another ref type]",
            "test_the_ref_and_event_must_be_the_reasons_own[admin_grant naming a payment]",
        ],
    ),
    Case(
        id="t51-S6-bare-refund",
        what="service: bare refund taken",
        edits=[
            (
                RULES,
                "REFUSED = frozenset({LedgerReason.REFUND})",
                "REFUSED: frozenset[LedgerReason] = frozenset()",
            )
        ],
        expect=[
            "test_bare_refund_is_refused_and_writes_nothing",
            "test_each_reason_is_taken_in_its_own_direction_only",
        ],
    ),
    Case(
        id="t51-S7-men-only-in-service",
        what="service: no gender check of its own (the database still refuses)",
        edits=[(SERVICE, "    if gender is not Gender.MALE:\n", "    if False:\n")],
        expect=[
            "test_anyone_but_a_man_is_refused_by_the_service[a woman]",
            "test_anyone_but_a_man_is_refused_by_the_service[no gender]",
            "test_no_gender_yet_is_refused_so_choosing_female_holds_nothing",
        ],
    ),
    Case(
        id="t51-S8-insufficient",
        what="service: a debit beyond the balance not refused (the database CHECK still refuses)",
        edits=[
            (
                SERVICE,
                "    if direction is Direction.DEBIT and balance < amount:\n",
                "    if direction is Direction.DEBIT and False:\n",
            )
        ],
        expect=[
            "test_a_debit_beyond_the_balance_is_refused_and_writes_nothing",
            "test_an_insufficient_balance_answers_with_its_code_and_two_numbers",
            "test_two_debits_of_the_whole_balance_take_turns",
        ],
    ),
    Case(
        id="t51-S9-event-rules",
        what="service: the event rules not checked",
        edits=[
            (
                RULES,
                "    if not rule.caller_names_event:\n        if event is not None:",
                "    if False:\n        if event is not None:",
            ),
            (
                RULES,
                "    elif not isinstance(event, str) or not 1 <= len(event) <= EVENT_MAX_LENGTH:",
                "    elif False:",
            ),
        ],
        expect=[
            "test_the_ref_and_event_must_be_the_reasons_own[an event where the ref is the event]",
            "test_the_ref_and_event_must_be_the_reasons_own[an event too long]",
        ],
    ),
    # --- Events ---------------------------------------------------------------
    Case(
        id="t51-E1-publish-before-commit",
        what="events: queued straight onto the committed list (published whatever happens)",
        edits=[
            (
                EVENTS,
                "    pending.append((transaction, Event(user_id, type_, data)))",
                "    sync.info.setdefault(_COMMITTED, []).append(Event(user_id, type_, data))",
            )
        ],
        expect=[
            "test_an_event_is_dropped_when_its_transaction_rolls_back",
            "test_a_rolled_back_credit_publishes_nothing",
        ],
    ),
    Case(
        id="t51-E2-release-counts-as-commit",
        what="events: a released savepoint's events kept as if committed",
        edits=[
            (EVENTS, "    if session.in_nested_transaction():\n        return\n", "")
        ],
        expect=["test_a_released_savepoints_events_wait_for_the_outer_commit"],
    ),
    Case(
        id="t51-E3-failed-publish-raises",
        what="events: a failed publish fails the request",
        edits=[
            (
                EVENTS,
                "    except Exception as error:  # noqa: BLE001 — whatever failed, the request stands",
                "    except ZeroDivisionError as error:  # noqa: BLE001 — whatever failed, the request stands",
            )
        ],
        expect=["test_a_failed_publish_is_logged_and_the_request_stands"],
    ),
    Case(
        id="t51-E4-no-timeout",
        what="events: no timeout on the publish",
        edits=[
            (
                EVENTS,
                "        async with asyncio.timeout(PUBLISH_TIMEOUT_S):",
                "        async with asyncio.timeout(None):",
            )
        ],
        expect=["test_a_publish_that_never_answers_is_cut_off"],
    ),
    Case(
        id="t51-E5-publish-under-the-session",
        what="get_session: publishes before the session has closed",
        edits=[
            (
                DB,
                """            finally:
                committed = events.take_committed(session)
    finally:
        await events.publish(committed, request.app.state.redis)""",
                """            finally:
                committed = events.take_committed(session)
                await events.publish(committed, request.app.state.redis)
                committed = []
    finally:
        await events.publish(committed, request.app.state.redis)""",
            )
        ],
        expect=["test_the_publish_waits_for_the_session_to_close"],
    ),
    # --- The seed and make_user ------------------------------------------------
    Case(
        id="t51-K1-seed-key",
        what="seed: a new event for its grant every run",
        edits=[
            (
                SEED,
                "            event=SEED_EVENT,\n",
                '            event=f"{SEED_EVENT}-{clock.now().timestamp()}",\n',
            )
        ],
        expect=["test_a_second_run_changes_nothing"],
    ),
    Case(
        id="t51-K2-seed-insert-only",
        what="seed: credits only the people it creates (insert-only, no exception)",
        edits=[
            (
                SEED,
                "        if person.credits:\n",
                "        if person.credits and person.key in report.created:\n",
            )
        ],
        expect=["test_credits_reach_a_test_man_already_there"],
    ),
    Case(
        id="t51-M1-make-user-writes-balance",
        what="make_user: writes the balance itself instead of crediting",
        edits=[
            (
                CONFTEST,
                """        if credits:
            await wallet_service.credit(
                db, user.id, credits, LedgerReason.ADMIN_GRANT, event="make_user"
            )""",
                """        if credits:
            await db.execute(
                text("update wallets set balance = :c where user_id = :u"),
                {"c": credits, "u": user.id},
            )""",
            ),
            (
                CONFTEST,
                "import pytest\n",
                "import pytest\nfrom sqlalchemy import text\n",
            ),
        ],
        expect=[
            "test_credits_arrive_as_an_admin_grant",
            "test_make_user_never_writes_a_balance_itself",
        ],
    ),
    # --- Rule 15 ------------------------------------------------------------
    Case(
        id="t51-R1-key-logged",
        what="rule 15: the wallet logs its key",
        edits=[
            (
                SERVICE,
                """        delta=delta,
        balance_after=balance_after,
    )""",
                """        delta=delta,
        balance_after=balance_after,
        key=key,
    )""",
            )
        ],
        expect=["test_the_wallets_logs_and_refusals_carry_nothing_secret"],
    ),
]


# --- T-5.4: the same guards at fifty connections ------------------------------


def edits_of(case_id: str) -> list[tuple[str, str, str]]:
    """The edits of a T-5.1 case, reused where T-5.4 breaks the same guard."""
    return next(c["edits"] for c in T51 if c["id"] == case_id)


FIFTY_DEBITS = "test_fifty_debits_on_ten_two_apply_and_the_rest_find_it_gone"
ONE_KEY = "test_one_key_fifty_times_at_once_is_one_entry"
UNDER_FIFTY_KEYS = "test_one_payment_under_fifty_keys_is_one_entry"
LAST_LINE = "test_one_key_fifty_times_with_the_repeat_check_bypassed_is_one_entry"
TWO_MEN = "test_two_men_with_one_client_key_both_apply"

T54: list[Case] = [
    Case(
        id="t54-for-update",
        what="D-077 layer 4: the wallet read without FOR UPDATE",
        edits=[(REPO, "            .with_for_update(of=Wallet)\n", "")],
        expect=[FIFTY_DEBITS, f"{ONE_KEY}[debit]", f"{ONE_KEY}[credit]", TWO_MEN],
    ),
    Case(
        id="t54-repeat-before-lock",
        what="D-077 layer 4: the repeat check made before the lock is granted",
        edits=edits_of("t51-L4b-repeat-before-lock"),
        expect=[f"{ONE_KEY}[debit]", f"{ONE_KEY}[credit]", TWO_MEN],
    ),
    Case(
        id="t54-repeat-check-removed",
        what="D-077 layer 4: no repeat check at all",
        edits=[
            (
                SERVICE,
                "    existing = await repository.entry_by_key(session, key)\n",
                "    existing = None\n",
            )
        ],
        expect=[f"{ONE_KEY}[debit]", f"{ONE_KEY}[credit]", TWO_MEN],
    ),
    Case(
        id="t54-unique-key",
        what="D-077 layer 1: ledger_entries.idempotency_key not UNIQUE (migration and model)",
        edits=edits_of("t51-L1-unique-key"),
        expect=[LAST_LINE],
    ),
    Case(
        id="t54-per-event-index",
        what="D-077 layer 3: the per-event index not unique (migration and model)",
        edits=edits_of("t51-L3a-per-event-index"),
        expect=[UNDER_FIFTY_KEYS],
    ),
    Case(
        id="t54-forced-overlap",
        what="D-077 layer 6: the harness's forced overlap removed",
        edits=[
            (
                RACES,
                "                        await asyncio.wait_for(self.all_open.wait(), OPEN_WAIT_S)\n",
                "",
            )
        ],
        expect=[
            FIFTY_DEBITS,
            f"{ONE_KEY}[debit]",
            f"{ONE_KEY}[credit]",
            UNDER_FIFTY_KEYS,
            LAST_LINE,
            TWO_MEN,
        ],
    ),
]


# --- T-4.4: the worker, moderation, D-092's Pillow, D-093, D-094, the seed's photos --
# Each case's selection is the files that must catch it.

T44: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t44-01-exif-carried-into-the-output-d-092-1",
            what="EXIF carried into the output (D-092 1)",
            edits=[
                (
                    "app/core/images.py",
                    "                width, height = image.size\n",
                    '                width, height = image.size\n                _carried = image.info.get("exif", b"")\n',
                ),
                (
                    "app/core/images.py",
                    '    clean.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)',
                    '    clean.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, exif=_carried)',
                ),
            ],
            expect=[
                "test_no_location_survives_the_reencode[image/jpeg]",
                "test_no_location_survives_the_reencode[image/png]",
                "test_no_location_survives_the_reencode[image/webp]",
                "test_a_located_photo_is_stored_with_no_location_anywhere",
            ],
        ),
        ["tests/core/test_reencode.py", "tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-02-a-metadata-strip-the-original-bytes-kept",
            what="a metadata strip: the original bytes kept (D-092 1)",
            edits=[
                (
                    "app/core/images.py",
                    "    return Reencoded(data=out.getvalue(), width=clean.width, height=clean.height)",
                    "    return Reencoded(data=data, width=clean.width, height=clean.height)",
                ),
            ],
            expect=[
                "test_no_location_survives_the_reencode[image/jpeg]",
                "test_a_located_photo_is_stored_with_no_location_anywhere",
            ],
        ),
        ["tests/core/test_reencode.py", "tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-03-the-pixel-limit-removed-pillow-s-default",
            what="the pixel limit removed, Pillow's default left (D-092 2)",
            edits=[
                ("app/core/images.py", "Image.MAX_IMAGE_PIXELS = MAX_PIXELS\n", "\n"),
                (
                    "app/core/images.py",
                    "                if width * height > MAX_PIXELS:\n                    raise TooManyPixels\n",
                    "",
                ),
            ],
            expect=[
                "test_a_bomb_under_pillows_default_is_refused_by_our_limit",
                "test_the_limit_is_set_here_never_left_to_pillows_default",
            ],
        ),
        ["tests/core/test_reencode.py"],
    ),
    (
        Case(
            id="t44-04-every-pillow-parser-reachable",
            what="every Pillow parser reachable",
            edits=[
                (
                    "app/core/images.py",
                    "io.BytesIO(data), formats=[_PILLOW_FORMAT[image_type]]",
                    "io.BytesIO(data), formats=None",
                ),
            ],
            expect=["test_only_the_judged_format_is_parsed"],
        ),
        ["tests/core/test_reencode.py"],
    ),
    (
        Case(
            id="t44-05-pillow-pinned-with-d-092-3",
            what="Pillow pinned with >= (D-092 3)",
            edits=[
                ("pyproject.toml", '"pillow==12.3.0",', '"pillow>=12.3.0",'),
            ],
            expect=["test_pillow_is_pinned_exactly_and_the_pin_is_what_runs"],
        ),
        ["tests/core/test_reencode.py"],
    ),
    (
        Case(
            id="t44-06-idempotency-removed",
            what="idempotency removed",
            edits=[
                (
                    "app/modules/photos/service.py",
                    '    if photo.status is not ReviewStatus.PENDING:\n        return f"already {photo.status.value}: nothing to do"\n',
                    "",
                ),
            ],
            expect=["test_running_it_again_on_a_decided_photo_does_nothing"],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-07-a-private-photo-published",
            what="a private photo published",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "        if locked.kind is PhotoKind.PUBLIC:\n            key = public_photo_key(locked.id)",
                    "        if True:\n            key = public_photo_key(locked.id)",
                ),
            ],
            expect=[
                "test_an_approved_private_photo_never_reaches_the_public_bucket",
                "test_a_located_photo_is_stored_with_no_location_anywhere[private]",
            ],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-08-the-public-copy-copied-from-the-upload-n",
            what="the public copy copied from the upload, not the bytes scored",
            edits=[
                (
                    "app/modules/photos/service.py",
                    '            await _stored(\n                storage.put_bytes(\n                    settings.R2_BUCKET_PUBLIC, key, clean.data, "image/jpeg"\n                )\n            )',
                    "            await storage.copy(settings.R2_BUCKET_PRIVATE, locked.raw_key, settings.R2_BUCKET_PUBLIC, key)",
                ),
            ],
            expect=[
                "test_the_public_copy_is_what_was_scored_even_if_the_upload_changed"
            ],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-09-a-possible-minor-not-recorded-d-093-3-4",
            what="a possible minor not recorded (D-093 3, 4)",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "            safety_service.record_possible_minor(\n                session,\n                locked.user_id,\n                score=max(scores.minors),\n                model=MINOR_MODEL,\n            )\n",
                    "",
                ),
            ],
            expect=[
                "test_a_possible_minor_is_rejected_recorded_as_a_score_and_every_copy_deleted",
                "test_a_possible_minors_photo_still_stored_is_tried_again_until_gone",
            ],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-10-a-possible-minor-s-copies-kept-d-093-4",
            what="a possible minor's copies kept (D-093 4)",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "    if reason == moderation_rules.MINOR_SUSPECTED:\n        await _delete_every_copy(photo, storage, settings)\n",
                    "",
                ),
            ],
            expect=[
                "test_a_possible_minor_is_rejected_recorded_as_a_score_and_every_copy_deleted",
                "test_a_minor_score_wins_over_nudity",
            ],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-11-the-deletion-assumed-not-read-back",
            what="the deletion assumed, not read back",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "    except Exception:  # noqa: BLE001 — unreadable is not proof it left\n        return False\n    return False\n",
                    "    except Exception:  # noqa: BLE001 — unreadable is not proof it left\n        return False\n    return True\n",
                ),
            ],
            expect=[
                "test_a_possible_minors_photo_still_stored_is_tried_again_until_gone"
            ],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-13-the-user-s-row-not-locked-before-the-dec",
            what="the user's row not locked before the decision",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "        try:\n            await users_service.locked_user(session, photo.user_id)\n        except LookupError:\n            locked = None\n        else:\n            locked = await repository.photo_for_update(session, photo.user_id, photo.id)\n",
                    "        locked = await repository.photo_for_update(session, photo.user_id, photo.id)\n",
                ),
            ],
            expect=["test_the_decision_and_a_reorder_take_turns"],
        ),
        ["tests/modules/photos/test_moderate_race.py"],
    ),
    (
        Case(
            id="t44-14-nudity-checked-before-a-possible-minor",
            what="nudity checked before a possible minor",
            edits=[
                (
                    "app/modules/photos/moderation.py",
                    '    if any(score >= MINOR_AT for score in scores.minors):\n        return "minor_suspected"\n    if max(scores.nudity[name] for name in EXPLICIT) >= NUDITY_AT:\n        return "nudity"\n',
                    '    if max(scores.nudity[name] for name in EXPLICIT) >= NUDITY_AT:\n        return "nudity"\n    if any(score >= MINOR_AT for score in scores.minors):\n        return "minor_suspected"\n',
                ),
            ],
            expect=["test_a_minor_score_wins_over_nudity"],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-15-human-review-turned-on-a-workflow-in-the",
            what="human review turned on: a workflow in the request",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    '            "models": ",".join(MODELS),\n',
                    '            "models": ",".join(MODELS),\n            "workflow": "wfl_human_review",\n',
                ),
            ],
            expect=[
                "test_a_check_is_one_post_of_the_image_with_three_models",
                "test_every_request_stays_on_the_plain_image_api",
            ],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-16-a-second-sightengine-endpoint-workflows",
            what="a second Sightengine endpoint (workflows)",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    'CHECK_URL: Final = "https://api.sightengine.com/1.0/check.json"',
                    'CHECK_URL: Final = "https://api.sightengine.com/1.0/check-workflow.json"',
                ),
            ],
            expect=["test_every_request_stays_on_the_plain_image_api"],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-17-a-lax-reader-types-coerced",
            what="a lax reader: types coerced",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    'model_config = ConfigDict(strict=True, extra="allow", frozen=True)',
                    'model_config = ConfigDict(strict=False, extra="allow", frozen=True)',
                ),
            ],
            expect=[
                "test_an_answer_in_any_other_shape_fails_loudly_never_reads_as_zero[a score as a string]"
            ],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-18-a-lax-reader-a-missing-score-read-as-0",
            what="a lax reader: a missing score read as 0",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    "    erotica: float\n",
                    "    erotica: float = 0.0\n",
                ),
            ],
            expect=[
                "test_an_answer_in_any_other_shape_fails_loudly_never_reads_as_zero[a nudity class missing]"
            ],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-19-the-keys-sent-in-the-url",
            what="the keys sent in the URL",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    "                data=self._form,\n",
                    "                params=self._form,\n",
                ),
            ],
            expect=[
                "test_a_check_is_one_post_of_the_image_with_three_models",
                "test_every_request_stays_on_the_plain_image_api",
            ],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-20-the-fake-drifted-back-to-the-documentati",
            what="the fake drifted back to the documentation (D-094)",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    '    "text": {"has_artificial": 0.01, "has_natural": 0.02},',
                    '    "text": {"has_artificial": 0.01, "has_natural": 0.02, "boxes": []},',
                ),
            ],
            expect=["test_an_answer_with_no_text_has_no_boxes_as_real_answers_do"],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-21-the-upload-kept-until-sightengine-answer",
            what="the upload kept until Sightengine answers",
            edits=[
                (
                    "app/modules/photos/service.py",
                    '    await _stored(storage.put_bytes(private, photo.raw_key, clean.data, "image/jpeg"))\n',
                    "",
                ),
            ],
            expect=[
                "test_a_moderation_failure_tries_again_and_keeps_no_original",
                "test_a_located_photo_is_stored_with_no_location_anywhere",
            ],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-22-trusting-the-type-complete-saw",
            what="trusting the type complete saw",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "    image_type = sniff(data[:SNIFF_BYTES])\n",
                    '    image_type = sniff(b"\\xff\\xd8\\xff")\n',
                ),
            ],
            expect=["test_the_bytes_decide_again_not_what_complete_saw"],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-23-no-size-bound-at-the-worker",
            what="no size bound at the worker",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "    if len(data) > MAX_UPLOAD_BYTES:\n",
                    "    if False:\n",
                ),
            ],
            expect=[
                "test_what_the_worker_cant_read_is_rejected_and_its_file_removed[over 8 MB since complete]"
            ],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-24-an-unreadable-upload-s-file-left-behind",
            what="an unreadable upload's file left behind",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "        locked.reject_reason = reason\n    await storage.delete(settings.R2_BUCKET_PRIVATE, photo.raw_key)\n",
                    "        locked.reject_reason = reason\n",
                ),
            ],
            expect=["test_what_the_worker_cant_read_is_rejected_and_its_file_removed"],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-25-a-refused-user-s-re-encoded-copy-left-be",
            what="a refused user's re-encoded copy left behind",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "            # have run before the copy above was written. Don't leave it.\n            await storage.delete(settings.R2_BUCKET_PRIVATE, photo.raw_key)\n",
                    "            # have run before the copy above was written. Don't leave it.\n",
                ),
            ],
            expect=["test_a_user_refused_while_their_photo_was_checked_leaves_no_file"],
        ),
        ["tests/modules/photos/test_moderate.py"],
    ),
    (
        Case(
            id="t44-26-the-third-failure-retried-never-logged",
            what="the third failure retried, never logged",
            edits=[
                (
                    "app/workers/tasks/moderate_photo.py",
                    "        if job_try < MODERATE_TRIES:\n",
                    "        if job_try <= MODERATE_TRIES:\n",
                ),
            ],
            expect=[
                "test_the_third_failure_logs_an_error_and_leaves_the_photo_pending"
            ],
        ),
        ["tests/workers/test_moderate_photo.py"],
    ),
    (
        Case(
            id="t44-27-the-worker-starts-without-sightengine-s",
            what="the worker starts without Sightengine's keys",
            edits=[
                (
                    "app/workers/main.py",
                    '    if settings.MODERATION_PROVIDER == "sightengine":\n',
                    "    if False:\n",
                ),
            ],
            expect=[
                "test_sightengine_without_its_keys_is_refused_naming_them",
                "test_check_says_why_it_wouldnt_start_and_never_echoes_a_value",
            ],
        ),
        ["tests/workers/test_worker.py"],
    ),
    (
        Case(
            id="t44-28-arq-s-default-0-5-s-poll-d-091",
            what="ARQ's default 0.5 s poll (D-091)",
            edits=[
                (
                    "app/workers/main.py",
                    '        "poll_delay": settings.WORKER_POLL_DELAY_S,\n',
                    '        "poll_delay": 0.5,\n',
                ),
            ],
            expect=[
                "test_it_polls_every_10_seconds_which_is_d091s_sum",
                "test_the_poll_delay_is_a_setting",
            ],
        ),
        ["tests/workers/test_worker.py"],
    ),
    (
        Case(
            id="t44-29-arq-logs-the-job-s-arguments-rule-15",
            what="ARQ logs the job's arguments (rule 15)",
            edits=[
                (
                    "app/workers/main.py",
                    '            record.args = (waited, ref, "…", extra)\n',
                    "            record.args = (waited, ref, _, extra)\n",
                ),
            ],
            expect=[
                "test_arq_never_logs_a_jobs_arguments_which_can_be_storage_keys",
                "test_the_started_line_keeps_the_jobs_name_and_timing",
            ],
        ),
        ["tests/workers/test_worker.py"],
    ),
    (
        Case(
            id="t44-30-the-worker-s-errors-carry-query-values-r",
            what="the worker's errors carry query values (rule 15)",
            edits=[
                (
                    "app/workers/main.py",
                    "        hide_parameters=True,\n",
                    "        hide_parameters=False,\n",
                ),
            ],
            expect=["test_the_workers_database_errors_carry_no_values"],
        ),
        ["tests/workers/test_worker.py"],
    ),
    (
        Case(
            id="t44-31-the-worker-s-fly-config-drifts-from-the",
            what="the worker's Fly config drifts from the API's",
            edits=[
                (
                    "../infra/fly.worker.toml",
                    'R2_BUCKET_PUBLIC = "velora-staging-public"',
                    'R2_BUCKET_PUBLIC = "velora-staging-other"',
                ),
            ],
            expect=["test_the_worker_reads_the_same_settings_as_the_api_on_staging"],
        ),
        ["tests/workers/test_worker.py"],
    ),
    (
        Case(
            id="t44-32-the-seed-adds-a-second-photo-on-a-re-run",
            what="the seed adds a second photo on a re-run",
            edits=[
                ("seed/run.py", "    if held is not None:\n        return\n", ""),
            ],
            expect=[
                "test_a_second_run_adds_no_photo",
                "test_a_place_0_that_already_holds_a_live_photo_gets_none",
                "test_a_second_run_changes_nothing",
            ],
        ),
        [
            "tests/seed/test_seed.py::test_a_second_run_adds_no_photo",
            "tests/seed/test_seed.py::test_a_place_0_that_already_holds_a_live_photo_gets_none",
            "tests/seed/test_seed.py::test_a_second_run_changes_nothing",
        ],
    ),
    (
        Case(
            id="t44-33-the-seed-s-placeholder-not-re-encoded",
            what="the seed's placeholder not re-encoded",
            edits=[
                (
                    "seed/photos.py",
                    '    return reencode(out.getvalue(), "image/png")\n',
                    "    return Reencoded(data=out.getvalue(), width=SIZE[0], height=SIZE[1])\n",
                ),
            ],
            expect=[
                "test_everyone_past_the_photos_step_has_an_approved_photo_at_place_0"
            ],
        ),
        [
            "tests/seed/test_seed.py::test_everyone_past_the_photos_step_has_an_approved_photo_at_place_0"
        ],
    ),
]

# --- T-4.6: D-096's read, and what an owner is told ------------------------------

OUTCOME = ["tests/modules/photos/test_outcome.py"]
T46: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t46-01-every-reason-reaches-the-owner-by-name",
            what="every reason reaches the owner by name",
            edits=[
                (
                    "app/modules/photos/service.py",
                    "    if reason is None or reason in OWNER_REASONS:\n",
                    "    if True:\n",
                )
            ],
            expect=["test_any_other_reason_reaches_its_owner_as_other"],
        ),
        OUTCOME,
    ),
    (
        Case(
            id="t46-02-someone-else-s-photo-readable",
            what="someone else's photo readable",
            edits=[
                (
                    "app/modules/photos/repository.py",
                    "            Photo.id == photo_id,\n            Photo.user_id == user_id,\n            Photo.kind.in_(",
                    "            Photo.id == photo_id,\n            Photo.kind.in_(",
                )
            ],
            expect=["test_someone_elses_photo_a_selfie_and_no_photo_answer_alike"],
        ),
        OUTCOME,
    ),
    (
        Case(
            id="t46-03-a-selfie-readable",
            what="a selfie readable",
            edits=[
                (
                    "app/modules/photos/repository.py",
                    "            Photo.user_id == user_id,\n            Photo.kind.in_((PhotoKind.PUBLIC, PhotoKind.PRIVATE)),\n        )\n    )\n    return photo\n",
                    "            Photo.user_id == user_id,\n        )\n    )\n    return photo\n",
                )
            ],
            expect=["test_someone_elses_photo_a_selfie_and_no_photo_answer_alike"],
        ),
        OUTCOME,
    ),
]

CASES: list[tuple[Case, list[str]]] = (
    [(c, T51_SELECTION) for c in T51] + [(c, T54_SELECTION) for c in T54] + T44 + T46
)

# The fifty-connection fixture's own message when Postgres refuses a connection.
REFUSED_CONNECTIONS = "connections ("


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked() -> dict[str, str]:
    """Every file under api/ but caches and the virtualenv, and infra/'s Fly
    configs (T-4.4 breaks one), by SHA-256, keyed by their path from api/."""
    skip = {".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    files = {
        str(path.relative_to(API)): sha(path)
        for path in API.rglob("*")
        if path.is_file() and not skip & set(path.relative_to(API).parts)
    }
    for path in (API.parent / "infra").glob("fly.*.toml"):
        files[f"../infra/{path.name}"] = sha(path)
    return files


def failed_tests(output: str) -> list[str]:
    """The node ids pytest's `-rfE` summary names, whole. A parametrize id may
    hold spaces and even " - ", so the brackets are read as one; the summary's
    own " - " starts the message after them."""
    pattern = r"^(?:FAILED|ERROR) (\S+?(?:\[.*?\])?)(?: - .*)?$"
    return sorted(set(re.findall(pattern, output, re.MULTILINE)))


def run_tests(selection: list[str]) -> tuple[int, str, float]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("TEST_DATABASE_URL", None)
    start = time.monotonic()
    proc = subprocess.run(  # its exit code is read below
        # --frozen: a case that edits pyproject.toml mustn't re-lock (T-4.4).
        [
            "uv",
            "run",
            "--frozen",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-rfE",
            *selection,
        ],
        cwd=API,
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr, time.monotonic() - start


def run_case(
    case: Case, selection: list[str], before: dict[str, str]
) -> dict[str, Any]:
    originals: dict[str, bytes] = {}
    for rel, old, new in case["edits"]:
        path = API / rel
        originals.setdefault(rel, path.read_bytes())
        text = path.read_text()
        if text.count(old) != 1:
            raise SystemExit(f"{case['id']}: its anchor in {rel} is gone or ambiguous")
        path.write_text(text.replace(old, new))
    try:
        code, output, took = run_tests(selection)
    finally:
        for rel, data in originals.items():
            (API / rel).write_bytes(data)
    restored = all(sha(API / rel) == before[rel] for rel in originals)
    failed = failed_tests(output)
    missing = [e for e in case["expect"] if not any(e in f for f in failed)]
    summary = [
        line for line in output.splitlines() if re.search(r"\d+ (passed|failed)", line)
    ]
    inconclusive = REFUSED_CONNECTIONS in output and "of 50" in output
    return {
        "id": case["id"],
        "red": code != 0 and not missing and not inconclusive,
        "inconclusive": inconclusive,
        "missing": missing,
        "failed": failed,
        "summary": summary[-1] if summary else output[-300:],
        "seconds": round(took, 1),
        "restored": restored,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "prefixes", nargs="*", help="run cases whose id starts with these"
    )
    parser.add_argument("--repeat", type=int, default=1, help="runs per case")
    parser.add_argument("--list", action="store_true", help="list the cases and stop")
    parser.add_argument("--json", type=Path, help="write every run's result here")
    args = parser.parse_args()
    chosen = [
        (case, selection)
        for case, selection in CASES
        if not args.prefixes or any(case["id"].startswith(p) for p in args.prefixes)
    ]
    if args.list or not chosen:
        for case, _ in chosen or CASES:
            say(f"{case['id']:32} {case['what']}")
        return 0 if args.list else 2
    before = tracked()
    runs: list[dict[str, Any]] = []
    for case, selection in chosen:
        for attempt in range(1, args.repeat + 1):
            result = run_case(case, selection, before)
            runs.append(result)
            verdict = (
                "INCONCLUSIVE (Postgres refused connections)"
                if result["inconclusive"]
                else "red"
                if result["red"]
                else f"NOT RED, missing {result['missing']}"
            )
            say(
                f"{case['id']} run {attempt}/{args.repeat}: {verdict}; "
                f"{result['summary'].strip()}; restored={result['restored']}",
            )
            if args.json:
                args.json.write_text(json.dumps(runs, indent=2))
    changed = sorted(
        k for k in set(before) | set(tracked()) if before.get(k) != tracked().get(k)
    )
    say(f"files differing from before the runs: {changed or 'none'}")
    by_case: dict[str, list[bool]] = {}
    for run in runs:
        by_case.setdefault(run["id"], []).append(run["red"])
    for case_id, reds in by_case.items():
        say(f"  {case_id}: red in {sum(reds)} of {len(reds)}")
    if changed or not all(run["restored"] for run in runs):
        return 3
    return 0 if all(all(reds) for reds in by_case.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
