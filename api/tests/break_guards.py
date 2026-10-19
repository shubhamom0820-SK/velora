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
# From T-5.2 the direction CHECK, the ref-type CHECK and the per-event index are
# re-created by this migration, so a weakening of 97ddae55f597's copies never
# reaches the head: T-5.1's three cases for them weaken this file instead.
SHAPE_T52 = (
    "alembic/versions/20261004_a1d7de534ef7_ledger_shape_names_the_new_reasons.py"
)
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
                SHAPE_T52,
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
            "test_one_entry_per_event_except_the_reasons_that_repeat",
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
                SHAPE_T52,
                """    return "ref_type IS NULL OR (reason, ref_type) IN ({})".format(""",
                """    return "true OR (reason, ref_type) IN ({})".format(""",
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
                """    balance, gender = await _lock(session, user_id)
    if gender is not Gender.MALE:
        raise WalletMisuse("only a man may hold credits (D-076)")

    existing = await repository.entry_by_key(session, key)
""",
                """    existing = await repository.entry_by_key(session, key)
    balance, gender = await _lock(session, user_id)
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
                SHAPE_T52,
                """    return (
        f"(reason IN ({_sql_list(CREDITS)}) AND delta > 0) "
        f"OR (reason IN ({_sql_list(debits)}) AND delta < 0)"
    )""",
                '''    return "delta <> 0"''',
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
        edits=[
            (
                SERVICE,
                "    if not session.in_transaction():\n        raise WalletMisuse(\n",
                "    if False:\n        raise WalletMisuse(\n",
            )
        ],
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
                """            await grant(db, user.id, credits, event="make_user")""",
                """            await db.execute(
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
                    "        try:\n            user = await users_service.locked_user(session, photo.user_id)\n        except LookupError:\n            locked = None\n        else:\n            locked = await repository.photo_for_update(session, photo.user_id, photo.id)\n",
                    "        user = await users_service.get_user(session, photo.user_id)\n        locked = await repository.photo_for_update(session, photo.user_id, photo.id)\n",
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
            what="the worker's settings drift from the API's (P-49: compose.yml)",
            edits=[
                (
                    "../infra/gce/compose.yml",
                    '      WORKER_POLL_DELAY_S: "10"\n',
                    '      WORKER_POLL_DELAY_S: "10"\n      R2_BUCKET_PUBLIC: velora-staging-other\n',
                ),
            ],
            expect=["test_the_worker_reads_the_same_settings_as_the_api"],
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
    # The founder's answers, 4 October 2026: D-101's minor threshold, and the
    # reader strict only where it reads.
    (
        Case(
            id="t44-34-the-minor-threshold-back-at-the-coin-flip",
            what="D-101: a possible minor from 0.5, not 0.35",
            edits=[
                (
                    "app/modules/photos/moderation.py",
                    "MINOR_AT: Final = 0.35  # an asymmetry, not data: see above (D-101)\n",
                    "MINOR_AT: Final = 0.5\n",
                )
            ],
            expect=["test_a_possible_minor_from_0_35[0.35-minor_suspected]"],
        ),
        ["tests/modules/photos/test_moderation_rules.py"],
    ),
    (
        Case(
            id="t44-35-an-unknown-field-refused",
            what="the reader refuses a field it has never seen",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    'model_config = ConfigDict(strict=True, extra="allow", frozen=True)',
                    'model_config = ConfigDict(strict=True, extra="forbid", frozen=True)',
                )
            ],
            expect=["test_a_field_never_seen_is_logged_once_by_name_never_refused"],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-36-an-unread-field-required",
            what="the reader requires a field the decision never reads (media)",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    "    artificial_faces: list[Any]\n    text: _Text\n",
                    "    artificial_faces: list[Any]\n    text: _Text\n    media: dict[str, Any]\n",
                )
            ],
            expect=["test_a_field_the_decision_never_reads_may_go[media]"],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-37-an-unknown-field-unnoticed",
            what="a field never seen passes without a log line",
            edits=[
                (
                    "app/core/providers/moderation.py",
                    '        log.warning("moderation.unknown_fields", fields=sorted(unknown))\n',
                    "        pass\n",
                )
            ],
            expect=["test_a_field_never_seen_is_logged_once_by_name_never_refused"],
        ),
        ["tests/core/test_moderation.py"],
    ),
    (
        Case(
            id="t44-38-the-minor-score-not-kept",
            what="D-101's revisit: a photo's minor score not kept below the threshold",
            edits=[
                (
                    "app/modules/photos/moderation.py",
                    '        "minor": max(scores.minors, default=None),\n',
                    "",
                )
            ],
            expect=["test_an_approved_public_photo_is_published_from_the_bytes_scored"],
        ),
        ["tests/modules/photos/test_moderate.py"],
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
                    "            Photo.user_id == user_id,\n            Photo.kind.in_(OWNERS_KINDS),\n        )\n    )\n    return photo\n",
                    "            Photo.user_id == user_id,\n        )\n    )\n    return photo\n",
                )
            ],
            expect=["test_someone_elses_photo_a_selfie_and_no_photo_answer_alike"],
        ),
        OUTCOME,
    ),
]

# --- The landing guard (4 October 2026): a push to main asks the checks itself ----

GUARD = "tests/test_push_gate.py"
REFUSES = "test_the_landing_guard_refuses_what_it_should"

LAND: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="land-1-the-marks-not-asked",
            what="push-gate lets main move without make lint and make test's marks",
            edits=[
                (
                    "../scripts/push-gate",
                    '    [[ -f "$marks/$kind-$tree" ]] || missing+=("make $kind")\n',
                    "    :\n",
                )
            ],
            expect=[REFUSES],
        ),
        [GUARD],
    ),
    (
        Case(
            id="land-2-ci-not-asked",
            what="push-gate lets main move without asking CI",
            edits=[
                (
                    "../scripts/push-gate",
                    '  if ! "$root/scripts/with-tools" --need gh "$ci_gate" --branch "$branch" "$local_sha" </dev/null >&2; then\n',
                    "  if false; then\n",
                )
            ],
            expect=[REFUSES],
        ),
        [GUARD],
    ),
    (
        Case(
            id="land-3-only-main-s-first-line",
            what="push-gate reads only the first ref of a push",
            edits=[
                (
                    "../scripts/push-gate",
                    "while read -r _local_ref local_sha remote_ref _remote_sha; do\n",
                    "read -r _local_ref local_sha remote_ref _remote_sha; for _once in 1; do\n",
                ),
            ],
            expect=[REFUSES],
        ),
        [GUARD],
    ),
    (
        Case(
            id="land-4-a-dirty-tree-marked",
            what="mark-checked vouches for a tree with changes not committed",
            edits=[
                (
                    "../scripts/mark-checked",
                    'if [[ -n "$(git status --porcelain)" ]]; then echo dirty; else',
                    "if false; then echo dirty; else",
                )
            ],
            expect=[REFUSES],
        ),
        [GUARD],
    ),
    (
        Case(
            id="land-5-any-branch-s-run",
            what="push-gate reads whichever branch's run points at the commit (P-140)",
            edits=[
                (
                    "../scripts/push-gate",
                    '    elif [[ -n "$carried" && "$(wc -l <<<"$carried" | tr -d \' \')" == 1 ]]; then\n      branch="$carried"\n',
                    '    elif [[ -n "$carried" ]]; then\n      branch="$(head -n 1 <<<"$carried")"\n',
                )
            ],
            expect=[REFUSES],
        ),
        [GUARD],
    ),
]

# --- T-5.2: prices, charge(), the debit's callers, the two reasons ---------------

PRICING = "app/modules/pricing/service.py"
PRICING_REPO = "app/modules/pricing/repository.py"
RETYPE = "alembic/versions/20261004_4a7e20790605_ledger_reasons_for_extend_and_dms.py"
REOPEN = "alembic/versions/20261004_e0a0c47fa4ff_price_reopen_and_extend_together.py"
DMS = "alembic/versions/20261004_134555ebf46f_price_private_messages.py"
PACKS = "alembic/versions/20261004_cc564bfd728e_packs_become_d099s_four.py"
CALLERS = "tests/modules/pricing/test_debit_callers.py"
T52_SELECTION = [
    "tests/modules/pricing",
    "tests/modules/wallet",
    "--ignore=tests/modules/wallet/test_concurrency.py",
    "tests/test_reference_data.py",
    "tests/test_migrations.py",
    "tests/test_schema.py",
]
NO_GENDER_CHECK = "    if user.gender not in (Gender.MALE, Gender.FEMALE):\n        raise PricingMisuse("

T52: list[Case] = [
    Case(
        id="t52-01-a-woman-priced",
        what="price_for: a woman pays the row's price",
        edits=[
            (
                PRICING,
                "    return credits if user.gender is Gender.MALE else 0\n",
                "    return credits\n",
            )
        ],
        expect=[
            "test_a_woman_pays_nothing_for_any_action",
            "test_a_woman_is_charged_nothing_and_no_row_is_written",
        ],
    ),
    Case(
        id="t52-02-a-missing-row-priced-0",
        what="price_for: a missing row priced 0, not a 500",
        edits=[
            (
                PRICING,
                '        raise PricingMisuse(f"{action} has no price: never 0 by default (T-5.2)")\n',
                "        return 0\n",
            )
        ],
        expect=["test_an_action_with_no_row_is_a_500_never_0"],
    ),
    Case(
        id="t52-03-an-inactive-row-priced",
        what="price_for: an inactive row priced like an active one",
        edits=[
            (
                PRICING,
                "    if not active:\n        raise AppError(",
                "    if False:\n        raise AppError(",
            )
        ],
        expect=[
            "test_an_inactive_action_is_not_allowed_for_anyone",
            "test_an_inactive_action_charges_nothing",
        ],
    ),
    Case(
        id="t52-04-no-gender-priced",
        what="price_for: a user with no gender priced (the check removed)",
        edits=[
            (PRICING, NO_GENDER_CHECK, "    if False:\n        raise PricingMisuse(")
        ],
        expect=[
            "test_a_user_with_no_gender_is_never_priced",
            "test_a_gender_nobody_has_named_is_never_priced",
        ],
    ),
    Case(
        id="t52-05-no-gender-check-a-blacklist",
        what="price_for: the gender check made a blacklist, `is None`",
        edits=[
            (
                PRICING,
                NO_GENDER_CHECK,
                "    if user.gender is None:\n        raise PricingMisuse(",
            )
        ],
        expect=["test_a_gender_nobody_has_named_is_never_priced"],
    ),
    Case(
        id="t52-06-a-cached-price",
        what="price_for: the row cached per action, missing a changed row",
        edits=[
            (
                PRICING,
                "class PricingMisuse(Exception):",
                "_CACHE: dict[LedgerReason, tuple[int, bool] | None] = {}\n\n\nclass PricingMisuse(Exception):",
            ),
            (
                PRICING,
                "    row = await repository.price_row(session, action.value)\n",
                "    if action not in _CACHE:\n        _CACHE[action] = await repository.price_row(session, action.value)\n    row = _CACHE[action]\n",
            ),
        ],
        expect=[
            "test_the_price_is_read_fresh_every_time",
            "test_a_man_is_charged_the_price_now",
        ],
    ),
    Case(
        id="t52-07-charge-debits-0",
        what="charge: debits whatever the price, 0 included",
        edits=[(PRICING, "    if price == 0:\n        return None\n", "")],
        expect=[
            "test_a_woman_is_charged_nothing_and_no_row_is_written",
            "test_a_price_of_0_debits_nothing",
        ],
    ),
    Case(
        id="t52-08-a-priced-action-with-no-reason",
        what="a data migration prices an action that is no ledger reason",
        edits=[
            (
                REOPEN,
                'PRICES = {"thread_reopen": 2, "thread_extend": 10}',
                'PRICES = {"thread_reopen": 2, "thread_extend": 10, "thread_boost": 10}',
            )
        ],
        expect=[
            "test_every_priced_action_is_a_ledger_reason",
            "test_the_debit_reasons_are_the_priced_actions_and_gift",
            "test_prices_are_public_and_exactly_the_active_actions",
            "test_the_rows_are_exactly_the_tested_actions",
        ],
    ),
    Case(
        id="t52-09-a-debit-reason-with-no-price",
        what="dm_message a debit reason with no price row",
        edits=[
            (
                DMS,
                'PRICES = {"dm_open": 8, "dm_message": 2}',
                'PRICES = {"dm_open": 8}',
            )
        ],
        expect=[
            "test_the_debit_reasons_are_the_priced_actions_and_gift",
            "test_prices_are_public_and_exactly_the_active_actions",
        ],
    ),
    Case(
        id="t52-10-the-reasons-cant-go-down",
        what="4a7e20790605's downgrade leaves the two values in the type",
        edits=[
            (
                RETYPE,
                "    _retype([label for label in _labels() if label not in ADDED])\n",
                "    pass\n",
            )
        ],
        expect=["test_the_reasons_go_down_and_up_and_keep_what_stood"],
    ),
    Case(
        id="t52-11-the-downgrade-drops-a-reason-in-use",
        what="4a7e20790605's downgrade no longer refuses a reason the ledger holds",
        edits=[
            (
                RETYPE,
                "    if used:\n        raise RuntimeError(",
                "    if False:\n        raise RuntimeError(",
            )
        ],
        expect=["test_the_reasons_refuse_to_go_down_once_the_ledger_holds_one"],
    ),
    Case(
        id="t52-12-the-rebuild-loses-a-check",
        what="the rebuild re-creates every CHECK on reason but ref_required",
        edits=[
            (
                RETYPE,
                "    for name, definition in checks:\n",
                '    for name, definition in [c for c in checks if "ref_required" not in c[0]]:\n',
            )
        ],
        expect=[
            "test_the_reasons_go_down_and_up_and_keep_what_stood",
            "test_each_reason_has_exactly_one_ref_type_in_the_database",
        ],
    ),
    Case(
        id="t52-13-a-data-migration-cant-go-down",
        what="the packs' downgrade does nothing",
        edits=[
            (
                PACKS,
                '    """Downgrade schema: D-005\'s ladder."""\n',
                '    """Downgrade schema: D-005\'s ladder."""\n    return\n',
            )
        ],
        expect=["test_t52_data_downgrades_restore_t114s_values"],
    ),
    Case(
        id="t52-14-extend-once-per-thread-in-the-database",
        what="the per-event index no longer leaves thread_extend out",
        edits=[
            (
                SHAPE_T52,
                'REPEATS = (*REPEATS_BEFORE, "thread_extend")',
                "REPEATS = REPEATS_BEFORE",
            )
        ],
        expect=[
            "test_one_entry_per_event_except_the_reasons_that_repeat",
            "test_extend_can_be_bought_again_for_one_thread",
        ],
    ),
    Case(
        id="t52-15-extend-once-per-thread-in-the-rules",
        what="RULES: thread_extend no longer repeats (model and service)",
        edits=[
            (
                RULES,
                "    LedgerReason.THREAD_EXTEND: Rule(DEBIT, RefType.THREAD, caller_names_event=True),",
                "    LedgerReason.THREAD_EXTEND: Rule(DEBIT, RefType.THREAD),",
            )
        ],
        expect=[
            "test_one_entry_per_event_except_the_reasons_that_repeat",
            "test_extend_can_be_bought_again_for_one_thread",
        ],
    ),
    Case(
        id="t52-16-dm-message-refs-a-thread",
        what="the database pins dm_message to `thread`, not `message`",
        edits=[
            (
                SHAPE_T52,
                '    ("dm_message", "message"),',
                '    ("dm_message", "thread"),',
            )
        ],
        expect=["test_each_reason_has_exactly_one_ref_type_in_the_database"],
    ),
    Case(
        id="t52-17-direction-misses-a-new-reason",
        what="the direction CHECK leaves dm_message out of the debits",
        edits=[
            (
                SHAPE_T52,
                'DEBITS = (*DEBITS_BEFORE, "thread_extend", "dm_message")',
                'DEBITS = (*DEBITS_BEFORE, "thread_extend")',
            )
        ],
        expect=["test_each_reason_has_one_direction_in_the_database"],
    ),
    Case(
        id="t52-18-a-caller-nobody-named",
        what="app code reaches the debit outside charge()",
        edits=[
            (
                PRICING,
                "    return await repository.active_prices(session)\n",
                "    _ = wallet_service.debit\n    return await repository.active_prices(session)\n",
            )
        ],
        expect=["test_only_charge_reaches_the_debit"],
    ),
    Case(
        id="t52-19-the-scan-blind-to-attributes",
        what="the callers' scan ignores `.debit` attributes",
        edits=[
            (
                CALLERS,
                "    if isinstance(node, ast.Attribute) and node.attr == target:\n        return True\n",
                "    if False:\n        return True\n",
            )
        ],
        expect=[
            "test_only_charge_reaches_the_debit",
            "test_a_caller_nobody_has_named_is_found",
            "test_the_allowlist_names_a_function_not_a_file",
        ],
    ),
    Case(
        id="t52-20-the-allowlist-by-file",
        what="the callers' scan records a file, not the function in it",
        edits=[
            (
                CALLERS,
                "                (rel, scope)\n",
                '                (rel, "charge")\n',
            )
        ],
        expect=["test_the_allowlist_names_a_function_not_a_file"],
    ),
    Case(
        id="t52-21-prices-list-an-inactive-action",
        what="GET /prices lists inactive actions too",
        edits=[(PRICING_REPO, "        .where(ActionPrice.active.is_(True))\n", "")],
        expect=["test_an_inactive_action_is_left_out_and_gifts_are_never_in"],
    ),
    Case(
        id="t52-22-price-for-outside-a-transaction",
        what="price_for reads outside its caller's transaction",
        edits=[
            (
                PRICING,
                "    if not session.in_transaction():\n        raise PricingMisuse(",
                "    if False:\n        raise PricingMisuse(",
            )
        ],
        expect=["test_price_for_refuses_outside_a_transaction"],
    ),
]


# --- P-142: one run's fifty connections at a time, on the whole server -----------

P142: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="p142-fifty-turn",
            what="P-142: a fifty-connection phase takes the server's turn without waiting",
            edits=[
                (
                    CONCURRENCY,
                    'text("select pg_try_advisory_lock(:lock, 0)"), {"lock": FIFTY_LOCK}',
                    'text("select true"), {"lock": FIFTY_LOCK}',
                )
            ],
            expect=["test_a_fifty_waits_while_another_run_holds_the_turn"],
        ),
        [CONCURRENCY],
    ),
]

# --- P-143: make hooks only from the clone's main checkout -----------------------

HOOKS_TEST = "tests/test_require_main_checkout.py"
P143: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="p143-a-worktree-allowed",
            what="P-143: the check lets a linked worktree through",
            edits=[
                (
                    "../scripts/require-main-checkout",
                    'if [[ "$git_dir" != "$common_dir" ]]; then\n',
                    "if false; then\n",
                )
            ],
            expect=["test_make_hooks_is_refused_outside_the_main_checkout"],
        ),
        [HOOKS_TEST],
    ),
    (
        Case(
            id="p143-check-not-run",
            what="P-143: make hooks no longer runs the check",
            edits=[("../Makefile", "\t@scripts/require-main-checkout\n", "")],
            expect=["test_the_check_is_the_first_thing_make_hooks_runs"],
        ),
        [HOOKS_TEST],
    ),
]

# --- P-38: Phagwara's areas replace Bengaluru's, and the seed's scatter fits them --

P38_SELECTION = ["tests/test_reference_data.py", "tests/seed/test_seed.py"]
AREAS = "alembic/versions/20261005_bc589ac265c2_phagwara_areas.py"
SEED_DATA = "seed/data.py"
COUNT = "        .where(_these(city, names))\n    )\n    if in_use:\n"
REFUSES_IN_USE = "test_the_migration_refuses_to_remove_an_area_in_use"
LAUNCH_CITY = "test_areas_are_in_the_launch_city"
UNDER_HALF = "test_the_scatter_stays_under_half_the_closest_gap"
INSIDE = "test_each_profile_sits_on_its_scatters_grid_point_inside_its_area"

P38: list[Case] = [
    Case(
        id="p38-01-count-ignored",
        what="the migration removes areas whatever its count says",
        edits=[(AREAS, "    if in_use:\n", "    if False:\n")],
        expect=[f"{REFUSES_IN_USE}[upgrade]", f"{REFUSES_IN_USE}[downgrade]"],
    ),
    Case(
        id="p38-02-count-every-area",
        what="the count is of every profile with an area, not the areas removed",
        edits=[(AREAS, COUNT, "        .where(sa.true())\n    )\n    if in_use:\n")],
        expect=["test_the_migration_counts_only_the_areas_it_removes"],
    ),
    Case(
        id="p38-03-count-wrong-city",
        what="the count always looks at Phagwara's areas, so the upgrade counts none",
        edits=[
            (
                AREAS,
                COUNT,
                "        .where(_these(CITY, names))\n    )\n    if in_use:\n",
            )
        ],
        expect=[f"{REFUSES_IN_USE}[upgrade]"],
    ),
    Case(
        id="p38-04-message-without-the-fix",
        what="the refusal says what it found but not what to do",
        edits=[
            (
                AREAS,
                'so it stopped before changing anything. {fix}"',
                'so it stopped before changing anything."',
            )
        ],
        expect=[f"{REFUSES_IN_USE}[upgrade]", f"{REFUSES_IN_USE}[downgrade]"],
    ),
    Case(
        id="p38-05-downgrade-short-of-40",
        what="the downgrade puts 39 of Bengaluru's areas back",
        edits=[
            (
                AREAS,
                "        (OLD_CITY, OLD_AREAS),\n",
                "        (OLD_CITY, OLD_AREAS[1:]),\n",
            )
        ],
        expect=["test_the_downgrade_puts_bengalurus_40_back"],
    ),
    Case(
        id="p38-06-bengaluru-area-left-behind",
        what="the upgrade leaves Koramangala in place",
        edits=[
            (
                AREAS,
                "        (OLD_CITY, [name for name, _, _ in OLD_AREAS]),\n",
                "        (OLD_CITY, [name for name, _, _ in OLD_AREAS[1:]]),\n",
            )
        ],
        expect=[LAUNCH_CITY, "test_the_areas_are_phagwaras_list"],
    ),
    Case(
        id="p38-07-lat-lng-swapped",
        what="one centroid's latitude and longitude swapped",
        edits=[(AREAS, '"LPU", 31.2533, 75.7033,', '"LPU", 75.7033, 31.2533,')],
        expect=[LAUNCH_CITY],
    ),
    Case(
        id="p38-08-scatter-back-to-750",
        what="Bengaluru's 750 m scatter carried across to Phagwara",
        edits=[(SEED, "SCATTER_RADIUS_M = 250\n", "SCATTER_RADIUS_M = 750\n")],
        expect=[UNDER_HALF, INSIDE],
    ),
    Case(
        id="p38-09-scatter-just-over-half",
        what="a scatter of 256 m, just over half the closest gap (510.16 m)",
        edits=[(SEED, "SCATTER_RADIUS_M = 250\n", "SCATTER_RADIUS_M = 256\n")],
        expect=[UNDER_HALF],
    ),
    Case(
        id="p38-10-seed-still-in-bengaluru",
        what="the seed looks for its areas in Bengaluru",
        edits=[(SEED, 'AREA_CITY = "Phagwara"\n', 'AREA_CITY = "Bengaluru"\n')],
        expect=[UNDER_HALF, INSIDE],
    ),
    # p38-11 (Ananya back with three others, two of them 89 m apart) went with
    # D-490: on the 1 km grid profiles share points by design, so the seed no
    # longer keeps everyone 100 m apart, and nothing is left for it to break.
]

# --- T-4.5: selfie face matching, the wake, the review, the seed's selfies ----------
# Each case's selection is the files that must catch it.

VER = "tests/modules/verification"
RULES45 = "app/modules/verification/rules.py"
SERVICE45 = "app/modules/verification/service.py"
REPO45 = "app/modules/verification/repository.py"
FACEMATCH = "app/core/providers/facematch.py"
FACE_TESTS = "tests/core/test_facematch.py"
WORKER_TESTS = "tests/workers/test_worker.py"
WAKE_TESTS = "tests/workers/test_wake.py"
JOB_TESTS = "tests/workers/test_verify_selfie.py"
UPLOAD_TESTS = "tests/modules/photos/test_upload.py"
PHOTOS_SERVICE = "app/modules/photos/service.py"
WAKE = "app/workers/wake.py"

T45: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t45-01-the-threshold-itself-refused",
            what="at exactly the threshold, refused (> for >=)",
            edits=[
                (
                    RULES45,
                    "    if best >= MATCH_THRESHOLD:\n",
                    "    if best > MATCH_THRESHOLD:\n",
                )
            ],
            expect=["test_at_the_threshold_it_matches_and_records_the_numbers"],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-02-the-threshold-lowered",
            what="the threshold lowered from D-260's 0.363 to 0.30",
            edits=[
                (
                    RULES45,
                    "MATCH_THRESHOLD: Final = 0.363\n",
                    "MATCH_THRESHOLD: Final = 0.30\n",
                )
            ],
            expect=[
                "test_the_threshold_is_sface_s_published_lfw_number",
                "test_just_below_the_threshold_it_doesnt",
            ],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-03-the-first-photo-counts-not-the-best",
            what="the first photo's similarity counted, not the best",
            edits=[
                (
                    FACEMATCH,
                    "        return max(found) if found else None\n",
                    "        return found[0] if found else None\n",
                )
            ],
            # The selfie has one reference since T-4.12 (D-391), so only the
            # provider's own test sees the best counted among several.
            expect=["test_each_photo_is_compared_in_order_and_the_best_counts"],
        ),
        [FACE_TESTS],
    ),
    # t45-04, "photos compared from the private upload, not the public copy",
    # left with T-4.12: the selfie's one reference is the face photo, which
    # has no public copy; its private copy is the scored bytes written back
    # (D-092). The badge's comparison reads the public copy: `t412-` holds it.
    (
        Case(
            id="t45-05-the-original-selfie-kept",
            what="the re-encoded selfie not written back: the upload, location and all, kept",
            edits=[
                (
                    SERVICE45,
                    '    await _stored(storage.put_bytes(private, selfie.raw_key, clean.data, "image/jpeg"))\n',
                    "",
                )
            ],
            expect=["test_a_located_selfie_is_stored_with_no_location"],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-06-the-original-selfie-compared",
            what="the upload's own bytes compared, not the re-encoded ones",
            edits=[
                (SERVICE45, "    del data\n", ""),
                (
                    SERVICE45,
                    "    match = await facematch.compare(clean.data, [ref for _, ref in found])\n",
                    "    match = await facematch.compare(data, [ref for _, ref in found])\n",
                ),
            ],
            expect=["test_a_located_selfie_is_stored_with_no_location"],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-07-a-matched-selfie-published",
            what="an approved selfie given a public key",
            edits=[
                (
                    SERVICE45,
                    "            user.is_verified = True\n",
                    '            user.is_verified = True\n            photo.public_key = f"p/{photo.id}.jpg"\n',
                )
            ],
            expect=["test_a_matched_selfie_is_never_public_and_never_shown"],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-08-a-match-never-marks-the-user",
            what="an approved selfie leaves is_verified false",
            edits=[(SERVICE45, "            user.is_verified = True\n", "")],
            expect=[
                "test_at_the_threshold_it_matches_and_records_the_numbers",
                "test_a_wake_and_the_job_at_once_decide_it_once",
            ],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-09-many-faces-allowed",
            what="a selfie with several faces not refused as such",
            edits=[
                (
                    RULES45,
                    "    if match.faces_in_selfie > 1:\n        return MANY_FACES\n",
                    "",
                )
            ],
            expect=[
                "test_the_selfie_must_hold_exactly_one_face[2-many_faces]",
                "test_the_selfie_must_hold_exactly_one_face[3-many_faces]",
                "test_a_selfie_without_exactly_one_face_compares_nothing[three_people-3]",
            ],
        ),
        [VER, FACE_TESTS],
    ),
    (
        Case(
            id="t45-10-decided-again-once-decided",
            what="the decision written without re-reading that it's still pending",
            edits=[
                (
                    SERVICE45,
                    (
                        "        if locked.status is not ReviewStatus.PENDING:\n"
                        '            return f"{locked.status.value} while it was compared: left as it is"\n'
                    ),
                    "",
                )
            ],
            expect=["test_a_wake_and_the_job_at_once_decide_it_once"],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-11-the-decision-unlocked",
            what="the user's and the verification's row locks removed from the decision",
            edits=[
                (
                    SERVICE45,
                    "            user = await users_service.locked_user(session, verification.user_id)\n",
                    "            user = await users_service.get_user(session, verification.user_id)\n",
                ),
                (
                    REPO45,
                    (
                        "        .with_for_update()\n"
                        "        .execution_options(populate_existing=True)\n"
                        "    )\n"
                        "    return verification\n"
                    ),
                    (
                        "        .execution_options(populate_existing=True)\n"
                        "    )\n"
                        "    return verification\n"
                    ),
                ),
            ],
            expect=["test_a_wake_and_the_job_at_once_decide_it_once"],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-12-every-reason-named-to-the-owner",
            what="a reason off D-263's list reaches the owner by name",
            edits=[
                (
                    RULES45,
                    "    if reason is None or reason in OWNER_REASONS:\n",
                    "    if True:\n",
                )
            ],
            expect=[
                "test_a_rejection_names_its_reason_only_from_the_list[something_added_later-other]"
            ],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-13-no-wake",
            what="the submit never wakes the worker (D-261)",
            edits=[
                (
                    SERVICE45,
                    "    await queue.wake(VERIFY_SELFIE, str(verification.id))\n",
                    "",
                )
            ],
            expect=[
                "test_it_queues_the_comparison_then_wakes_the_worker_after_the_commit",
                "test_a_submitted_selfie_is_decided_by_the_wake_and_the_job_finds_it_done",
            ],
        ),
        [VER, WORKER_TESTS],
    ),
    (
        Case(
            id="t45-14-the-wake-before-the-commit",
            what="the wake sent inside the submit's transaction",
            edits=[
                (
                    SERVICE45,
                    (
                        "        out = await _out(session, verification)\n"
                        "    await queue.wake(VERIFY_SELFIE, str(verification.id))\n"
                    ),
                    (
                        "        out = await _out(session, verification)\n"
                        "        await queue.wake(VERIFY_SELFIE, str(verification.id))\n"
                    ),
                )
            ],
            # Only the in-transaction check catches this. The end-to-end test
            # stays green: the commit lands microseconds after the publish,
            # long before the listener's database read (seen, 5 October 2026).
            expect=[
                "test_it_queues_the_comparison_then_wakes_the_worker_after_the_commit"
            ],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-15-a-model-not-hash-checked",
            what="a model's SHA-256 not checked (D-088)",
            edits=[
                (
                    "app/core/facemodels.py",
                    (
                        "    if _sha256(path) != model.sha256:\n"
                        '        return "not D-088\'s SHA-256"\n'
                    ),
                    "",
                )
            ],
            expect=[
                "test_sface_without_d088s_exact_models_is_refused_naming_them[altered",
                "test_load_refuses_a_model_that_isnt_d088s",
            ],
        ),
        [FACE_TESTS, WORKER_TESTS],
    ),
    (
        Case(
            id="t45-16-the-api-loads-opencv",
            what="OpenCV imported where the API imports the provider",
            edits=[
                (
                    FACEMATCH,
                    "from PIL import Image\n",
                    "import cv2  # noqa: F401\nfrom PIL import Image\n",
                )
            ],
            expect=["test_the_api_never_loads_opencv"],
        ),
        [FACE_TESTS],
    ),
    (
        Case(
            id="t45-17-opencv-decodes-the-file",
            what="OpenCV's decoder reading the image bytes instead of Pillow's pixels",
            edits=[
                (
                    FACEMATCH,
                    (
                        '    with Image.open(io.BytesIO(jpeg), formats=["JPEG"]) as decoded:\n'
                        '        rgb = decoded.convert("RGB")\n'
                        "    return np.ascontiguousarray(np.asarray(rgb)[:, :, ::-1])\n"
                    ),
                    (
                        "    import cv2\n\n"
                        "    decoded: np.ndarray = cv2.imdecode(\n"
                        "        np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR\n"
                        "    )\n"
                        "    return decoded\n"
                    ),
                )
            ],
            expect=["test_opencv_never_parses_an_image_file"],
        ),
        [FACE_TESTS],
    ),
    (
        Case(
            id="t45-18-a-sixth-selfie-a-day",
            what="six selfies a day, not five (off by one)",
            edits=[
                (
                    SERVICE45,
                    "    if len(counted) < rules.ATTEMPTS:\n",
                    "    if len(counted) <= rules.ATTEMPTS:\n",
                )
            ],
            expect=[
                "test_five_selfies_in_24_hours_and_the_sixth_waits",
                "test_the_sixth_selfie_in_a_day_is_refused_at_submit_too",
            ],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-19-attempts-never-leave-the-window",
            what="every selfie ever sent counted, not the last 24 hours'",
            edits=[(REPO45, "            Verification.created_at > since,\n", "")],
            expect=["test_selfies_sent_over_24_hours_ago_no_longer_count"],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-20-a-refusal-leaves-the-verification",
            what="an under-18 refusal leaves the verification rows (D-078)",
            edits=[
                (
                    "app/modules/users/repository.py",
                    '    Attached(Verification, ("user_id",)),\n',
                    "",
                )
            ],
            expect=["test_a_refusals_selfie_and_its_verification_go_with_it"],
        ),
        ["tests/modules/users/test_dob_gender.py"],
    ),
    (
        Case(
            id="t45-21-an-unsent-selfie-blocks-the-next",
            what="a selfie never sent holds the selfie place forever",
            edits=[
                (
                    PHOTOS_SERVICE,
                    (
                        "        if kind is PhotoKind.SELFIE:\n"
                        "            live, replaced = await _replace_unsent_selfies(session, live)\n"
                    ),
                    "",
                )
            ],
            expect=["test_a_selfie_never_sent_is_replaced_by_the_next"],
        ),
        [UPLOAD_TESTS],
    ),
    (
        Case(
            id="t45-22-a-selfie-being-compared-replaced",
            what="a selfie being compared replaced by a new upload",
            edits=[
                (
                    PHOTOS_SERVICE,
                    "    replaced = [p for p in waiting if p.id not in sent]\n",
                    "    replaced = list(waiting)\n",
                )
            ],
            expect=["test_a_selfie_being_compared_holds_its_place"],
        ),
        [UPLOAD_TESTS],
    ),
    (
        Case(
            id="t45-23-the-seed-adds-a-second-selfie",
            what="the seed adds a second selfie on a re-run",
            edits=[
                ("seed/run.py", "    if approved is not None:\n        return\n", "")
            ],
            expect=["test_a_second_run_adds_no_photo"],
        ),
        ["tests/seed/test_seed.py"],
    ),
    (
        Case(
            id="t45-24-the-review-shows-only-the-near",
            what="the review lists only results near the threshold (the refuted design, D-260)",
            edits=[
                ("app/tools/selfie_review.py", "    if args.near:\n", "    if True:\n")
            ],
            expect=["test_every_decision_is_listed_far_from_the_threshold_too"],
        ),
        ["tests/tools/test_selfie_review.py"],
    ),
    (
        Case(
            id="t45-25-reconnects-never-back-off-to-a-cap",
            what="the listener's backoff uncapped",
            edits=[
                (
                    WAKE,
                    "                backoff = min(backoff * 2, self._max_backoff_s)\n",
                    "                backoff = backoff * 2\n",
                )
            ],
            expect=[
                "test_a_connection_that_never_holds_backs_off_to_once_in_5_minutes"
            ],
        ),
        [WAKE_TESTS],
    ),
    (
        Case(
            id="t45-26-backoff-reset-on-every-drop",
            what="the backoff restarts from a second after any drop, held or not",
            edits=[(WAKE, "                if held:\n", "                if True:\n")],
            expect=[
                "test_it_starts_again_from_a_second_only_after_a_connection_held[dropping-early-keeps-backing-off]"
            ],
        ),
        [WAKE_TESTS],
    ),
    (
        Case(
            id="t45-27-a-failing-comparison-stops-the-ear",
            what="a comparison that fails takes the listener's connection with it",
            edits=[
                (
                    WAKE,
                    (
                        "        try:\n"
                        "            await self._handle(verification_id)\n"
                        "        except Exception as error:  # noqa: BLE001 — the queued job still runs\n"
                        "            log.info(\n"
                        '                "wake.left_to_the_queue",\n'
                        "                why=type(error).__name__,\n"
                        "                **{self._id_name: str(verification_id)},\n"
                        "            )\n"
                    ),
                    "        await self._handle(verification_id)\n",
                )
            ],
            expect=["test_a_failing_comparison_never_stops_the_listening"],
        ),
        [WAKE_TESTS],
    ),
    (
        Case(
            id="t45-28-the-last-try-leaves-her-waiting",
            what="the job's last try gives up without deciding, so she waits on nothing",
            edits=[
                (
                    "app/workers/tasks/verify_selfie.py",
                    "    if final is None:\n",
                    "    if True:\n",
                )
            ],
            expect=[
                "test_the_last_failure_is_unavailable_so_she_can_start_again",
                "test_a_face_photo_still_waiting_at_the_last_try_is_no_photos",
            ],
        ),
        [JOB_TESTS],
    ),
    (
        Case(
            id="t45-29-a-refused-users-selfie-left-behind",
            what="a selfie written back after its user was refused is left in storage",
            edits=[
                (
                    SERVICE45,
                    "            await to.storage.delete(to.settings.R2_BUCKET_PRIVATE, selfie.raw_key)\n",
                    "",
                )
            ],
            expect=["test_a_user_refused_while_it_was_compared_leaves_no_selfie"],
        ),
        [VER],
    ),
    (
        Case(
            id="t45-30-the-worker-starts-without-the-models",
            what="the worker's refusal without D-088's models removed",
            edits=[
                (
                    "app/workers/main.py",
                    '    if settings.FACEMATCH_PROVIDER == "sface":\n',
                    '    if settings.FACEMATCH_PROVIDER == "never":\n',
                )
            ],
            expect=[
                "test_sface_without_d088s_exact_models_is_refused_naming_them[missing",
                "test_sface_without_d088s_exact_models_is_refused_naming_them[altered",
                "test_sface_without_d088s_exact_models_is_refused_naming_them[cut short",
            ],
        ),
        [WORKER_TESTS],
    ),
    (
        Case(
            id="t45-31-an-altered-download-kept",
            what="a downloaded model kept although it isn't D-088's",
            edits=[
                (
                    "app/core/facemodels.py",
                    (
                        "            if wrong:\n"
                        "                partial.unlink()\n"
                        '                raise ValueError(f"{model.name} from {model.url}: {wrong}")\n'
                    ),
                    "",
                )
            ],
            expect=["test_fetch_refuses_an_altered_download_and_leaves_nothing"],
        ),
        [FACE_TESTS],
    ),
    (
        Case(
            id="t45-32-a-failed-wake-fails-the-request",
            what="a wake that fails raises, after the submit has committed",
            edits=[
                (
                    "app/core/queue.py",
                    (
                        "        try:\n"
                        "            await asyncio.wait_for(\n"
                        "                self._arq.publish(wake_channel(job), value), WAKE_TIMEOUT_S\n"
                        "            )\n"
                        "        except Exception as error:  # noqa: BLE001 — the queued job still runs\n"
                        '            log.warning("queue.wake_failed", job=job, error=type(error).__name__)\n'
                    ),
                    (
                        "        await asyncio.wait_for(\n"
                        "            self._arq.publish(wake_channel(job), value), WAKE_TIMEOUT_S\n"
                        "        )\n"
                    ),
                )
            ],
            expect=[
                "test_a_wake_that_fails_is_logged_and_never_raises",
                "test_a_wake_that_hangs_gives_up_after_a_second",
            ],
        ),
        ["tests/core/test_queue.py"],
    ),
]

# --- T-4.8: finishing onboarding, D-310's trigger, the seed's completeness ----------

ONBOARDING = "tests/modules/onboarding"
RULES48 = "app/modules/onboarding/rules.py"
SERVICE48 = "app/modules/onboarding/service.py"
REPO48 = "app/modules/onboarding/repository.py"
MIGRATION48 = "alembic/versions/20261005_15a9b138750b_done_needs_a_matched_selfie.py"
EACH = "test_each_requirement_is_refused_by_name"


def requirement_dropped(key: str, check: str, *expect: str) -> Case:
    """One requirement always met, as a careless edit to the rules leaves it."""
    return Case(
        id=f"t48-{key.replace('_', '-')}-not-required",
        what=f"{key} not required",
        edits=[(RULES48, f'        "{key}": {check},\n', f'        "{key}": True,\n')],
        expect=[f"{EACH}[{case}]" for case in expect],
    )


T48: list[tuple[Case, list[str]]] = [
    (
        requirement_dropped("seeking", "facts.seeking is not None", "no seeking"),
        [ONBOARDING],
    ),
    (
        requirement_dropped(
            "intents",
            "INTENTS_MIN <= facts.intents <= INTENTS_MAX",
            "no intent",
            "four intents",
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-more-than-three-intents",
            what="more than three intents taken (D-041)",
            edits=[
                (
                    RULES48,
                    '        "intents": INTENTS_MIN <= facts.intents <= INTENTS_MAX,\n',
                    '        "intents": INTENTS_MIN <= facts.intents,\n',
                )
            ],
            expect=[f"{EACH}[four intents]"],
        ),
        [ONBOARDING],
    ),
    (
        requirement_dropped("first_name", "bool(facts.first_name)", "no first name"),
        [ONBOARDING],
    ),
    (
        requirement_dropped("hometown", "bool(facts.hometown)", "no hometown"),
        [ONBOARDING],
    ),
    (requirement_dropped("city", "bool(facts.city)", "no city"), [ONBOARDING]),
    (requirement_dropped("location", "facts.located", "no location"), [ONBOARDING]),
    (
        requirement_dropped("username", "bool(facts.username)", "no username"),
        [ONBOARDING],
    ),
    (requirement_dropped("about", "bool(facts.about)", "no about"), [ONBOARDING]),
    # The photo requirement's case left with the requirement (D-392, T-4.12).
    (
        requirement_dropped(
            "interests", "facts.interests == INTERESTS_PER_PROFILE", "four interests"
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-a-removed-photo-counted",
            what="a photo its owner removed counted: its public_key stays",
            edits=[
                (REPO48, "            Photo.status == ReviewStatus.APPROVED,\n", "")
            ],
            expect=[
                f"{EACH}[a photo its owner removed]",
                "test_completeness_counts_approved_public_photos_only",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-any-approved-photo-counted",
            what="a private photo or a selfie counted",
            edits=[
                (
                    REPO48,
                    "            Photo.kind == PhotoKind.PUBLIC,\n            Photo.status == ReviewStatus.APPROVED,\n            Photo.public_key.is_not(None),\n",
                    "            Photo.status == ReviewStatus.APPROVED,\n",
                )
            ],
            expect=[
                f"{EACH}[a private photo only]",
                f"{EACH}[a selfie only]",
                "test_completeness_counts_approved_public_photos_only",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-a-woman-finishes-unmatched",
            what="the service's match check removed (the trigger alone stops her)",
            edits=[
                (
                    SERVICE48,
                    "        if rules.needs_a_match(user.gender) and not user.is_verified:\n",
                    "        if False:\n",
                )
            ],
            expect=[
                "test_a_woman_without_a_match_is_refused",
                "test_no_gender_needs_a_match_too",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-the-allowlist-a-blacklist",
            what="women named instead of men: no gender finishes unmatched",
            edits=[
                (
                    RULES48,
                    "    return gender not in MAY_FINISH_UNMATCHED\n",
                    "    return gender is Gender.FEMALE\n",
                )
            ],
            expect=[
                "test_no_gender_needs_a_match_too",
                "test_only_a_man_finishes_without_a_match[no gender]",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-match-checked-before-the-profile",
            what="the selfie refused before what's missing is named",
            edits=[
                (
                    SERVICE48,
                    '        missing = rules.missing(facts)\n        if missing:\n            raise AppError(\n                "PROFILE_INCOMPLETE",\n',
                    '        missing = rules.missing(facts)\n        if rules.needs_a_match(user.gender) and not user.is_verified:\n            raise AppError("VERIFICATION_REQUIRED", "", status=403)\n        if missing:\n            raise AppError(\n                "PROFILE_INCOMPLETE",\n',
                )
            ],
            expect=["test_a_profile_short_of_something_is_told_that_before_the_selfie"],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-finished-from-any-step",
            what="D-068's step rule removed: a step before selfie finishes",
            edits=[
                (
                    SERVICE48,
                    "        if not users_service.at_step(user, OnboardingStep.SELFIE):\n",
                    "        if user.onboarding_step is OnboardingStep.DONE:\n",
                )
            ],
            expect=["test_before_the_selfie_step_is_onboarding_incomplete"],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-done-checked-again",
            what="a finished profile checked again, and refused",
            edits=[
                (
                    SERVICE48,
                    "        if not users_service.at_step(user, OnboardingStep.SELFIE):\n            return await users_service.me(session, user)\n",
                    "        users_service.at_step(user, OnboardingStep.SELFIE)\n",
                )
            ],
            expect=["test_once_done_it_changes_nothing_and_checks_nothing"],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-the-row-not-locked",
            what="the user's row read, not locked, before the facts",
            edits=[
                (
                    SERVICE48,
                    "        user = await users_service.locked_user(session, user.id)\n        if not users_service.at_step(user, OnboardingStep.SELFIE):\n",
                    "        user = await users_service.get_user(session, user.id)\n        if not users_service.at_step(user, OnboardingStep.SELFIE):\n",
                )
            ],
            expect=["test_finishing_waits_for_the_photos_decision"],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-completeness-not-set",
            what="the step moved, completeness left at signup's 0",
            edits=[
                (
                    SERVICE48,
                    "        profile.completeness = rules.completeness(facts.approved_photos)\n",
                    "",
                )
            ],
            expect=[
                "test_a_man_finishes_without_a_selfie",
                "test_completeness_counts_approved_public_photos_only",
                "test_finishing_waits_for_the_photos_decision",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-trigger-removed",
            what="D-310's trigger never created",
            edits=[(MIGRATION48, "    op.execute(sa.text(TRIGGER))\n", "")],
            expect=[
                "test_only_a_man_moves_to_done_unmatched",
                "test_a_row_written_as_done_is_held_to_the_same_rule",
                "test_the_app_is_refused_by_the_trigger_itself",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-trigger-a-blacklist",
            what="the trigger names women instead of men: no gender passes",
            edits=[
                (
                    MIGRATION48,
                    "    if new.gender is distinct from 'male' and not new.is_verified then\n",
                    "    if new.gender = 'female' and not new.is_verified then\n",
                )
            ],
            expect=["test_only_a_man_moves_to_done_unmatched"],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-trigger-on-update-only",
            what="a row inserted as done not checked",
            edits=[
                (
                    MIGRATION48,
                    '    "before insert or update of onboarding_step on users "\n',
                    '    "before update of onboarding_step on users "\n',
                )
            ],
            expect=["test_a_row_written_as_done_is_held_to_the_same_rule"],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-trigger-decides-p161",
            what="a row already done checked too, deciding P-161 and P-163",
            edits=[
                (
                    MIGRATION48,
                    "    if tg_op = 'UPDATE' and old.onboarding_step = 'done' then\n        return new;\n    end if;\n",
                    "",
                )
            ],
            expect=["test_a_row_already_done_is_left_to_p161_and_p163"],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-migration-precheck",
            what="the upgrade guards a woman already done unmatched",
            edits=[
                (
                    MIGRATION48,
                    "    op.execute(sa.text(REQUIRE_NONE_DONE_WITHOUT_A_MATCH))\n",
                    "",
                )
            ],
            expect=[
                "test_the_migration_refuses_to_guard_a_woman_already_done_unmatched"
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t48-deploy-readback-skips-it",
            what="the deploy's readback doesn't ask for D-310's trigger",
            edits=[
                (
                    "../scripts/migrate-with-url",
                    '    ("users", "users_done_needs_a_match"),\n',
                    "",
                )
            ],
            expect=[
                "test_an_empty_database_is_migrated_and_read_back",
                "test_a_head_stamped_without_its_migration_is_refused",
                "test_a_trigger_that_refuses_nothing_is_refused[",
            ],
        ),
        ["tests/test_migrate_with_url.py"],
    ),
    (
        Case(
            id="t48-seed-completeness-left-0",
            what="the seed's finished profiles left at signup's 0",
            edits=[
                (
                    "seed/run.py",
                    "            await _completeness(session, person, user_ids[person.key], report)\n",
                    "            pass\n",
                )
            ],
            expect=["test_every_finished_profile_could_have_finished"],
        ),
        ["tests/seed/test_seed.py"],
    ),
]

# --- T-4.11: D-381's bench-only tools, and the probe's faces guard ------------

T411_SELECTION = ["tests/bench"]
FACES411 = "bench/liveness/run.py"
FACES_TESTS = "tests/bench/liveness/test_faces.py::"
T411: list[Case] = [
    Case(
        id="t411-01-torch-in-the-lock",
        what="torch locked, so `uv sync --locked` puts it in the API image",
        edits=[
            (
                "uv.lock",
                '\n[[package]]\nname = "aioboto3"\n',
                (
                    '\n[[package]]\nname = "torch"\nversion = "2.14.1"\n'
                    'source = { registry = "https://pypi.org/simple" }\n'
                    '\n[[package]]\nname = "aioboto3"\n'
                ),
            )
        ],
        expect=["test_the_lock_holds_no_bench_only_package"],
    ),
    Case(
        id="t411-02-a-variant-in-the-lock",
        what="onnxruntime-gpu locked: a variant's name, not the exact one",
        edits=[
            (
                "uv.lock",
                '\n[[package]]\nname = "alembic"\n',
                (
                    '\n[[package]]\nname = "onnxruntime-gpu"\nversion = "1.30.0"\n'
                    'source = { registry = "https://pypi.org/simple" }\n'
                    '\n[[package]]\nname = "alembic"\n'
                ),
            )
        ],
        expect=["test_the_lock_holds_no_bench_only_package"],
    ),
    Case(
        id="t411-03-the-api-image-installs-torch",
        what="a RUN in the API's Dockerfile installs torch beside the lock",
        edits=[
            (
                "Dockerfile",
                "RUN uv sync --locked --no-dev\n",
                "RUN uv sync --locked --no-dev\nRUN uv pip install torch\n",
            )
        ],
        expect=["test_the_api_image_installs_only_the_lock"],
    ),
    Case(
        id="t411-04-the-bench-in-the-image",
        what="api/.dockerignore no longer keeps the bench out of the image",
        edits=[
            (
                ".dockerignore",
                "# no /app/bench, and neither of them.\nbench\n",
                "# no /app/bench, and neither of them.\n",
            )
        ],
        expect=["test_the_bench_never_enters_the_api_image"],
    ),
    Case(
        id="t411-05-the-faces-guard-off",
        what="a faces directory inside the repository is read",
        edits=[
            (
                FACES411,
                "        if target.is_relative_to(root.resolve()):\n",
                "        if False:\n",
            )
        ],
        expect=[
            FACES_TESTS + "test_a_directory_inside_the_repository_is_refused",
            FACES_TESTS + "test_a_link_into_the_repository_is_refused",
            FACES_TESTS + "test_another_worktree_of_the_repository_is_refused",
            FACES_TESTS + "test_the_real_repository_is_asked",
            FACES_TESTS + "test_the_command_refuses_before_starting_anything",
        ],
    ),
    Case(
        id="t411-06-a-link-taken-at-its-word",
        what="a link judged by where it sits, not where it leads",
        edits=[
            (
                FACES411,
                "    target = chosen.resolve()\n",
                "    target = chosen.absolute()\n",
            )
        ],
        expect=[FACES_TESTS + "test_a_link_into_the_repository_is_refused"],
    ),
    Case(
        id="t411-07-only-this-checkout",
        what="the other worktrees of the repository forgotten",
        edits=[
            (
                FACES411,
                "    return [REPO, *worktrees(porcelain)]\n",
                "    return [REPO]\n",
            )
        ],
        expect=[FACES_TESTS + "test_another_worktree_of_the_repository_is_refused"],
    ),
    Case(
        id="t411-08-git-failing-opens-it",
        what="git unable to list the worktrees, and every directory read",
        edits=[(FACES411, "    if code != 0:\n", "    if False:\n")],
        expect=[FACES_TESTS + "test_if_git_cant_list_the_worktrees_only_the_fixtures"],
    ),
]


# --- T-4.12: the face photo, the badge, nobody needing a public photo (D-391 to D-393) --

PHOTOS412 = "app/modules/photos/service.py"
MODERATION412 = "app/modules/photos/moderation.py"
PHOTOS_REPO412 = "app/modules/photos/repository.py"
USERS_REPO412 = "app/modules/users/repository.py"
MIGRATION412 = (
    "alembic/versions/20261008_ed3028467a15_a_face_photo_for_the_selfie_check.py"
)
PHOTOS_TESTS412 = ["tests/modules/photos"]
BADGE_TESTS = ["tests/modules/verification/test_badge.py"]
MIGRATION_TESTS412 = [
    "tests/modules/photos/test_face_photo_migration.py",
    "tests/test_schema.py",
]

T412: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t412-01-no-face-back-on-public-photos",
            what="D-392: a public photo refused for showing no face",
            edits=[
                (
                    MODERATION412,
                    "    if kind is PhotoKind.VERIFICATION and not scores.minors:\n",
                    "    if kind is not PhotoKind.PRIVATE and not scores.minors:\n",
                )
            ],
            expect=[
                "test_no_face_for_the_face_photo_never_a_public_one[public-None]",
                "test_a_public_or_private_photo_needs_no_face[public]",
            ],
        ),
        PHOTOS_TESTS412,
    ),
    (
        Case(
            id="t412-02-no-face-off-the-face-photo",
            what="D-391: a face photo with no face approved, leaving the selfie to find out",
            edits=[
                (
                    MODERATION412,
                    "    if kind is PhotoKind.VERIFICATION and not scores.minors:\n",
                    "    if kind is PhotoKind.SELFIE and not scores.minors:\n",
                )
            ],
            expect=[
                "test_no_face_for_the_face_photo_never_a_public_one[verification-no_face]",
                "test_the_face_photo_needs_a_face_and_is_never_published",
            ],
        ),
        PHOTOS_TESTS412,
    ),
    (
        Case(
            id="t412-03-the-selfie-compared-with-the-public-photos-again",
            what="D-391: the selfie's references the shown photos, not the face photo",
            edits=[
                (
                    SERVICE45,
                    "            face = await repository.face_photo(session, verification.user_id)\n            references = [face] if face is not None else []\n",
                    "            references = await repository.shown_photos_with_a_face(\n                session, verification.user_id\n            )\n",
                )
            ],
            expect=[
                "test_the_selfie_is_compared_with_the_face_photo_alone",
                "test_with_no_face_photo_there_is_nothing_to_compare_with",
            ],
        ),
        [VER],
    ),
    (
        Case(
            id="t412-04-the-reference-read-from-the-public-bucket",
            what="the face photo read from the public bucket, where it never is",
            edits=[
                (
                    SERVICE45,
                    "            settings.R2_BUCKET_PRIVATE, photo.raw_key, MAX_UPLOAD_BYTES + 1\n",
                    "            settings.R2_BUCKET_PUBLIC, photo.raw_key, MAX_UPLOAD_BYTES + 1\n",
                )
            ],
            expect=[
                "test_it_compares_the_re_encoded_selfie_with_the_approved_face_photo_only",
                "test_at_the_threshold_it_matches_and_records_the_numbers",
            ],
        ),
        [VER],
    ),
    (
        Case(
            id="t412-05-the-face-photo-replaceable-after-the-match",
            what="point 4: a new face photo allowed once the selfie matched",
            edits=[
                (
                    PHOTOS412,
                    '    if user.is_verified:\n        raise AppError(\n            "NOT_ALLOWED", "Your face photo can\'t change once your selfie matched."\n        )\n',
                    "",
                )
            ],
            expect=[
                "test_the_face_photo_cant_change_once_the_selfie_matched",
                "test_the_face_photo_goes_until_the_selfie_matched",
            ],
        ),
        PHOTOS_TESTS412,
    ),
    (
        Case(
            id="t412-06-the-face-photo-replaceable-mid-comparison",
            what="point 4: a new face photo allowed while the worker compares the old",
            edits=[
                (
                    PHOTOS412,
                    '    if await verification_repository.selfie_being_compared(session, user.id):\n        raise AppError(\n            "NOT_ALLOWED", "Your face photo can\'t change while your selfie is compared."\n        )\n',
                    "",
                )
            ],
            expect=[
                "test_nor_while_a_selfie_is_being_compared_with_it",
                "test_the_face_photo_stays_while_the_selfie_is_compared",
            ],
        ),
        PHOTOS_TESTS412,
    ),
    (
        Case(
            id="t412-07-the-face-photo-listed-to-anyone",
            what="06-TESTING #14: the owner's list no longer the owner's",
            edits=[
                (
                    PHOTOS_REPO412,
                    "            Photo.user_id == user_id,\n            Photo.kind.in_(OWNERS_KINDS),\n            Photo.status != ReviewStatus.REJECTED,\n",
                    "            Photo.kind.in_(OWNERS_KINDS),\n            Photo.status != ReviewStatus.REJECTED,\n",
                )
            ],
            expect=["test_the_face_photo_is_its_owners_alone"],
        ),
        PHOTOS_TESTS412,
    ),
    (
        Case(
            id="t412-08-show-on-an-unapproved-face-photo",
            what="the toggle on before moderation approved the face photo",
            edits=[
                (
                    PHOTOS412,
                    '        if face.status is not ReviewStatus.APPROVED:\n            raise AppError("NOT_ALLOWED", "Your face photo hasn\'t been approved yet.")\n',
                    "",
                )
            ],
            expect=["test_show_needs_an_approved_face_photo"],
        ),
        PHOTOS_TESTS412,
    ),
    (
        Case(
            id="t412-09-show-approved-at-once-from-the-private-copy",
            what="the copy published without being scored (T-4.4's rule, P-79)",
            edits=[
                (
                    PHOTOS412,
                    "            raw_key=raw,\n            moderation={FROM_PHOTO_ID: str(face.id)},\n",
                    "            raw_key=raw,\n            public_key=public_photo_key(copy_id),\n            status=ReviewStatus.APPROVED,\n            moderation={FROM_PHOTO_ID: str(face.id)},\n",
                )
            ],
            expect=[
                "test_show_makes_a_pending_public_copy_and_sends_it_through_moderation"
            ],
        ),
        PHOTOS_TESTS412,
    ),
    (
        Case(
            id="t412-10-the-allowlist-a-blacklist",
            what="rule 16: who needs a face photo named by who doesn't",
            edits=[
                (
                    RULES48,
                    "    return gender not in MAY_LEAVE_PHOTOS_WITHOUT_A_FACE_PHOTO\n",
                    "    return gender is Gender.FEMALE\n",
                )
            ],
            expect=[
                "test_anyone_but_a_man_needs_a_face_photo[no gender]",
                "test_only_a_man_leaves_the_photos_step_without_a_face_photo[no gender]",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t412-11-the-face-photo-check-removed",
            what="point 2: the photos step left without a face photo by anyone",
            edits=[
                (
                    SERVICE48,
                    "        if rules.needs_a_face_photo(\n            user.gender\n        ) and not await",
                    "        if False and not await",
                )
            ],
            expect=["test_anyone_but_a_man_needs_a_face_photo"],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t412-12-photo-back-in-the-requirements",
            what="D-392: a public photo needed to finish again",
            edits=[
                (
                    RULES48,
                    '        "interests": facts.interests == INTERESTS_PER_PROFILE,\n',
                    '        "photo": facts.approved_photos >= 1,\n        "interests": facts.interests == INTERESTS_PER_PROFILE,\n',
                )
            ],
            expect=[
                "test_zero_photos_finishes_at_completeness_50",
                "test_no_photo_is_not_missing",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t412-13-completeness-below-50-at-zero",
            what="D-392: no photo ranked below the bottom",
            edits=[
                (
                    RULES48,
                    "    extra = max(0, approved_photos - 1)\n",
                    "    extra = approved_photos - 1\n",
                )
            ],
            expect=[
                "test_completeness_is_50_and_10_for_each_photo_after_the_first[0-50]",
                "test_zero_photos_finishes_at_completeness_50",
            ],
        ),
        [ONBOARDING],
    ),
    (
        Case(
            id="t412-14-a-non-match-rejects-the-photo",
            what="D-393 rule 3: her photo from behind taken down",
            edits=[
                (
                    SERVICE45,
                    "        locked.moderation = {\n            **(locked.moderation or {}),\n            SELFIE_MATCH: {\n",
                    '        if not matched:\n            locked.status = ReviewStatus.REJECTED\n            locked.reject_reason = "no_match"\n        locked.moderation = {\n            **(locked.moderation or {}),\n            SELFIE_MATCH: {\n',
                )
            ],
            expect=[
                "test_a_shown_face_that_doesnt_match_isnt_rejected_and_doesnt_count"
            ],
        ),
        BADGE_TESTS,
    ),
    (
        Case(
            id="t412-15-the-comparison-not-queued-on-approval",
            what="D-393: a photo approved after the match never compared",
            edits=[
                (
                    PHOTOS412,
                    "        if locked.kind is PhotoKind.PUBLIC and scores.minors and user.is_verified:\n            await queue_match(queue, locked)\n",
                    "",
                )
            ],
            expect=[
                "test_an_approved_public_photo_with_a_face_is_queued_for_the_badge[a-shown-face-with-a-selfie-kept]",
                "test_shown_the_copy_is_compared_for_the_badge_once_approved",
            ],
        ),
        PHOTOS_TESTS412,
    ),
    (
        Case(
            id="t412-16-the-comparison-not-queued-on-the-selfies-decision",
            what="D-393: the photos already there never compared",
            edits=[
                (
                    SERVICE45,
                    "            to_compare = await repository.shown_photos_with_a_face(session, user.id)\n",
                    "            to_compare = []\n",
                )
            ],
            expect=[
                "test_a_match_queues_the_badges_comparison_for_each_shown_face",
                "test_the_selfie_is_compared_with_the_face_photo_alone",
            ],
        ),
        [VER],
    ),
    (
        Case(
            id="t412-17-the-badge-on-is-verified-alone",
            what="D-393 rule 4: the badge with no shown face that matched",
            edits=[
                (
                    # `badge_of` since T-6.2, which `shows_badge` reads.
                    REPO45,
                    "    return and_(is_verified.is_(True), main_matched.is_(True))\n",
                    "    return is_verified.is_(True)\n",
                )
            ],
            expect=["test_the_query_needs_is_verified_and_a_main_photo_that_matched"],
        ),
        BADGE_TESTS,
    ),
    (
        Case(
            id="t412-18-the-badge-counting-a-non-match",
            what="D-393 rule 3: a comparison made, whatever it said",
            edits=[
                (
                    REPO45,
                    # D-910 since T-9.8: the main photo's comparison.
                    "    return and_(is_verified.is_(True), main_matched.is_(True))\n",
                    "    return and_(is_verified.is_(True), main_matched.is_not(None))\n",
                )
            ],
            expect=[
                "test_the_query_needs_is_verified_and_a_main_photo_that_matched",
                "test_a_shown_face_that_doesnt_match_isnt_rejected_and_doesnt_count",
            ],
        ),
        BADGE_TESTS,
    ),
    (
        Case(
            id="t412-19-the-migration-not-re-creating-the-indexes",
            what="the rebuild leaving photos without its indexes",
            edits=[
                (
                    MIGRATION412,
                    "    for _, definition in indexes:\n        op.execute(definition)\n",
                    "",
                )
            ],
            expect=[
                "test_the_rebuild_keeps_the_check_and_the_indexes",
                "test_two_live_public_photos_cannot_share_a_slot",
            ],
        ),
        MIGRATION_TESTS412,
    ),
    (
        Case(
            id="t412-20-the-downgrade-not-refusing",
            what="the kind dropped from under the rows that use it",
            edits=[
                (
                    MIGRATION412,
                    "    if used:\n        raise RuntimeError(\n",
                    "    if False:\n        raise RuntimeError(\n",
                )
            ],
            expect=["test_the_downgrade_refuses_while_a_face_photo_exists"],
        ),
        MIGRATION_TESTS412,
    ),
    (
        Case(
            id="t412-21-the-seed-adding-a-second-face-photo",
            what="the seed's re-run no longer changing nothing",
            edits=[(SEED, "    if live is not None:\n        return\n", "")],
            expect=["test_a_second_run_adds_no_photo"],
        ),
        ["tests/seed/test_seed.py"],
    ),
    (
        Case(
            id="t412-22-the-face-photo-kept-past-a-refusal",
            what="D-078: a refusal's face photo file left in storage",
            edits=[
                (
                    USERS_REPO412,
                    "            select(column).where(or_(*naming), column.is_not(None))\n",
                    '            select(column).where(\n                or_(*naming),\n                column.is_not(None),\n                getattr(file.model, "kind", None) != "verification",\n            )\n',
                )
            ],
            expect=["test_a_refusals_face_photo_goes_with_it"],
        ),
        ["tests/modules/users/test_dob_gender.py"],
    ),
]

# --- T-8.1: packs, orders, GST, turnover, the simulator, Razorpay's orders ------

PAY_SERVICE = "app/modules/payments/service.py"
PAY_REPO = "app/modules/payments/repository.py"
PAY_RULES = "app/modules/payments/rules.py"
PAY_SCHEMAS = "app/modules/payments/schemas.py"
PAY_ROUTER = "app/modules/payments/router.py"
ADMIN_ROUTER = "app/modules/admin/router.py"
GST_COLUMN = "alembic/versions/20261008_86d605e7b904_payments_carry_gst_paise.py"
ORDER_KEY = "alembic/versions/20261008_25558532ccde_one_order_per_idempotency_key.py"
RAZORPAY = "app/core/providers/payments.py"
T81_SELECTION = [
    "tests/modules/payments",
    "tests/modules/e2e/test_payments_simulator.py",
    "tests/workers/test_log_turnover.py",
    "tests/core/test_razorpay.py",
    "tests/test_config.py",
    "tests/test_schema.py",
    "tests/test_migrations.py",
]

T81: list[Case] = [
    Case(
        id="t81-01-a-woman-sold-velas",
        what="D-076: a woman shown the store and sold an order",
        edits=[
            (
                PAY_SERVICE,
                "    if user.gender is not Gender.MALE:\n",
                "    if user.gender is None:\n",
            )
        ],
        expect=[
            "test_a_woman_is_refused_the_store",
            "test_a_woman_is_refused_before_any_gateway_is_asked",
        ],
    ),
    Case(
        id="t81-02-variant-b-shown-its-own-empty-store",
        what="D-480: variant B shown its own packs, of which none is active",
        edits=[(PAY_RULES, 'MappingProxyType({"B": "A"})', "MappingProxyType({})")],
        expect=[
            "test_each_variant_sees_d099s_four_with_the_first_purchase_bonus[B]",
            "test_no_man_is_ever_shown_an_empty_store",
            "test_every_variant_a_man_can_be_in_is_shown_packs_that_exist",
        ],
    ),
    Case(
        id="t81-03-an-empty-store-shown-blank",
        what="D-480: a store with no active pack answered with an empty list",
        edits=[(PAY_SERVICE, "    if not packs:\n", "    if False:\n")],
        expect=["test_a_store_with_no_active_pack_is_a_500_and_an_error_never_a_blank"],
    ),
    Case(
        id="t81-04-the-browser-names-a-price",
        what="rule 6: an order body naming an amount or Velas accepted",
        edits=[
            (
                PAY_SCHEMAS,
                'model_config = ConfigDict(extra="forbid")\n\n    pack_id: str',
                'model_config = ConfigDict(extra="ignore")\n\n    pack_id: str',
            )
        ],
        expect=["test_a_body_naming_a_price_or_velas_is_refused"],
    ),
    Case(
        id="t81-05-the-keys-order-not-looked-up",
        what="D-481: a key sent again makes a second gateway order",
        edits=[
            (PAY_SERVICE, "        if existing is not None:\n", "        if False:\n")
        ],
        expect=["test_the_same_key_twice_is_one_order"],
    ),
    Case(
        id="t81-06-the-race-not-caught",
        what="D-481: the insert's conflict on the key not handled",
        edits=[
            (
                PAY_REPO,
                '        .on_conflict_do_nothing(constraint="uq_payments_user_id_idempotency_key")\n',
                "",
            )
        ],
        expect=["test_the_same_key_racing_itself_is_one_order"],
    ),
    Case(
        id="t81-07-the-key-not-unique-per-man",
        what="D-481: the database's unique key widened until it holds nothing",
        edits=[
            (
                ORDER_KEY,
                '["user_id", "idempotency_key"],',
                '["idempotency_key", "provider_order_id"],',
            )
        ],
        expect=[
            "test_the_database_refuses_a_second_order_for_one_key",
            "test_the_same_key_racing_itself_is_one_order",
        ],
    ),
    Case(
        id="t81-08-a-key-reused-for-another-pack",
        what="D-481: a key's first order returned for another pack",
        edits=[
            (PAY_SERVICE, "    if payment.pack_id != pack_id:\n", "    if False:\n")
        ],
        expect=["test_the_same_key_with_another_pack_is_already_used"],
    ),
    Case(
        id="t81-09-another-variants-pack-sold",
        what="D-480: an order for a pack outside the man's store",
        edits=[
            (
                PAY_REPO,
                "            CreditPack.variant == variant,\n            CreditPack.active.is_(True),\n",
                "            CreditPack.active.is_(True),\n",
            )
        ],
        expect=["test_a_pack_outside_his_store_isnt_found"],
    ),
    Case(
        id="t81-10-a-retired-pack-sold",
        what="D-250: an order for a retired pack",
        edits=[
            (
                PAY_REPO,
                "            CreditPack.variant == variant,\n            CreditPack.active.is_(True),\n",
                "            CreditPack.variant == variant,\n",
            )
        ],
        expect=["test_a_retired_or_unknown_pack_isnt_found[pack-25]"],
    ),
    Case(
        id="t81-11-a-refund-restores-the-bonus",
        what="D-231: a refunded purchase not counted as a purchase",
        edits=[
            (
                PAY_REPO,
                "Payment.status.in_((PaymentStatus.PAID, PaymentStatus.REFUNDED))",
                "Payment.status.in_((PaymentStatus.PAID,))",
            )
        ],
        expect=["test_a_refunded_purchase_was_still_a_purchase"],
    ),
    Case(
        id="t81-12-registered-for-gst-accepted",
        what="D-482: GST_REGISTERED=true starts, changing nothing",
        edits=[
            (
                "app/core/config.py",
                "        if self.GST_REGISTERED:\n",
                "        if False:\n",
            )
        ],
        expect=["test_registering_for_gst_refuses_to_start_until_p350_builds_it"],
    ),
    Case(
        id="t81-13-a-registered-split-made-up",
        what="D-482: a registered split computed as 0, silently",
        edits=[(PAY_RULES, "    if registered:\n", "    if False:\n")],
        expect=["test_a_registered_split_isnt_built"],
    ),
    Case(
        id="t81-14-gst-outside-the-amount",
        what="D-450: the database lets gst_paise reach the whole amount",
        edits=[
            (
                GST_COLUMN,
                '"gst_paise >= 0 AND gst_paise < amount_paise",',
                '"gst_paise >= 0",',
            )
        ],
        expect=["test_the_database_keeps_gst_inside_the_amount"],
    ),
    Case(
        id="t81-15-gst-shown-unregistered",
        what="D-450: the order's response carries gst_paise, 0",
        edits=[
            (
                PAY_SCHEMAS,
                "    key_id: str\n    amount_paise: int\n",
                "    key_id: str\n    amount_paise: int\n    gst_paise: int = 0\n",
            )
        ],
        expect=["test_an_unregistered_payment_says_gst_nowhere"],
    ),
    Case(
        id="t81-16-the-year-in-utc",
        what="D-483: the financial year turned at midnight UTC, not IST",
        edits=[
            (
                PAY_RULES,
                "    local = instant.astimezone(IST)\n",
                "    local = instant.astimezone(UTC)\n",
            ),
            (
                PAY_RULES,
                "datetime(self.first_year, 4, 1, tzinfo=IST)",
                "datetime(self.first_year, 4, 1, tzinfo=UTC)",
            ),
            (
                PAY_RULES,
                "datetime(self.first_year + 1, 4, 1, tzinfo=IST)",
                "datetime(self.first_year + 1, 4, 1, tzinfo=UTC)",
            ),
            (
                PAY_RULES,
                "from datetime import datetime\n",
                "from datetime import UTC, datetime\n",
            ),
        ],
        expect=[
            "test_payments_either_side_of_1_april_fall_in_their_own_years",
            "test_the_year_turns_at_midnight_in_india_not_utc",
        ],
    ),
    Case(
        id="t81-17-unpaid-orders-counted",
        what="D-483: turnover counts every payment, paid or not",
        edits=[
            (PAY_REPO, "                Payment.status == PaymentStatus.PAID,\n", "")
        ],
        expect=["test_only_paid_payments_count"],
    ),
    Case(
        id="t81-18-the-years-end-counted-twice",
        what="D-483: a payment at the year's end counted in both years",
        edits=[(PAY_REPO, "Payment.paid_at < ends_at,", "Payment.paid_at <= ends_at,")],
        expect=["test_payments_either_side_of_1_april_fall_in_their_own_years"],
    ),
    Case(
        id="t81-19-the-warning-a-paisa-late",
        what="D-483: the warning only above ₹15 lakh, not at it",
        edits=[(PAY_RULES, ">= TURNOVER_ALERT_PAISE", "> TURNOVER_ALERT_PAISE")],
        expect=[
            "test_the_lines_level_at_15_and_20_lakh[150000000-warning]",
            "test_the_line_warns_at_15_lakh_and_not_a_paisa_below",
        ],
    ),
    Case(
        id="t81-20-the-error-a-paisa-late",
        what="D-483: the error only above ₹20 lakh, not at it",
        edits=[(PAY_RULES, ">= GST_THRESHOLD_PAISE", "> GST_THRESHOLD_PAISE")],
        expect=[
            "test_the_lines_level_at_15_and_20_lakh[200000000-error]",
            "test_the_line_is_an_error_from_20_lakh",
        ],
    ),
    Case(
        id="t81-21-a-moderator-reads-revenue",
        what="D-483: turnover readable by a moderator",
        edits=[
            (
                ADMIN_ROUTER,
                "async def turnover(\n    admin: Annotated[User, Depends(require_role(Role.ADMIN))]",
                "async def turnover(\n    admin: Annotated[User, Depends(require_role(Role.MODERATOR, Role.ADMIN))]",
            )
        ],
        expect=["test_anyone_but_an_admin_is_forbidden[moderator]"],
    ),
    Case(
        id="t81-22-a-read-not-audited",
        what="02-ARCHITECTURE §12: an admin's read of turnover leaves no audit row",
        edits=[
            (
                PAY_SERVICE,
                (
                    "        await admin_service.audit(\n"
                    '            session, admin_id, "turnover.read", {"financial_year": year.label}\n'
                    "        )\n"
                ),
                "",
            )
        ],
        expect=["test_an_admin_reads_this_years_turnover_and_the_read_is_audited"],
    ),
    Case(
        id="t81-23-the-simulator-by-blacklist",
        what="rule 16: the simulator served everywhere but production",
        edits=[
            (
                "app/main.py",
                "        settings.ENV in PAYMENTS_SIMULATOR_SERVED_IN\n",
                '        settings.ENV != "production"\n',
            )
        ],
        expect=[
            "test_isnt_served_anywhere_else[ENV=staging]",
            "test_isnt_served_anywhere_else[ENV=env-nobody-has-named-2031]",
        ],
    ),
    Case(
        id="t81-24-the-simulator-beside-razorpay",
        what="rule 16: the simulator served beside a real gateway",
        edits=[
            (
                "app/main.py",
                "        and settings.PAYMENTS_PROVIDER in PAYMENTS_SIMULATOR_SERVED_FOR\n",
                "        and True\n",
            )
        ],
        expect=["test_isnt_served_anywhere_else[PAYMENTS_PROVIDER=razorpay]"],
    ),
    Case(
        id="t81-25-orders-unlimited",
        what="02-ARCHITECTURE §12: more than 20 orders an hour",
        edits=[(PAY_ROUTER, "ORDERS_PER_HOUR = 20\n", "ORDERS_PER_HOUR = 21\n")],
        expect=["test_twenty_orders_an_hour"],
    ),
    Case(
        id="t81-26-razorpays-amount-trusted",
        what="Razorpay's order trusted for an amount we didn't ask",
        edits=[
            (
                RAZORPAY,
                '    if amount != amount_paise or currency != "INR":\n',
                '    if currency != "INR":\n',
            )
        ],
        expect=["test_an_answer_that_isnt_our_order_is_never_trusted[other-amount]"],
    ),
    Case(
        id="t81-27-razorpay-called-with-half-a-key",
        what="P-382: Razorpay called with one of its two keys missing",
        edits=[
            (
                RAZORPAY,
                "        if not (self._key_id and self._key_secret):\n",
                "        if not (self._key_id or self._key_secret):\n",
            )
        ],
        expect=["test_without_keys_it_refuses_and_calls_nobody"],
    ),
    Case(
        id="t81-28-the-cron-in-the-machines-zone",
        what="D-483: the daily line scheduled in the machine's zone, not UTC",
        edits=[("app/workers/main.py", "    timezone = UTC\n", "")],
        expect=["test_it_runs_once_a_day_at_0900_ist"],
    ),
]


# --- P-120: positions on a 1 km grid, never exactly (D-490) --------------------------

PROFILES_REPO120 = "app/modules/profiles/repository.py"
PROFILES_MODELS120 = "app/modules/profiles/models.py"
SNAP120 = "alembic/versions/20261008_4c71a9e2b058_snap_profile_positions.py"
CHECK120 = "alembic/versions/20261008_9b4e0d2c7a15_profiles_location_on_grid.py"
GRID_TESTS120 = ["tests/modules/profiles/test_grid.py"]
LOCATION_TESTS120 = [
    "tests/modules/profiles/test_grid.py",
    "tests/modules/profiles/test_location.py",
]

P120: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="p120-01-a-shared-position-stored-exactly",
            what="D-490: `PUT /me/location` storing the exact point",
            edits=[
                (
                    PROFILES_REPO120,
                    "    return on_grid(exact_point(lat, lng))\n",
                    "    return exact_point(lat, lng)\n",
                )
            ],
            expect=[
                "test_every_position_inside_one_cell_is_stored_as_the_same_point",
                "test_a_position_is_stored_with_its_nearest_area_and_answers_me",
            ],
        ),
        LOCATION_TESTS120,
    ),
    (
        Case(
            id="p120-02-no-check",
            what="D-490: the database taking an exact point (the CHECK gone)",
            edits=[
                (
                    CHECK120,
                    '    op.create_check_constraint(op.f(NAME), "profiles", ON_GRID)\n',
                    "    pass\n",
                ),
                (
                    CHECK120,
                    '    op.drop_constraint(op.f(NAME), "profiles", type_="check")\n',
                    "    pass\n",
                ),
                (
                    PROFILES_MODELS120,
                    '        CheckConstraint(LOCATION_ON_GRID, name="location_on_grid"),\n',
                    "",
                ),
            ],
            expect=["test_the_database_refuses_a_position_off_the_grid"],
        ),
        GRID_TESTS120,
    ),
    (
        Case(
            id="p120-03-the-area-from-the-grid-point",
            what="D-220: a shared position's area found from its grid point",
            edits=[
                (
                    PROFILES_REPO120,
                    "    here = exact_point(lat, lng)\n",
                    "    here = point(lat, lng)\n",
                )
            ],
            expect=[
                "test_the_area_is_found_from_the_exact_position_not_its_grid_point[True]",
                "test_the_area_is_found_from_the_exact_position_not_its_grid_point[False]",
            ],
        ),
        GRID_TESTS120,
    ),
    (
        Case(
            id="p120-04-a-picked-centroid-stored-exactly",
            what="D-490: a picked area stored at its exact centroid",
            edits=[
                (
                    PROFILES_REPO120,
                    "    return on_grid(select(Area.centroid).where(Area.id == area_id).scalar_subquery())\n",
                    "    return select(Area.centroid).where(Area.id == area_id).scalar_subquery()\n",
                )
            ],
            expect=["test_a_picked_area_is_stored_at_its_centroids_grid_point"],
        ),
        LOCATION_TESTS120,
    ),
    (
        Case(
            id="p120-05-the-migration-moving-nothing",
            what="D-490: the positions stored before the grid left exact",
            edits=[
                (
                    SNAP120,
                    '            "WHERE location IS NOT NULL "\n',
                    '            "WHERE false "\n',
                )
            ],
            expect=["test_the_migration_moves_the_positions_already_stored"],
        ),
        GRID_TESTS120,
    ),
    (
        Case(
            # p120-01's red is the CHECK refusing the write; with the CHECK gone
            # too, the tests' own assertions must still see the exact point.
            id="p120-07-stored-exactly-with-no-check",
            what="D-490: the exact point stored, and the database letting it",
            edits=[
                (
                    PROFILES_REPO120,
                    "    return on_grid(exact_point(lat, lng))\n",
                    "    return exact_point(lat, lng)\n",
                ),
                (
                    CHECK120,
                    '    op.create_check_constraint(op.f(NAME), "profiles", ON_GRID)\n',
                    "    pass\n",
                ),
                (
                    CHECK120,
                    '    op.drop_constraint(op.f(NAME), "profiles", type_="check")\n',
                    "    pass\n",
                ),
                (
                    PROFILES_MODELS120,
                    '        CheckConstraint(LOCATION_ON_GRID, name="location_on_grid"),\n',
                    "",
                ),
            ],
            expect=[
                "test_every_position_inside_one_cell_is_stored_as_the_same_point",
                "test_a_position_is_stored_with_its_nearest_area_and_answers_me",
            ],
        ),
        LOCATION_TESTS120,
    ),
    (
        Case(
            id="p120-06-the-seed-storing-exactly",
            what="D-490: the seed writing its scatter's exact point",
            edits=[
                (
                    SEED,
                    "            location = profiles_repository.on_grid(\n",
                    "            location = (\n",
                )
            ],
            expect=[
                "test_each_profile_sits_on_its_scatters_grid_point_inside_its_area"
            ],
        ),
        ["tests/seed/test_seed.py"],
    ),
]

# --- P-210: completeness kept current after onboarding finishes ----------------------

PHOTOS210 = "app/modules/photos/service.py"
ONBOARDING210 = "app/modules/onboarding/service.py"
COMPLETENESS_TESTS210 = ["tests/modules/photos/test_completeness.py"]

P210: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="p210-01-an-approval-not-counted",
            what="P-210: moderation's approval leaving completeness as it was",
            edits=[
                (
                    PHOTOS210,
                    "        if locked.kind is PhotoKind.PUBLIC:\n            await onboarding_service.refresh_completeness(session, user)\n",
                    "",
                )
            ],
            expect=["test_an_approval_after_finishing_raises_it"],
        ),
        COMPLETENESS_TESTS210,
    ),
    (
        Case(
            id="p210-02-a-removal-not-counted",
            what="P-210: removing a shown photo leaving completeness as it was",
            edits=[
                (
                    PHOTOS210,
                    "        if photo.kind is PhotoKind.PUBLIC:\n            await onboarding_service.refresh_completeness(session, user)\n",
                    "",
                )
            ],
            expect=[
                "test_removing_an_approved_public_photo_lowers_it[False]",
                "test_removing_an_approved_public_photo_lowers_it[True]",
            ],
        ),
        COMPLETENESS_TESTS210,
    ),
    (
        Case(
            id="p210-03-set-before-finishing",
            what="D-310: completeness set before onboarding is done",
            edits=[
                (
                    ONBOARDING210,
                    "    if user.onboarding_step is not OnboardingStep.DONE:\n        return\n    profile = await repository.profile_of(session, user.id)\n    approved",
                    "    profile = await repository.profile_of(session, user.id)\n    approved",
                )
            ],
            expect=["test_before_finishing_an_approval_leaves_it_to_finishing"],
        ),
        COMPLETENESS_TESTS210,
    ),
]

# --- T-6.2: the discovery feed --------------------------------------------------------

DISCOVERY_TESTS62 = ["tests/modules/discovery"]

T62: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t62-01-self-in-the-feed",
            what="the viewer shown to themselves",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        User.id != viewer.id,\n",
                    "",
                )
            ],
            expect=[
                "test_someone_seeking_everyone_sees_both_who_want_them_and_never_themselves"
            ],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-02-swiped-still-shown",
            what="someone already swiped shown again",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        ~exists().where(Swipe.swiper_id == viewer.id, Swipe.target_id == User.id),\n",
                    "",
                )
            ],
            expect=[
                "test_someone_i_swiped_is_gone_whichever_way[like]",
                "test_someone_i_swiped_is_gone_whichever_way[pass]",
                "test_someone_i_swiped_is_gone_whichever_way[super]",
            ],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-03-a-block-one-way",
            what="critical 9: a block hides only the blocked from the blocker",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        .where(Block.unblocked_at.is_(None), or_(by(a, b), by(b, a)))\n",
                    "        .where(Block.unblocked_at.is_(None), by(a, b))\n",
                )
            ],
            expect=["test_a_block_either_way_hides_each_from_the_other[her]"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-04-hidden-shown",
            what="a hidden profile in the feed",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        hidden if hidden_ok is None else or_(hidden, hidden_ok),\n",
                    "",
                )
            ],
            expect=["test_a_hidden_profile_is_left_out"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-05-not-done-shown",
            what="someone mid-onboarding in the feed",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        User.onboarding_step == OnboardingStep.DONE,\n        hidden if hidden_ok is None else or_(hidden, hidden_ok),\n",
                    "        hidden if hidden_ok is None else or_(hidden, hidden_ok),\n",
                )
            ],
            expect=["test_someone_not_done_is_left_out[selfie]"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-06-not-active-shown",
            what="a frozen or deleted account in the feed",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        User.id != viewer.id,\n        User.status == UserStatus.ACTIVE,\n",
                    "        User.id != viewer.id,\n",
                )
            ],
            expect=[
                "test_anyone_not_active_is_left_out[frozen]",
                "test_anyone_not_active_is_left_out[deleted]",
            ],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-07-freeze-band-shown",
            what="D-031: the freeze band in the feed",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        hidden if hidden_ok is None else or_(hidden, hidden_ok),\n        ~_in_band(User.id, FraudBand.FREEZE),\n",
                    "        hidden if hidden_ok is None else or_(hidden, hidden_ok),\n",
                )
            ],
            expect=["test_a_frozen_band_is_left_out_for_everyone[None]"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-08-shadow-shown-to-all",
            what="D-031: the shadowed shown to everyone",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "    if not viewer.shadowed:\n        conditions.append(~_in_band(User.id, FraudBand.SHADOW))\n",
                    "",
                )
            ],
            expect=["test_the_shadowed_are_shown_only_to_the_shadowed[None-False]"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-09-shadow-hidden-from-shadow",
            what="D-031: the shadowed hidden from each other too",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "    if not viewer.shadowed:\n        conditions.append(~_in_band(User.id, FraudBand.SHADOW))\n",
                    "    conditions.append(~_in_band(User.id, FraudBand.SHADOW))\n",
                )
            ],
            expect=["test_the_shadowed_are_shown_only_to_the_shadowed[shadow-True]"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-10-one-sided-seeking",
            what="discovery not mutual: her seeking ignored",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "            Profile.seeking.in_(rules.seekings_wanting(viewer.gender)),\n",
                    "",
                )
            ],
            expect=["test_a_man_sees_the_women_nearby_who_want_men"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-11-badge-is-is-verified",
            what="D-393: the badge reduced to is_verified",
            edits=[
                (
                    "app/modules/verification/repository.py",
                    "    return and_(is_verified.is_(True), main_matched.is_(True))\n",
                    "    return is_verified.is_(True)\n",
                )
            ],
            expect=[
                "test_the_badge_is_d393s_never_is_verified_alone[True-False-False]",
                "test_the_verified_filter_is_the_badge_never_is_verified_alone",
            ],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-12-hidden-age-shown",
            what="a hidden age on the card",
            edits=[
                (
                    "app/modules/discovery/service.py",
                    "        if row.hide_age or row.dob is None\n        else users_service.age_on(row.dob, clock.today_ist()),\n        username=row.username,\n",
                    "        if row.dob is None\n        else users_service.age_on(row.dob, clock.today_ist()),\n        username=row.username,\n",
                )
            ],
            expect=["test_hidden_age_and_distance_are_null"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-13-under-a-kilometre",
            what="D-034: 0 km on a card",
            edits=[
                (
                    "app/modules/discovery/rules.py",
                    "    return max(1, math.floor(metres / 1000 + 0.5))\n",
                    "    return math.floor(metres / 1000 + 0.5)\n",
                )
            ],
            expect=[
                "test_the_distance_is_whole_kilometres_between_grid_points_never_under_1[0-1]"
            ],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-14-as-of-not-pinned",
            what="D-491: each page ranked at its own time",
            edits=[
                (
                    "app/modules/discovery/service.py",
                    "        as_of, score, last = FEED_CURSOR.decode(params.cursor)\n",
                    "        _, score, last = FEED_CURSOR.decode(params.cursor)\n",
                )
            ],
            expect=[
                "test_time_passing_between_pages_never_repeats_or_skips_a_card",
                "test_each_cursor_carries_the_scrolls_first_instant",
            ],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-15-radius-not-app-configs",
            what="the radius fixed at 25 km, app_config ignored",
            edits=[
                (
                    "app/modules/discovery/service.py",
                    "            radius_m=radius_km * 1000.0,\n            new_first=",
                    "            radius_m=25_000.0,\n            new_first=",
                )
            ],
            expect=["test_the_radius_is_read_from_app_config_within_a_minute"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-16-main-photo-any-status",
            what="P-75: a pending or rejected photo as the main one, or in the list",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        Photo.status == ReviewStatus.APPROVED,\n        Photo.public_key.is_not(None),\n    ]\n",
                    "        Photo.public_key.is_not(None) | Photo.public_key.is_(None),\n    ]\n",
                )
            ],
            expect=[
                "test_the_main_photo_is_the_lowest_approved_public_place_gap_or_not",
                "test_only_approved_public_photos_are_shown_and_nothing_private_named",
            ],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-17-jit-left-on",
            what="D-495: the feed compiled by JIT on every request",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "    await session.execute(JIT_OFF)\n",
                    "",
                )
            ],
            expect=["test_the_feed_runs_with_jit_off_for_its_own_transaction_only"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-18-radius-past-the-index",
            what="the radius written so the GIST index can't serve it",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        *visible_to(viewer, mutual=True),\n        func.ST_DWithin(Profile.location, here, radius_m),\n",
                    "        *visible_to(viewer, mutual=True),\n        func.ST_Distance(Profile.location, here) <= radius_m,\n",
                )
            ],
            expect=["test_a_spread_crowd_is_searched_through_the_gist_index"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-19-intents-ignored",
            what="D-041: the intent filter not applied",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "    if intent_ids:\n        conditions.append(\n",
                    "    if False:\n        conditions.append(\n",
                )
            ],
            expect=["test_intents_match_on_any_overlap"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-20-online-feed-unfiltered",
            what="the online feed showing anyone",
            edits=[
                (
                    "app/modules/discovery/service.py",
                    (
                        "            online_since=(\n"
                        "                as_of - rules.ONLINE_FOR if online or feed is Feed.ONLINE else None\n"
                        "            ),\n"
                    ),
                    "            online_since=None,\n",
                )
            ],
            expect=["test_the_online_feed_is_the_last_five_minutes_only"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-21-new-not-lifted",
            what="the new feed ranked like for-you",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "            (User.created_at >= literal(as_of - rules.NEW_FOR), rules.NEW_LIFT),\n",
                    "            (User.created_at >= literal(as_of - rules.NEW_FOR), 0.0),\n",
                )
            ],
            expect=["test_the_new_feed_puts_the_new_first_then_ranks_each"],
        ),
        DISCOVERY_TESTS62,
    ),
    (
        Case(
            id="t62-22-weights-moved",
            what="D-491's weights changed quietly",
            edits=[
                (
                    "app/modules/discovery/rules.py",
                    "WEIGHT_DISTANCE: Final = 0.40\n",
                    "WEIGHT_DISTANCE: Final = 0.45\n",
                )
            ],
            expect=["test_the_score_is_d491s_formula_exactly"],
        ),
        DISCOVERY_TESTS62,
    ),
]

# --- T-6.3: the public profile -------------------------------------------------------

T63: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t63-01-hidden-closed-to-a-chat",
            what="D-493: a hidden profile refused to someone it shares a Thread with",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "                hidden_ok=shares_a_match_or_thread(viewer.id, User.id),\n",
                    "                hidden_ok=None,\n",
                )
            ],
            expect=[
                "test_a_hidden_profile_opens_to_someone_it_shares_a_match_or_thread_with[match]",
                "test_a_hidden_profile_opens_to_someone_it_shares_a_match_or_thread_with[thread]",
            ],
        ),
        ["tests/modules/discovery/test_public_profile.py"],
    ),
    (
        Case(
            id="t63-02-hidden-open-to-anyone",
            what="D-493: a hidden profile opened to strangers",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "                hidden_ok=shares_a_match_or_thread(viewer.id, User.id),\n",
                    "                hidden_ok=User.id == User.id,\n",
                )
            ],
            expect=[
                "test_every_refusal_is_the_same_not_found_as_nobody",
                "test_a_hidden_profile_opens_to_someone_it_shares_a_match_or_thread_with[thread]",
            ],
        ),
        ["tests/modules/discovery/test_public_profile.py"],
    ),
    (
        Case(
            id="t63-03-a-thread-doesnt-count",
            what="D-493: only a match opens a hidden profile",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "        exists().where(Thread.user_low == low, Thread.user_high == high),\n",
                    "",
                )
            ],
            expect=[
                "test_a_hidden_profile_opens_to_someone_it_shares_a_match_or_thread_with[thread]"
            ],
        ),
        ["tests/modules/discovery/test_public_profile.py"],
    ),
    (
        Case(
            id="t63-04-seeking-applied",
            what="D-493: a link refused by seeking",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "    session: AsyncSession, viewer: Viewer, user_id: UUID, *, mutual: bool = False\n",
                    "    session: AsyncSession, viewer: Viewer, user_id: UUID, *, mutual: bool = True\n",
                )
            ],
            expect=["test_seeking_and_the_radius_dont_apply_a_link_reaches_past_them"],
        ),
        ["tests/modules/discovery/test_public_profile.py"],
    ),
    (
        Case(
            id="t63-05-my-own-view-recorded",
            what="a view of my own profile recorded",
            edits=[
                (
                    "app/modules/discovery/service.py",
                    "    if not own:\n        await repository.record_view(",
                    "    if True:\n        await repository.record_view(",
                )
            ],
            expect=["test_my_own_profile_opens_with_nothing_between_us"],
        ),
        ["tests/modules/discovery/test_public_profile.py"],
    ),
    (
        Case(
            id="t63-06-views-not-counted",
            what="a second view not counted",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    '                "view_count": ProfileView.view_count + 1,\n',
                    '                "view_count": ProfileView.view_count,\n',
                )
            ],
            expect=["test_a_view_is_one_row_per_pair_counted"],
        ),
        ["tests/modules/discovery/test_public_profile.py"],
    ),
    (
        Case(
            id="t63-07-hidden-kudos-shown",
            what="kudos shown when she hides them",
            edits=[
                (
                    "app/modules/discovery/service.py",
                    "    kudos = await repository.kudos_counts(session, user_id) if row.show_kudos else None\n",
                    "    kudos = await repository.kudos_counts(session, user_id)\n",
                )
            ],
            expect=["test_kudos_are_counted_and_null_when_hidden"],
        ),
        ["tests/modules/discovery/test_public_profile.py"],
    ),
    (
        Case(
            id="t63-08-album-counts-pending",
            what="the album count including photos not approved",
            edits=[
                (
                    "app/modules/discovery/repository.py",
                    "            Photo.kind == PhotoKind.PRIVATE,\n            Photo.status == ReviewStatus.APPROVED,\n",
                    "            Photo.kind == PhotoKind.PRIVATE,\n",
                )
            ],
            expect=[
                "test_only_approved_public_photos_are_shown_and_nothing_private_named"
            ],
        ),
        ["tests/modules/discovery/test_public_profile.py"],
    ),
]

# --- T-9.6: settings, deletion, the erasure, the export ----------------------------

ERASURE96 = "app/modules/account/erasure.py"
ACCOUNT96 = "app/modules/account/service.py"
ACCOUNT_REPO96 = "app/modules/account/repository.py"
ACCOUNT_SCHEMAS96 = "app/modules/account/schemas.py"
ACCOUNT_ROUTER96 = "app/modules/account/router.py"
USERS_SERVICE96 = "app/modules/users/service.py"
USERS_REPO96 = "app/modules/users/repository.py"
ANONYMISED96 = "alembic/versions/20261008_a3c12afe34d5_users_can_be_anonymised.py"
EXPORTS96 = "alembic/versions/20261008_b4bfd6974ee4_data_exports.py"
WORKER96 = "app/workers/main.py"
T96_SELECTION = [
    "tests/modules/account",
    "tests/modules/users",
    "tests/modules/auth",
    "tests/workers/test_worker.py",
    "tests/test_schema.py",
]
ERASED_29 = (
    "test_an_account_deleted_29_days_ago_is_erased_and_kept_exactly_as_d051_says"
)
CLASSIFIED = "test_every_column_keyed_to_users_is_erased_or_kept"
ALL_MINE = "test_the_export_is_all_mine_and_nothing_of_theirs"
RACE = "test_a_sign_in_and_the_erasure_at_once_never_leave_both_or_neither"

T96: list[Case] = [
    Case(
        id="t96-01-an-erased-table-dropped",
        what="D-503: swipes left off the erased list",
        edits=[(ERASURE96, '    Erased(Swipe, ("swiper_id", "target_id")),\n', "")],
        expect=[CLASSIFIED, ERASED_29],
    ),
    Case(
        id="t96-02-a-kept-column-erased",
        what="D-503: kudos the erased person gave, erased too",
        edits=[
            (
                ERASURE96,
                '    Erased(Kudos, ("to_id",)),\n',
                '    Erased(Kudos, ("to_id", "from_id")),\n',
            )
        ],
        expect=[CLASSIFIED],
    ),
    Case(
        id="t96-03-the-welcome-hash-unnamed",
        what="D-503, P-371: T-8.11's table dropped from the kept list (built since)",
        edits=[
            (
                ERASURE96,
                '    ("welcome_grants", "user_id"): "one welcome per number, ever (D-470)",\n',
                "",
            )
        ],
        expect=[
            "test_every_column_keyed_to_users_is_erased_or_kept",
            "test_the_welcome_hash_is_kept",
        ],
    ),
    Case(
        id="t96-04-an-export-file-left-behind",
        what="D-503: the erasure forgets export files",
        edits=[(ERASURE96, '    (DataExport, "file_key", "private"),\n', "")],
        expect=[
            "test_every_storage_key_on_an_erased_table_is_in_the_file_list",
            ERASED_29,
        ],
    ),
    Case(
        id="t96-05-erased-at-28-days",
        what="D-500: the erasure a day early",
        edits=[
            (
                ACCOUNT96,
                "ERASE_AFTER = timedelta(days=29)\n",
                "ERASE_AFTER = timedelta(days=28)\n",
            )
        ],
        expect=["test_not_yet_29_days_is_left_alone"],
    ),
    Case(
        id="t96-06-erased-at-30-days",
        what="D-500: the erasure past 'within 30 days' once a daily job runs",
        edits=[
            (
                ACCOUNT96,
                "ERASE_AFTER = timedelta(days=29)\n",
                "ERASE_AFTER = timedelta(days=30)\n",
            )
        ],
        expect=[ERASED_29],
    ),
    Case(
        id="t96-07-the-erasure-takes-no-lock",
        what="D-500: the erasure reads the row without locking it",
        edits=[
            (
                ACCOUNT_REPO96,
                "        .where(User.id == user_id, *_due(cutoff))\n        .with_for_update()\n",
                "        .where(User.id == user_id, *_due(cutoff))\n",
            )
        ],
        expect=[f"{RACE}[sign_in]"],
    ),
    Case(
        id="t96-08-the-sign-in-takes-no-lock",
        what="D-500: the sign-in's lookup without the row's lock",
        edits=[
            (
                USERS_REPO96,
                "        .where(User.phone_hash == phone_hash, User.anonymised_at.is_(None))\n        .with_for_update()\n",
                "        .where(User.phone_hash == phone_hash, User.anonymised_at.is_(None))\n",
            )
        ],
        expect=[f"{RACE}[erasure]"],
    ),
    Case(
        id="t96-09-sign-in-finds-the-erased-row",
        what="D-500: the sign-in's lookup reads erased rows too",
        edits=[
            (
                USERS_REPO96,
                "        .where(User.phone_hash == phone_hash, User.anonymised_at.is_(None))\n",
                "        .where(User.phone_hash == phone_hash)\n",
            )
        ],
        expect=["test_after_the_erasure_the_number_starts_a_new_account"],
    ),
    Case(
        id="t96-10-no-restore",
        what="D-500: signing in again doesn't restore a deleted account",
        edits=[
            (
                USERS_SERVICE96,
                "    if user.status is not UserStatus.DELETED:\n        return False\n",
                "    if True:\n        return False\n",
            )
        ],
        expect=["test_signing_in_within_the_window_restores_the_account_and_its_velas"],
    ),
    Case(
        id="t96-11-delete-around-a-ban",
        what="D-051: a deletion let in before a ban isn't checked again under the lock",
        edits=[
            (
                ACCOUNT96,
                "        users_service.refuse_who_may_not_sign_in(locked)\n",
                "",
            )
        ],
        expect=["test_a_ban_or_freeze_stops_a_deletion_even_one_already_let_in"],
    ),
    Case(
        id="t96-12-delete-keeps-sessions",
        what="D-500: deleting leaves the sessions live",
        edits=[
            (
                ACCOUNT96,
                "        await auth_service.sign_out_everywhere(session, locked.id)\n",
                "",
            )
        ],
        expect=["test_deleting_hides_the_account_at_once_and_signs_it_out_everywhere"],
    ),
    Case(
        id="t96-13-deleted-forbidden-again",
        what="D-500: a deleted account's token answered FORBIDDEN, as before T-9.6",
        edits=[
            (
                USERS_SERVICE96,
                '    if user.status is UserStatus.DELETED:\n        raise AppError(\n            "SESSION_REVOKED",',
                '    if False:\n        raise AppError(\n            "SESSION_REVOKED",',
            )
        ],
        expect=[
            "test_a_deleted_accounts_token_is_signed_out_at_the_next_request",
            "test_an_account_that_cant_sign_in_cant_refresh_either[deleted-401-SESSION_REVOKED]",
        ],
    ),
    Case(
        id="t96-14-dob-cleared-any-time",
        what="D-501: the trigger lets dob go null without the anonymising update",
        edits=[
            (
                ANONYMISED96,
                "       and not (new.dob is null\n                and old.anonymised_at is null\n                and new.anonymised_at is not null) then\n",
                "       and not (new.dob is null) then\n",
            )
        ],
        expect=["test_dob_can_be_cleared_only_by_the_anonymising_update"],
    ),
    Case(
        id="t96-15-an-anonymised-row-takes-a-dob",
        what="D-501: no check keeps an anonymised row's dob and PIN empty",
        edits=[
            (
                ANONYMISED96,
                '        "anonymised_at IS NULL OR (dob IS NULL AND pin_hash IS NULL)",\n',
                '        "anonymised_at IS NULL OR true",\n',
            )
        ],
        expect=["test_an_anonymised_row_can_never_take_a_dob_or_come_back"],
    ),
    Case(
        id="t96-16-anonymised-at-cleared",
        what="D-500: the trigger keeping anonymised_at for good disarmed",
        edits=[
            (
                ANONYMISED96,
                "    if old.anonymised_at is not null\n",
                "    if false\n",
            )
        ],
        expect=["test_an_anonymised_row_can_never_take_a_dob_or_come_back"],
    ),
    Case(
        id="t96-17-two-live-accounts-on-a-number",
        what="D-500: the live accounts' hash index not unique",
        edits=[(ANONYMISED96, "        unique=True,\n", "        unique=False,\n")],
        expect=["test_a_number_holds_one_live_account_and_any_number_of_erased_ones"],
    ),
    Case(
        id="t96-18-users-downgrade-over-erased-rows",
        what="D-500: the downgrade goes on over erased accounts",
        edits=[(ANONYMISED96, "    if erased:\n", "    if False:\n")],
        expect=["test_the_downgrade_refuses_while_an_account_is_erased"],
    ),
    Case(
        id="t96-19-exports-downgrade-over-files",
        what="D-502: the downgrade drops rows whose files may be stored",
        edits=[(EXPORTS96, "    if stored:\n", "    if False:\n")],
        expect=["test_the_downgrade_refuses_while_an_export_may_have_its_file"],
    ),
    Case(
        id="t96-20-the-other-persons-words-exported",
        what="D-502: every message on the user's threads exported, theirs too",
        edits=[
            (
                ACCOUNT_REPO96,
                "            .where(Message.sender_id == user_id)\n",
                "            .where(\n                Message.thread_id.in_(\n                    select(Thread.id).where(\n                        or_(Thread.user_low == user_id, Thread.user_high == user_id)\n                    )\n                )\n            )\n",
            )
        ],
        expect=[ALL_MINE],
    ),
    Case(
        id="t96-21-reports-about-them-exported",
        what="T-9.1, D-502: reports about the user exported",
        edits=[
            (
                ACCOUNT_REPO96,
                "            .where(Report.reporter_id == user_id)\n",
                "            .where(\n                or_(Report.reporter_id == user_id, Report.reported_id == user_id)\n            )\n",
            )
        ],
        expect=[ALL_MINE],
    ),
    Case(
        id="t96-22-the-ledgers-ref-exported",
        what="D-502: the ledger's ref_id, which can name the other person, exported",
        edits=[
            (
                ACCOUNT_REPO96,
                "                LedgerEntry.reason,\n",
                "                LedgerEntry.reason,\n                LedgerEntry.ref_id,\n",
            )
        ],
        expect=[ALL_MINE],
    ),
    Case(
        id="t96-23-the-phone-logged",
        what="rule 15: the export's phone number in its log line",
        edits=[
            (
                ACCOUNT96,
                '    log.info("export.ready", export_id=str(export_id), size=len(body))\n',
                '    log.info("export.ready", export_id=str(export_id), phone=document["account"]["phone"])\n',
            )
        ],
        expect=[ALL_MINE],
    ),
    Case(
        id="t96-24-the-link-outlives-the-file",
        what="D-502: every link signed for 24 hours, whenever it is read",
        edits=[
            (
                ACCOUNT96,
                "        ttl = max(1, int((export.expires_at - now).total_seconds()))\n",
                "        ttl = int(EXPORT_LINK.total_seconds())\n",
            )
        ],
        expect=["test_ready_for_24_hours_then_expired_and_its_file_deleted"],
    ),
    Case(
        id="t96-25-a-delete-taken-on-its-word",
        what="D-090: a file's deletion believed without reading it back",
        edits=[(ACCOUNT96, "    if remaining:\n", "    if False:\n")],
        expect=[
            "test_a_file_that_wont_go_is_never_called_gone",
            "test_a_file_that_wont_go_stops_that_account_and_the_next_run_finishes",
        ],
    ),
    Case(
        id="t96-26-a-typo-ignored",
        what="T-9.6: an unknown privacy switch silently ignored",
        edits=[
            (
                ACCOUNT_SCHEMAS96,
                '    model_config = ConfigDict(extra="forbid")\n',
                '    model_config = ConfigDict(extra="ignore")\n',
            )
        ],
        expect=["test_a_body_that_sets_nothing_known_is_refused"],
    ),
    Case(
        id="t96-27-yes-is-true",
        what="T-9.6: a privacy switch read leniently, 'yes' as true",
        edits=[
            (
                ACCOUNT_SCHEMAS96,
                "    is_hidden: StrictBool | None = None\n",
                "    is_hidden: bool | None = None\n",
            )
        ],
        expect=["test_a_body_that_sets_nothing_known_is_refused"],
    ),
    Case(
        id="t96-28-two-exports-at-once",
        what="D-502: asking again makes a second export",
        edits=[
            (
                ACCOUNT96,
                "        if latest is not None and _still_useful(latest, now):\n",
                "        if False:\n",
            )
        ],
        expect=["test_asking_queues_one_export_and_asking_again_returns_it"],
    ),
    Case(
        id="t96-29-exports-unlimited",
        what="D-502: no daily limit on asking",
        edits=[(ACCOUNT_ROUTER96, "EXPORTS_PER_DAY = 5\n", "EXPORTS_PER_DAY = 500\n")],
        expect=["test_five_asks_a_day_then_rate_limited"],
    ),
    Case(
        id="t96-30-the-number-kept",
        what="D-500: the erasure leaves the encrypted number",
        edits=[(ACCOUNT96, "    user.phone_enc = None\n", "")],
        expect=[ERASED_29],
    ),
    Case(
        id="t96-31-the-crons-hour",
        what="D-500: the daily job an hour late",
        edits=[
            (
                WORKER96,
                "ERASE_AT_UTC: Final = (22, 0)\n",
                "ERASE_AT_UTC: Final = (23, 0)\n",
            )
        ],
        expect=["test_the_erasure_runs_daily_at_0330_ist"],
    ),
    Case(
        id="t96-32-the-machines-clock",
        what="D-500: the cron's hours read in the machine's timezone",
        edits=[(WORKER96, "    timezone = UTC\n", "")],
        expect=["test_the_erasure_runs_daily_at_0330_ist"],
    ),
]


# --- P-47: app_config cached 60 s per app -------------------------------------------

P47: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="p47-01-never-expires",
            what="P-47: a cached setting kept past its minute",
            edits=[
                (
                    "app/modules/admin/service.py",
                    "        if held is not None and now - held[1] < CACHED_FOR:\n",
                    "        if held is not None:\n",
                )
            ],
            expect=["test_the_cache_holds_a_value_for_a_minute_then_reads_again"],
        ),
        ["tests/modules/admin/test_config_cache.py"],
    ),
    (
        Case(
            id="p47-02-never-held",
            what="P-47: the cache read through every time",
            edits=[
                (
                    "app/modules/admin/service.py",
                    "            return held[0]\n",
                    "            pass\n",
                )
            ],
            expect=["test_the_cache_holds_a_value_for_a_minute_then_reads_again"],
        ),
        ["tests/modules/admin/test_config_cache.py"],
    ),
    (
        Case(
            id="p47-03-one-per-process",
            what="P-47: one cache for every app in the process",
            edits=[
                (
                    "app/modules/admin/service.py",
                    "async def config_int(\n",
                    "PROCESS_CACHE = ConfigCache()\n\n\nasync def config_int(\n",
                ),
                (
                    "app/main.py",
                    "    app.state.config_cache = ConfigCache()\n",
                    "    from app.modules.admin.service import PROCESS_CACHE\n\n    app.state.config_cache = PROCESS_CACHE\n",
                ),
            ],
            expect=["test_each_app_has_a_cache_of_its_own"],
        ),
        ["tests/modules/admin/test_config_cache.py"],
    ),
    (
        Case(
            id="p47-04-a-bad-row-cached",
            what="P-47: a mistyped row cached before it is refused",
            edits=[
                (
                    "app/modules/admin/service.py",
                    "    value = await repository.config_value(session, key)\n    if type(value) is not int:",
                    "    value = await repository.config_value(session, key)\n    if cache is not None:\n        cache.values[key] = (value, now)\n    if type(value) is not int:",
                )
            ],
            expect=[
                "test_a_row_that_isnt_an_integer_is_refused_and_never_cached[true]"
            ],
        ),
        ["tests/modules/admin/test_config_cache.py"],
    ),
]

# --- T-6.4: swipes, the daily cap, the Super Like, the match --------------------------

T64: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t64-01-no-cap",
            what="the men's daily cap never refusing",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "        if await counter.take(redis, user_id, day, limit) is None:\n",
                    "        if await counter.take(redis, user_id, day, limit * 0 + 10**6) is None:\n",
                )
            ],
            expect=["test_the_cap_is_app_configs_and_the_next_swipe_is_refused"],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-02-no-place-given-back",
            what="a refused swipe keeping its place in the count",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "            await counter.give_back(redis, user_id, day)\n",
                    "            pass\n",
                )
            ],
            expect=[
                "test_a_swipe_not_written_gives_its_place_back[duplicate]",
                "test_a_swipe_not_written_gives_its_place_back[nobody]",
                "test_a_swipe_not_written_gives_its_place_back[blocked]",
            ],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-03-super-counted",
            what="D-492: a Super Like counted toward the cap",
            edits=[
                (
                    "app/modules/swipes/rules.py",
                    "COUNTED: Final = frozenset({SwipeDirection.LIKE, SwipeDirection.PASS})\n",
                    "COUNTED: Final = frozenset(SwipeDirection)\n",
                )
            ],
            expect=["test_a_super_like_doesnt_count_and_goes_past_the_cap"],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-04-women-capped",
            what="a woman given the men's cap",
            edits=[
                (
                    "app/modules/swipes/rules.py",
                    "    return gender is Gender.MALE\n",
                    "    return gender is not None\n",
                )
            ],
            expect=["test_a_woman_has_no_cap_and_no_count"],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-05-utc-day",
            what="the cap's day by UTC, not IST",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "    day = clock.today_ist()\n",
                    "    day = clock.now().date()\n",
                )
            ],
            expect=["test_the_count_starts_again_at_ist_midnight"],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-06-no-pair-lock",
            what="two likes at once each missing the other's",
            edits=[
                (
                    "app/modules/swipes/repository.py",
                    '            "SELECT pg_advisory_xact_lock(:lock, hashtext("\n',
                    '            "SELECT pg_advisory_xact_lock_shared(:lock, hashtext("\n',
                )
            ],
            expect=["test_two_likes_at_once_make_one_match"],
        ),
        ["tests/modules/swipes/test_race.py"],
    ),
    (
        Case(
            id="t64-07-woman-charged",
            what="D-002: a woman's Super Like debited",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "        await pricing_service.charge(\n            session,\n            user,\n            LedgerReason.SUPER_LIKE,\n            shown=shown_price,\n            ref=Ref(RefType.USER, target_id),\n        )\n",
                    "        from app.modules.wallet import service as wallet_service\n\n        await wallet_service.debit(\n            session, user.id, 5, LedgerReason.SUPER_LIKE, ref=Ref(RefType.USER, target_id)\n        )\n",
                )
            ],
            expect=["test_a_womans_super_like_is_free_and_writes_no_ledger_row"],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-08-super-free-for-men",
            what="a man's Super Like never charged",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "        await pricing_service.charge(\n            session,\n            user,\n            LedgerReason.SUPER_LIKE,\n            shown=shown_price,\n            ref=Ref(RefType.USER, target_id),\n        )\n",
                    "        pass\n",
                )
            ],
            expect=[
                "test_a_mans_super_like_debits_five_through_the_wallet",
                "test_a_super_like_he_cant_afford_is_402_and_writes_nothing",
            ],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-09-no-duplicate-check",
            what="a second swipe left to the primary key",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "    if await repository.direction_of(session, user.id, target_id) is not None:\n",
                    "    if False:\n",
                )
            ],
            expect=[
                "test_one_swipe_per_pair_ever[like-pass]",
                "test_a_second_super_like_is_already_exists_and_charges_once",
            ],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-10-match-on-a-pass",
            what="a pass taken as a like",
            edits=[
                (
                    "app/modules/swipes/rules.py",
                    "LIKES: Final = frozenset({SwipeDirection.LIKE, SwipeDirection.SUPER})\n",
                    "LIKES: Final = frozenset(SwipeDirection)\n",
                )
            ],
            expect=[
                "test_a_pass_either_way_makes_no_match[pass-like]",
                "test_a_pass_either_way_makes_no_match[like-pass]",
            ],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-11-anyone-swipeable",
            what="D-492: anyone swipeable, the feed's rule ignored",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "    if not await repository.is_swipeable(session, viewer, target_id):\n",
                    "    if False:\n",
                )
            ],
            expect=["test_nobody_the_feed_could_never_show_you_can_be_swiped"],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-12-seeking-ignored",
            what="D-492: a swipe on someone who doesn't want your gender",
            edits=[
                (
                    "app/modules/swipes/repository.py",
                    "        .where(User.id == target_id, *visible_to(viewer, mutual=True))\n",
                    "        .where(User.id == target_id, *visible_to(viewer, mutual=False))\n",
                )
            ],
            expect=["test_nobody_the_feed_could_never_show_you_can_be_swiped"],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-13-nobody-notified",
            what="a match with no notification",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "        await notifications_service.notify(session, one, Kind.MATCH, payload)\n",
                    "",
                )
            ],
            expect=["test_a_like_back_makes_one_match_and_tells_both[like-like]"],
        ),
        ["tests/modules/swipes/test_swipe.py"],
    ),
    (
        Case(
            id="t64-14-nothing-published",
            what="a match nobody's socket hears of",
            edits=[
                (
                    "app/modules/swipes/service.py",
                    "        events.queue(session, one, MATCH_CREATED, payload)\n",
                    "",
                )
            ],
            expect=["test_a_match_is_published_to_both"],
        ),
        ["tests/modules/swipes/test_race.py"],
    ),
]

# --- T-6.6: search and the username lookup ----------------------------------------

DISCOVERY_REPO = "app/modules/discovery/repository.py"
T66_SELECTION = [
    "tests/modules/discovery/test_search.py",
    "tests/modules/discovery/test_by_username.py",
]
GONE = "test_nobody_hidden_blocked_unfinished_or_held_back_is_found"

T66: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t66-01-wildcard",
            what="D-540: `_` and `%` in a search reaching LIKE unescaped",
            edits=[
                (
                    "app/modules/discovery/rules.py",
                    '    escaped = term.replace("\\\\", "\\\\\\\\").replace("%", "\\\\%").replace("_", "\\\\_")\n',
                    "    escaped = term\n",
                )
            ],
            expect=["test_an_underscore_is_a_character_never_a_wildcard"],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-02-at-search-unfiltered",
            what="`@` search without `visible_to`: blocked, hidden, inactive, yourself",
            edits=[
                (
                    DISCOVERY_REPO,
                    "            *visible_to(viewer, mutual=False),\n            Profile.username.ilike(",
                    "            Profile.username.ilike(",
                )
            ],
            expect=[
                f"{GONE}[@gone]",
                "test_only_active_accounts_are_found",
                "test_you_never_find_yourself",
            ],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-03-at-search-hidden-with-a-match",
            what="D-493: a hidden profile let into `@` search by a shared match",
            edits=[
                (
                    DISCOVERY_REPO,
                    "            *visible_to(viewer, mutual=False),\n            Profile.username.ilike(",
                    "            *visible_to(\n                viewer,\n                mutual=False,\n                hidden_ok=shares_a_match_or_thread(viewer.id, User.id),\n            ),\n            Profile.username.ilike(",
                )
            ],
            expect=[f"{GONE}[@gone]"],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-04-text-search-unfiltered",
            what="text search without `visible_to`",
            edits=[
                (
                    DISCOVERY_REPO,
                    "            *visible_to(viewer, mutual=True),\n            func.ST_DWithin(Profile.location, here, radius_m),\n            or_(*matches),",
                    "            func.ST_DWithin(Profile.location, here, radius_m),\n            or_(*matches),",
                )
            ],
            expect=[
                f"{GONE}[Gone]",
                "test_text_keeps_to_the_radius_and_to_who_wants_whom",
            ],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-05-text-search-not-mutual",
            what="text search past seeking, as `@` search is",
            edits=[
                (
                    DISCOVERY_REPO,
                    "            *visible_to(viewer, mutual=True),\n            func.ST_DWithin(Profile.location, here, radius_m),\n            or_(*matches),",
                    "            *visible_to(viewer, mutual=False),\n            func.ST_DWithin(Profile.location, here, radius_m),\n            or_(*matches),",
                )
            ],
            expect=["test_text_keeps_to_the_radius_and_to_who_wants_whom"],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-06-text-search-no-radius",
            what="text search across India",
            edits=[
                (
                    DISCOVERY_REPO,
                    "            *visible_to(viewer, mutual=True),\n            func.ST_DWithin(Profile.location, here, radius_m),\n            or_(*matches),",
                    "            *visible_to(viewer, mutual=True),\n            or_(*matches),",
                )
            ],
            expect=["test_text_keeps_to_the_radius_and_to_who_wants_whom"],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-07-raw-is-verified",
            what="D-393: a row's badge read from raw `is_verified`",
            edits=[
                (
                    DISCOVERY_REPO,
                    '            badge_of(User.id, User.is_verified).label("shows_badge"),\n',
                    '            User.is_verified.label("shows_badge"),\n',
                )
            ],
            expect=["test_the_badge_is_d393s_never_raw_is_verified"],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-08-similarity-unread",
            what="D-540: the trigram threshold not the one rules.py names",
            edits=[
                (
                    "app/modules/discovery/rules.py",
                    "SIMILARITY: Final = 0.3\n",
                    "SIMILARITY: Final = 0.9\n",
                )
            ],
            expect=["test_text_finds_names_near_and_alike"],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-09-by-username-a-prefix",
            what="the username lookup matching a pattern, not the name",
            edits=[
                (
                    DISCOVERY_REPO,
                    "        select(Profile.user_id).where(Profile.username == username)\n",
                    '        select(Profile.user_id).where(Profile.username.ilike(username + "%"))\n',
                )
            ],
            expect=["test_a_name_nobody_holds_is_not_found[ab_d]"],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-10-pair-ids-untyped",
            what="an id read back from a query reaching least() as text",
            edits=[
                (
                    DISCOVERY_REPO,
                    "    if isinstance(value, UUID):\n        return literal(value, PG_UUID(as_uuid=True))\n    return value\n",
                    "    return value\n",
                )
            ],
            expect=["test_a_username_opens_the_same_profile_as_its_id"],
        ),
        T66_SELECTION,
    ),
    (
        Case(
            id="t66-11-search-unlimited",
            what="search without its own rate limit",
            edits=[
                (
                    "app/modules/discovery/router.py",
                    "SEARCHES_PER_MINUTE = 60\n",
                    "SEARCHES_PER_MINUTE = 10**6\n",
                )
            ],
            expect=["test_search_is_limited_to_60_a_minute"],
        ),
        T66_SELECTION,
    ),
]

# --- T-8.2: the webhook, reversals, the bonus at capture, the poll -------------

WEBHOOKS = "app/modules/payments/webhooks.py"
REVERSAL_SHAPE = (
    "alembic/versions/20261008_fb0a7ce8dd16_ledger_shape_names_the_reversals.py"
)
SAFETY_SERVICE = "app/modules/safety/service.py"
T82_SELECTION = [
    "tests/modules/payments",
    "tests/modules/wallet/test_guards.py",
    "tests/modules/wallet/test_service.py",
    "tests/modules/wallet/test_reversal_reason_migration.py",
    "tests/modules/pricing/test_debit_callers.py",
    "tests/core/test_razorpay.py",
    "tests/modules/e2e/test_payments_simulator.py",
]
MISMATCH = "test_an_amount_or_currency_not_the_rows_credits_nothing"

T82: list[Case] = [
    Case(
        id="t82-01-signature-skipped",
        what="the webhook applied without its signature checked",
        edits=[
            (
                WEBHOOKS,
                "    if signature is None or not payments.verify_webhook(body, signature):\n",
                "    if False:\n",
            )
        ],
        expect=[
            "test_a_bad_or_missing_signature_credits_nothing[bad]",
            "test_a_bad_or_missing_signature_credits_nothing[missing]",
        ],
    ),
    Case(
        id="t82-02-repeat-not-checked",
        what="D-026: a capture applied again when the anchor is already its own",
        edits=[
            (
                WEBHOOKS,
                "    if row.provider_payment_id is not None:\n        if row.provider_payment_id == payment.id:\n",
                "    if row.provider_payment_id not in (None, payment.id):\n        if False:\n",
            )
        ],
        expect=[
            "test_one_webhook_delivered_five_times_at_once_is_credited_once",
            "test_the_same_capture_again_is_a_repeat",
        ],
    ),
    Case(
        id="t82-03-row-lock-dropped",
        what="D-026: the payment row read without FOR UPDATE",
        edits=[
            (
                PAY_REPO,
                "select(Payment).with_for_update().execution_options(",
                "select(Payment).execution_options(",
            )
        ],
        expect=["test_one_webhook_delivered_five_times_at_once_is_credited_once"],
    ),
    Case(
        id="t82-04-bonus-decided-before-the-wallet-lock",
        what="P-380: the bonus decided before the wallet is locked",
        edits=[
            (
                WEBHOOKS,
                "    ref = Ref(RefType.PAYMENT, row.id)\n    # The wallet's lock is held from here to the commit (D-077).\n",
                "    ref = Ref(RefType.PAYMENT, row.id)\n    bought = await repository.bought_other_than(session, row.user_id, row.id)\n",
            ),
            (
                WEBHOOKS,
                "        if await repository.bought_other_than(session, row.user_id, row.id):\n",
                "        if bought:\n",
            ),
        ],
        expect=["test_two_orders_captured_at_once_grant_the_bonus_once"],
    ),
    Case(
        id="t82-05-the-webhooks-amount-trusted",
        what="rule 6: the webhook's amount taken for the row's",
        edits=[
            (
                WEBHOOKS,
                "    if payment.amount != row.amount_paise or payment.currency != CURRENCY:\n",
                "    row.amount_paise = payment.amount\n    if payment.amount != row.amount_paise or payment.currency != CURRENCY:\n",
            )
        ],
        expect=[f"{MISMATCH}[change0]", f"{MISMATCH}[change1]"],
    ),
    Case(
        id="t82-06-the-amount-not-checked",
        what="rule 6: a capture credited whatever its amount",
        edits=[
            (
                WEBHOOKS,
                "    if payment.amount != row.amount_paise or payment.currency != CURRENCY:\n",
                "    if payment.currency != CURRENCY:\n",
            )
        ],
        expect=[f"{MISMATCH}[change0]", f"{MISMATCH}[change1]"],
    ),
    Case(
        id="t82-07-a-womans-capture-not-refused",
        what="D-076: the service's own check that the owner is a man removed",
        edits=[
            (
                WEBHOOKS,
                "    if await repository.owner_gender(session, row.user_id) is not Gender.MALE:\n",
                "    if False:\n",
            )
        ],
        expect=["test_a_womans_payment_is_never_credited"],
    ),
    Case(
        id="t82-08-a-failed-attempt-sets-the-anchor",
        what="D-523: payment.failed sets provider_payment_id",
        edits=[
            (
                WEBHOOKS,
                '        row.status = PaymentStatus.FAILED\n        row.raw_webhook = event.raw\n        log.info("payments.failed"',
                '        row.status = PaymentStatus.FAILED\n        row.provider_payment_id = event.payment.id\n        row.raw_webhook = event.raw\n        log.info("payments.failed"',
            )
        ],
        expect=["test_a_failed_attempt_then_a_capture_is_paid_and_credited"],
    ),
    Case(
        id="t82-09-raw-webhook-by-strip-list",
        what="D-524: raw_webhook built by stripping payer fields, not by an allowlist",
        edits=[
            (
                WEBHOOKS,
                "            kept[name] = {key: entity[key] for key in keys if key in entity}\n",
                '            kept[name] = {key: value for key, value in entity.items() if key not in ("email", "contact", "vpa", "card_id", "card", "bank", "wallet", "acquirer_data", "notes", "description", "fee", "tax")}\n',
            )
        ],
        expect=["test_raw_webhook_keeps_exactly_the_allowlisted_fields"],
    ),
    Case(
        id="t82-10-reversed-only-when-processed",
        what="D-520: the Velas taken back at refund.processed, not refund.created",
        edits=[
            (
                WEBHOOKS,
                "    if event.name in REVERSE:\n        return await _reverse(session, row, event)\n",
                '    if event.name == "refund.created":\n        return Outcome.NOTHING_TO_DO\n    if event.name in REVERSE:\n        return await _reverse(session, row, event)\n',
            )
        ],
        expect=["test_a_refund_created_takes_the_velas_back_and_the_status_stays_paid"],
    ),
    Case(
        id="t82-11-a-restore-gives-back-the-whole-payment",
        what="D-520: a restore gives back the payment's Velas, not what its reversal took",
        edits=[
            (
                WEBHOOKS,
                "        -reversal.delta,\n        LedgerReason.PURCHASE_RESTORED,\n",
                "        row.credits + row.bonus_credits,\n        LedgerReason.PURCHASE_RESTORED,\n",
            )
        ],
        expect=[
            "test_a_restore_after_a_partial_reversal_gives_back_only_what_was_taken"
        ],
    ),
    Case(
        id="t82-12-a-reversal-refused-on-a-low-balance",
        what="D-520: reverse() refuses a low balance, as debit() does",
        edits=[
            (
                SERVICE,
                "    if at_most:\n        amount = min(balance, amount)\n",
                "    if False:\n        amount = min(balance, amount)\n",
            )
        ],
        expect=[
            "test_a_reversal_takes_at_most_the_balance_and_never_refuses",
            "test_velas_partly_spent_take_what_is_left_and_record_the_rest[refund]",
            "test_velas_partly_spent_take_what_is_left_and_record_the_rest[dispute]",
        ],
    ),
    Case(
        id="t82-13-a-refund-before-its-capture-ignored",
        what="D-523: a refund reaching an uncaptured order not captured first",
        edits=[
            (
                WEBHOOKS,
                "    if row.provider_payment_id is None:\n        await _capture(session, row, event)\n",
                "",
            )
        ],
        expect=[
            "test_a_refund_before_its_capture_captures_then_reverses[refund.created]",
            "test_a_refund_before_its_capture_captures_then_reverses[refund.processed]",
        ],
    ),
    Case(
        id="t82-14-a-dispute-refunded-at-creation",
        what="D-520, D-483: a dispute marks the payment refunded before it is lost",
        edits=[
            (
                WEBHOOKS,
                "    outcome = await _reverse_once(session, row, event)\n",
                '    outcome = await _reverse_once(session, row, event)\n    if event.kind == "dispute":\n        row.status = PaymentStatus.REFUNDED\n',
            )
        ],
        expect=[
            "test_turnover_drops_a_refund_and_keeps_a_dispute_not_yet_lost",
            "test_a_dispute_reverses_then_a_win_restores",
        ],
    ),
    Case(
        id="t82-15-the-poll-serves-anyones-payment",
        what="GET /payments/{id} answers for a payment that isn't the caller's",
        edits=[
            (
                PAY_SERVICE,
                "        if payment is None or payment.user_id != user.id:\n",
                "        if payment is None:\n",
            )
        ],
        expect=["test_someone_elses_payment_is_not_found_as_none_is"],
    ),
    Case(
        id="t82-16-the-direction-check-widened",
        what="D-521: purchase_restored allowed as a debit too",
        edits=[
            (
                REVERSAL_SHAPE,
                'DEBITS = (*DEBITS_BEFORE, "purchase_reversal")\n',
                'DEBITS = (*DEBITS_BEFORE, "purchase_reversal", "purchase_restored")\n',
            )
        ],
        expect=["test_each_reason_has_one_direction_in_the_database"],
    ),
    Case(
        id="t82-17-reverse-called-elsewhere",
        what="D-520: something but the webhook's reversal reaches reverse()",
        edits=[
            (
                SAFETY_SERVICE,
                "CHARGEBACK_SHORTFALL_WEIGHT: Final = fraud.WEIGHTS[fraud.CHARGEBACK_SHORTFALL]\n",
                'CHARGEBACK_SHORTFALL_WEIGHT: Final = fraud.WEIGHTS[fraud.CHARGEBACK_SHORTFALL]\n\n\nasync def _take(session, user_id):\n    from app.modules.wallet import service as wallet_service\n\n    await wallet_service.reverse(session, user_id, 5, "purchase_reversal", ref=None, event="x")\n',
            )
        ],
        expect=["test_only_the_webhooks_reversal_reaches_reverse"],
    ),
    Case(
        id="t82-18-verified-without-a-secret",
        what="P-382: verify_webhook says yes when RAZORPAY_WEBHOOK_SECRET isn't set",
        edits=[
            (
                RAZORPAY,
                "            return False\n        return _signed_by(self._webhook_secret.encode(), body, signature)\n",
                "            return True\n        return _signed_by(self._webhook_secret.encode(), body, signature)\n",
            )
        ],
        expect=[
            "test_without_the_secret_every_signature_is_refused_naming_the_setting",
            "test_with_razorpay_and_no_secret_every_webhook_is_refused",
        ],
    ),
]

# --- T-7.1: opening a Thread -----------------------------------------------------

T71_SELECTION = [
    "tests/modules/threads",
    "tests/modules/messages",
    "tests/test_schema.py",
]
THREADS_SERVICE = "app/modules/threads/service.py"
THREADS_RULES = "app/modules/threads/rules.py"
MESSAGES_SERVICE = "app/modules/messages/service.py"
FILTERS = "app/modules/messages/filters.py"
LIMITS = "app/modules/messages/limits.py"
DM_MIGRATION = (
    "alembic/versions/20261008_ddf84381ef6c_private_message_threads_never_expire.py"
)

T71: list[Case] = [
    Case(
        id="t71-01-no-pair-lock",
        what="opening without the pair's lock",
        edits=[
            (
                THREADS_SERVICE,
                "    await repository.lock_pair(session, user.id, other_id)\n",
                "    pass  # no lock\n",
            )
        ],
        expect=["test_a_double_tap_opens_one_thread_and_charges_once"],
    ),
    Case(
        id="t71-02-no-existing-thread",
        what="a second open never finding the first's Thread",
        edits=[
            (
                THREADS_SERVICE,
                "    if existing is not None:\n",
                "    if existing is not None and False:\n",
            )
        ],
        expect=[
            "test_a_second_open_returns_the_thread_and_charges_nothing",
            "test_an_expired_thread_refuses_him",
            "test_a_live_thread_is_returned_and_its_match_pointed_at_it",
        ],
    ),
    Case(
        id="t71-03-expired-lets-him-through",
        what="an expired Thread letting a man through",
        edits=[
            (
                THREADS_RULES,
                "    return gender is Gender.FEMALE\n",
                "    return True\n",
            )
        ],
        expect=["test_an_expired_thread_refuses_him"],
    ),
    Case(
        id="t71-04-no-charge",
        what="opening without the charge",
        edits=[
            (
                THREADS_SERVICE,
                (
                    "    await pricing_service.charge(\n"
                    "        session,\n"
                    "        user,\n"
                    "        rules.OPEN_PRICE[origin],\n"
                ),
                (
                    "    None and await pricing_service.charge(\n"
                    "        session,\n"
                    "        user,\n"
                    "        rules.OPEN_PRICE[origin],\n"
                ),
            )
        ],
        expect=[
            "test_a_man_opens_from_a_match_for_five_and_she_is_told",
            "test_a_private_message_costs_him_eight_and_never_expires",
            "test_a_man_without_the_velas_opens_nothing",
        ],
    ),
    Case(
        id="t71-05-dm-at-the-match-price",
        what="a private message charged as a Thread from a match",
        edits=[
            (
                THREADS_RULES,
                "    ThreadOrigin.DM: LedgerReason.DM_OPEN,\n",
                "    ThreadOrigin.DM: LedgerReason.THREAD_OPEN,\n",
            )
        ],
        expect=["test_a_private_message_costs_him_eight_and_never_expires"],
    ),
    Case(
        id="t71-06-countdown-to-her",
        what="her side shown the expiry",
        edits=[
            (
                THREADS_RULES,
                (
                    '    """Whether `expires_at` is shown to this person: a man (D-554)."""\n'
                    "    return gender is Gender.MALE\n"
                ),
                (
                    '    """Whether `expires_at` is shown to this person: a man (D-554)."""\n'
                    "    return True\n"
                ),
            )
        ],
        expect=["test_a_woman_opens_free_and_sees_no_countdown"],
    ),
    Case(
        id="t71-07-hours-written-in",
        what="24 hours written into the code, not read from thread_hours",
        edits=[
            (
                THREADS_RULES,
                "        return None\n    return now + timedelta(hours=hours)\n",
                "        return None\n    return now + timedelta(hours=24)\n",
            )
        ],
        expect=["test_the_hours_are_the_settings_never_a_number"],
    ),
    Case(
        id="t71-08-dm-not-mutual",
        what="a private message to someone who doesn't want your gender",
        edits=[
            (
                THREADS_SERVICE,
                "        other_id, mutual = request.user_id, True\n",
                "        other_id, mutual = request.user_id, False\n",
            ),
            (
                THREADS_SERVICE,
                "        session, user, other_id, mutual=origin is ThreadOrigin.DM\n",
                "        session, user, other_id, mutual=False\n",
            ),
        ],
        expect=["test_a_private_message_needs_her_to_want_his_gender"],
    ),
    Case(
        id="t71-09-match-not-pointed",
        what="a new Thread's match left pointing at nothing",
        edits=[
            (
                THREADS_SERVICE,
                "        await repository.link_match(session, match.id, thread.id)\n",
                "        pass\n",
            )
        ],
        expect=["test_a_man_opens_from_a_match_for_five_and_she_is_told"],
    ),
    Case(
        id="t71-10-she-isnt-told",
        what="the other person never told",
        edits=[
            (
                THREADS_SERVICE,
                "    events.queue(session, other_id, THREAD_OPENED, payload)\n",
                "    pass\n",
            )
        ],
        expect=[
            "test_a_man_opens_from_a_match_for_five_and_she_is_told",
            "test_a_private_message_costs_him_eight_and_never_expires",
        ],
    ),
    Case(
        id="t71-11-first-message-unmasked",
        what="the first message never masked",
        edits=[
            (
                MESSAGES_SERVICE,
                "        if thread.message_count < mask_first_n\n",
                "        if False\n",
            )
        ],
        expect=["test_a_private_message_costs_him_eight_and_never_expires"],
    ),
    Case(
        id="t71-12-rejection-forgotten",
        what="a refused message leaving no signal",
        edits=[
            (
                MESSAGES_SERVICE,
                "        safety_service.record_message_rejected(session, user_id, rule=rule)\n",
                "        pass\n",
            )
        ],
        expect=["test_a_rejected_first_message_opens_nothing_and_is_recorded"],
    ),
    Case(
        id="t71-13-abuse-word-dropped",
        what="a word gone from the abuse list",
        edits=[(FILTERS, r'r"\b(bitch|slut', r'r"\b(slut')],
        expect=["test_abuse_and_asking_for_money_are_refused"],
    ),
    Case(
        id="t71-14-no-new-men-limit",
        what="a woman's new-men limit never taken",
        edits=[
            (
                THREADS_SERVICE,
                "        if new_men is not None:\n",
                "        if new_men is not None and False:\n",
            )
        ],
        expect=["test_she_opens_with_so_many_new_men_a_day"],
    ),
    Case(
        id="t71-15-no-private-message-limit",
        what="a woman's private-message limit never taken",
        edits=[
            (
                THREADS_SERVICE,
                "        if private is not None:\n",
                "        if private is not None and False:\n",
            )
        ],
        expect=["test_she_sends_so_many_private_messages_a_day"],
    ),
    Case(
        id="t71-16-places-kept",
        what="a failed open keeping her places",
        edits=[
            (
                THREADS_SERVICE,
                "    except BaseException:\n        await taken.give_back()\n        raise\n",
                "    except BaseException:\n        raise\n",
            )
        ],
        expect=["test_her_places_come_back_when_nothing_is_written"],
    ),
    Case(
        id="t71-17-every-woman-a-man",
        what="a woman counted among her 30 men",
        edits=[(LIMITS, "    return gender is Gender.MALE\n", "    return True\n")],
        expect=["test_men_and_women_to_women_have_no_such_limit"],
    ),
    Case(
        id="t71-18-dm-must-expire",
        what="the CHECK still saying every active Thread expires",
        edits=[
            (
                DM_MIGRATION,
                """AFTER = "status <> 'active' OR expires_at IS NOT NULL OR origin = 'dm'"\n""",
                """AFTER = "status <> 'active' OR expires_at IS NOT NULL"\n""",
            )
        ],
        expect=[
            "test_an_active_private_message_never_expires",
            "test_a_private_message_costs_him_eight_and_never_expires",
        ],
    ),
    Case(
        id="t71-19-downgrade-invents-nothing",
        what="the downgrade not refusing over an active private message",
        edits=[(DM_MIGRATION, "    if never_expiring:\n", "    if False:\n")],
        expect=["test_going_back_refuses_while_a_private_message_is_active"],
    ),
    Case(
        id="t71-20-bare-transfer",
        what="the bare word transfer refused, as the prototype did",
        edits=[
            (
                FILTERS,
                r'    r"\b(paytm|gpay',
                r'    r"\btransfer\b|\b(paytm|gpay',
            )
        ],
        expect=["test_ordinary_sentences_are_not_refused"],
    ),
]

# --- T-8.11: welcome Velas, once per number ---------------------------------------

ONBOARDING_SERVICE = "app/modules/onboarding/service.py"
ONBOARDING_RULES = "app/modules/onboarding/rules.py"
ONBOARDING_REPO = "app/modules/onboarding/repository.py"
WELCOME_REASON = "alembic/versions/20261008_acfda05a9f20_ledger_reason_for_welcome.py"
WELCOME_SHAPE = "alembic/versions/20261008_a7e4f06d6b3f_ledger_shape_names_welcome.py"
WELCOME_GRANTS = "alembic/versions/20261008_39e51f5fb85a_welcome_grants.py"
WELCOME_SETTING = "alembic/versions/20261008_105ae9a99be1_welcome_velas.py"
ERASURE = "app/modules/account/erasure.py"
USERS_REPO = "app/modules/users/repository.py"
T811_SELECTION = [
    "tests/modules/onboarding",
    "tests/modules/wallet/test_guards.py",
    "tests/modules/wallet/test_welcome_reason_migration.py",
    "tests/modules/account/test_erasure.py",
    "tests/modules/users/test_dob_gender.py",
    "tests/test_app_role.py",
    "tests/test_reference_data.py",
]
SKIPS = "test_a_missing_or_broken_setting_skips_with_a_warning_and_never_fails_sign_up"
RE_SIGN_UP = "test_grant_delete_wait_out_the_erasure_sign_up_again_is_no_second_grant"

T811: list[Case] = [
    Case(
        id="t811-01-a-woman-credited",
        what="D-470, D-076: the grant's allowlist lets a woman through",
        edits=[
            (
                ONBOARDING_RULES,
                "WELCOME_GENDERS: Final = frozenset({Gender.MALE})\n",
                "WELCOME_GENDERS: Final = frozenset({Gender.MALE, Gender.FEMALE})\n",
            )
        ],
        expect=["test_a_woman_finishing_gets_nothing_and_finishes"],
    ),
    Case(
        id="t811-02-zero-credited",
        what="D-470: welcome_velas at 0 still reaches credit()",
        edits=[(ONBOARDING_SERVICE, "    if amount <= 0:\n", "    if amount < 0:\n")],
        expect=["test_welcome_velas_at_zero_gives_nothing"],
    ),
    Case(
        id="t811-03-missing-row-fails-sign-up",
        what="D-530: a missing welcome_velas row fails the sign-up",
        edits=[
            (
                ONBOARDING_SERVICE,
                "    except admin_service.MissingConfig:\n",
                "    except LookupError:\n",
            )
        ],
        expect=[f"{SKIPS}[no row]", f"{SKIPS}[not a number]"],
    ),
    Case(
        id="t811-04-claim-ignored",
        what="P-371: a number already given its welcome is credited again",
        edits=[
            (
                ONBOARDING_SERVICE,
                "    if not await repository.claim_welcome(session, user.phone_hash, user.id):\n",
                "    if not await repository.claim_welcome(session, user.phone_hash, user.id) and False:\n",
            )
        ],
        expect=[RE_SIGN_UP, "test_a_number_already_claimed_gets_nothing"],
    ),
    Case(
        id="t811-05-claim-not-one-statement",
        what="P-371: the claim inserts without ON CONFLICT, so a claimed number fails",
        edits=[
            (
                ONBOARDING_REPO,
                "        .on_conflict_do_nothing(index_elements=[WelcomeGrant.phone_hash])\n",
                "",
            )
        ],
        expect=[
            RE_SIGN_UP,
            "test_a_number_already_claimed_gets_nothing",
            "test_two_completions_overlapping_are_one_grant",
        ],
    ),
    Case(
        id="t811-06-welcome-not-a-credit",
        what="D-077: the direction CHECK left without welcome",
        edits=[
            (
                WELCOME_SHAPE,
                'CREDITS = (*CREDITS_BEFORE, "welcome")\n',
                "CREDITS = CREDITS_BEFORE\n",
            )
        ],
        expect=[
            "test_each_reason_has_one_direction_in_the_database",
            "test_a_man_finishing_gets_five_velas_once",
        ],
    ),
    Case(
        id="t811-07-welcome-repeats",
        what="D-470: welcome left out of the one-per-event index",
        edits=[
            (
                WELCOME_SHAPE,
                '    "purchase_restored",\n)\n\nCREDITS =',
                '    "purchase_restored",\n    "welcome",\n)\n\nCREDITS =',
            )
        ],
        expect=["test_one_entry_per_event_except_the_reasons_that_repeat"],
    ),
    Case(
        id="t811-08-reason-downgrade-unrefused",
        what="D-470: the reason's downgrade runs with a welcome row in the ledger",
        edits=[(WELCOME_REASON, "    if used:\n", "    if False:\n")],
        expect=["test_the_reason_refuses_to_go_down_once_the_ledger_holds_one"],
    ),
    Case(
        id="t811-09-table-downgrade-unrefused",
        what="P-371: welcome_grants dropped while it holds numbers",
        edits=[(WELCOME_GRANTS, "    if held:\n", "    if False:\n")],
        expect=["test_the_table_refuses_to_go_down_while_it_holds_a_number"],
    ),
    Case(
        id="t811-10-triggers-dropped",
        what="P-371: welcome_grants without refuse_change()",
        edits=[
            (
                WELCOME_GRANTS,
                "    for name, when, level in GUARDS:\n",
                "    for name, when, level in ():\n",
            )
        ],
        expect=[
            "test_a_welcome_once_recorded_is_never_changed_or_removed[update]",
            "test_a_welcome_once_recorded_is_never_changed_or_removed[delete]",
            "test_a_welcome_once_recorded_is_never_changed_or_removed[truncate]",
        ],
    ),
    Case(
        id="t811-11-app-role-may-delete",
        what="P-371: the app role keeps UPDATE and DELETE on welcome_grants",
        edits=[
            (
                WELCOME_GRANTS,
                '    op.execute(sa.text(f"revoke update, delete on welcome_grants from {APP_ROLE}"))\n',
                "",
            )
        ],
        expect=[
            "test_guarded_writes_are_refused[welcome_grants-update",
            "test_guarded_writes_are_refused[welcome_grants-delete",
            "test_no_refuse_change_trigger_is_reachable_by_the_app_role",
        ],
    ),
    Case(
        id="t811-12-erasure-erases-the-hash",
        what="P-371: the erasure lists welcome_grants among what it deletes",
        edits=[
            (
                ERASURE,
                "from app.modules.photos.models import Photo\n",
                (
                    "from app.modules.onboarding.models import WelcomeGrant\n"
                    "from app.modules.photos.models import Photo\n"
                ),
            ),
            (
                ERASURE,
                '    Erased(Session, ("user_id",)),\n',
                '    Erased(Session, ("user_id",)),\n    Erased(WelcomeGrant, ("user_id",)),\n',
            ),
        ],
        expect=[
            "test_every_column_keyed_to_users_is_erased_or_kept",
            "test_the_welcome_hash_is_kept",
            RE_SIGN_UP,
        ],
    ),
    Case(
        id="t811-13-under-18-split-forgets-it",
        what="D-072, D-078: welcome_grants dropped from UNDERAGE_KEEPS",
        edits=[
            (
                USERS_REPO,
                '    "welcome_grants": "given at done, after dob (D-470); a number\'s welcome, kept",\n',
                "",
            )
        ],
        expect=["test_every_table_keyed_to_users_is_one_d072_deletes_or_one_it_keeps"],
    ),
    Case(
        id="t811-14-the-setting-lost",
        what="D-530: the data migration seeds no welcome_velas row",
        edits=[
            (
                WELCOME_SETTING,
                'WELCOME_VELAS = ("welcome_velas", 5)\n',
                'WELCOME_VELAS = ("welcome_velas_lost", 5)\n',
            )
        ],
        expect=["test_app_config_seeds", "test_a_man_finishing_gets_five_velas_once"],
    ),
    Case(
        id="t811-15-the-race-commits-a-welcome",
        what="tests/committed.py: the onboarding race test commits a welcome row",
        edits=[
            (
                "tests/modules/onboarding/test_race.py",
                "            return 0  # nothing committed that can't be taken back (above)\n",
                "            pass\n",
            )
        ],
        expect=["test_finishing_waits_for_the_photos_decision"],
    ),
]

# --- T-7.2: the Thread list ---------------------------------------------------------

T72_SELECTION = ["tests/modules/threads/test_list.py"]
THREADS_REPOSITORY = "app/modules/threads/repository.py"

T72: list[Case] = [
    Case(
        id="t72-01-anyones-threads",
        what="the list not asking whose Threads",
        edits=[
            (
                THREADS_REPOSITORY,
                # `_listed` since T-9.8, which the list and the cleared list share.
                (
                    "            or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),\n"
                    "            ~blocked_either_way(viewer_id, other.id),\n"
                ),
                "            ~blocked_either_way(viewer_id, other.id),\n",
            )
        ],
        expect=["test_my_threads_newest_first_with_their_preview_and_unread"],
    ),
    Case(
        id="t72-02-cleared-shown",
        what="a cleared Thread shown with nothing newer",
        edits=[
            (
                THREADS_REPOSITORY,
                "            or_(cleared.is_(None), Thread.last_message_at > cleared),\n",
                "            true(),\n",
            )
        ],
        expect=["test_a_cleared_thread_hides_for_me_alone_until_something_newer"],
    ),
    Case(
        id="t72-03-blocked-listed",
        what="a blocked Thread listed",
        edits=[
            (
                THREADS_REPOSITORY,
                "            ~blocked_either_way(viewer_id, other.id),\n",
                "            true(),\n",
            )
        ],
        expect=["test_a_block_either_way_hides_the_thread"],
    ),
    Case(
        id="t72-04-blocked-read",
        what="a blocked Thread read by its id",
        edits=[
            (
                THREADS_REPOSITORY,
                "        ~blocked_either_way(viewer_id, _other(viewer_id)),\n    )\n    if lock:\n",
                "        true(),\n    )\n    if lock:\n",
            )
        ],
        expect=["test_a_block_either_way_hides_the_thread"],
    ),
    Case(
        id="t72-05-my-own-unread",
        what="my own messages counted as unread",
        edits=[
            (THREADS_REPOSITORY, "            Message.sender_id != viewer_id,\n", "")
        ],
        expect=[
            "test_my_threads_newest_first_with_their_preview_and_unread",
            "test_unread_keeps_those_with_something_unread",
        ],
    ),
    Case(
        id="t72-06-unread-before-clearing",
        what="messages before my clearing counted as unread",
        edits=[
            (
                THREADS_REPOSITORY,
                "            or_(cleared.is_(None), Message.created_at > cleared),\n",
                "",
            )
        ],
        expect=["test_a_cleared_thread_hides_for_me_alone_until_something_newer"],
    ),
    Case(
        id="t72-07-deleted-named",
        what="a deleted account's name shown",
        edits=[
            (
                "app/modules/threads/service.py",
                "        first_name=None if deleted else row.other_first_name,\n",
                "        first_name=row.other_first_name,\n",
            )
        ],
        expect=["test_a_deleted_account_is_named_as_one_and_nothing_more"],
    ),
    Case(
        id="t72-08-deleted-searchable",
        what="a deleted account found by its old name",
        edits=[
            (
                THREADS_REPOSITORY,
                "            other.status != UserStatus.DELETED,\n",
                "",
            )
        ],
        expect=["test_a_deleted_account_is_named_as_one_and_nothing_more"],
    ),
    Case(
        id="t72-09-q-a-pattern",
        what="q read as an ILIKE pattern",
        edits=[
            (
                THREADS_REPOSITORY,
                '    return f"%{escaped}%"\n',
                '    return f"%{text_}%"\n',
            )
        ],
        expect=["test_q_finds_their_name_or_username_anywhere_in_it"],
    ),
    Case(
        id="t72-10-recent-four-days",
        what="recent stretched past three days",
        edits=[
            (
                "app/modules/threads/rules.py",
                "RECENT_FOR: Final = timedelta(days=3)\n",
                "RECENT_FOR: Final = timedelta(days=4)\n",
            )
        ],
        expect=["test_recent_is_a_message_in_the_last_three_days"],
    ),
    Case(
        id="t72-11-whole-preview",
        what="a preview of the whole message",
        edits=[
            (
                "app/modules/threads/rules.py",
                "PREVIEW_CHARS: Final = 100\n",
                "PREVIEW_CHARS: Final = 1000\n",
            )
        ],
        expect=["test_a_preview_is_a_texts_first_hundred_characters"],
    ),
    Case(
        id="t72-12-knots-with-threads",
        what="the Knots tier holding Threads",
        edits=[
            (
                THREADS_REPOSITORY,
                "        [ThreadStatus.KNOTTED]\n",
                "        [ThreadStatus.KNOTTED, ThreadStatus.ACTIVE]\n",
            )
        ],
        expect=["test_threads_and_knots_are_separate_tiers"],
    ),
    Case(
        id="t72-13-anyones-thread-read",
        what="anyone's Thread read by its id",
        edits=[
            (
                THREADS_REPOSITORY,
                (
                    "        Thread.id == thread_id,\n"
                    "        or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),\n"
                ),
                "        Thread.id == thread_id,\n",
            )
        ],
        expect=["test_one_thread_is_mine_to_read_and_nobody_elses"],
    ),
    Case(
        id="t72-14-cursor-ignored",
        what="the cursor never applied",
        edits=[
            (
                THREADS_REPOSITORY,
                "        query = query.where(tuple_(key, Thread.id) < after)\n",
                "        pass\n",
            )
        ],
        expect=["test_pages_follow_the_cursor"],
    ),
]

# --- T-7.3: messages --------------------------------------------------------------

T73_SELECTION = ["tests/modules/messages", "tests/modules/threads/test_open.py"]
MESSAGES_RULES = "app/modules/messages/rules.py"
MESSAGES_REPOSITORY = "app/modules/messages/repository.py"

T73: list[Case] = [
    Case(
        id="t73-01-his-send-on-expired",
        what="an expired Thread taking his send",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if expired and not threads_rules.passes_an_expired_thread(user.gender):\n",
                "    if False:\n",
            )
        ],
        expect=["test_an_expired_thread_refuses_him_and_takes_hers_moving_nothing"],
    ),
    Case(
        id="t73-02-expiry-by-status-alone",
        what="expiry read from the status column, never the clock",
        edits=[
            (
                THREADS_RULES,
                (
                    "    return (\n"
                    "        thread.status is ThreadStatus.ACTIVE\n"
                    "        and thread.expires_at is not None\n"
                    "        and thread.expires_at <= now\n"
                    "    )\n"
                ),
                "    return False\n",
            )
        ],
        expect=[
            "test_an_expired_thread_refuses_him_and_takes_hers_moving_nothing",
            "test_a_thread_past_its_hour_refuses_him_before_the_cron",
        ],
    ),
    Case(
        id="t73-03-his-message-moves-the-hour",
        what="his message moving the hour on",
        edits=[
            (
                THREADS_RULES,
                "        gender is Gender.FEMALE\n        and thread.status",
                "        gender is not None\n        and thread.status",
            )
        ],
        expect=["test_his_message_never_moves_the_hour"],
    ),
    Case(
        id="t73-04-her-message-moves-nothing",
        what="her message never moving the hour",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if not expired and threads_rules.restarts_the_hour(thread, user.gender):\n",
                "    if False:\n",
            )
        ],
        expect=["test_her_message_moves_the_hour_on_and_clears_the_warning"],
    ),
    Case(
        id="t73-05-her-message-revives",
        what="her message reviving a Thread past its hour",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if not expired and threads_rules.restarts_the_hour(thread, user.gender):\n",
                "    if threads_rules.restarts_the_hour(thread, user.gender):\n",
            )
        ],
        expect=["test_an_expired_thread_refuses_him_and_takes_hers_moving_nothing"],
    ),
    Case(
        id="t73-06-hour-cut-short",
        what="her message cutting a longer hour short",
        edits=[
            (
                MESSAGES_SERVICE,
                "        if thread.expires_at is None or later > thread.expires_at:\n",
                "        if True:\n",
            )
        ],
        expect=["test_her_message_never_cuts_a_longer_hour_short"],
    ),
    Case(
        id="t73-07-warning-kept",
        what="a moved hour keeping its old warning",
        edits=[
            (
                MESSAGES_SERVICE,
                "            thread.expiry_warned_at = None\n",
                "            pass\n",
            )
        ],
        expect=["test_her_message_moves_the_hour_on_and_clears_the_warning"],
    ),
    Case(
        id="t73-08-answering-free",
        what="his first message in her Thread free",
        edits=[
            (
                MESSAGES_RULES,
                "    return LedgerReason.THREAD_REOPEN if they_wrote else LedgerReason.THREAD_OPEN\n",
                "    return None\n",
            )
        ],
        expect=[
            "test_answering_her_costs_him_the_re_open_once",
            "test_writing_first_where_she_opened_costs_him_the_open",
        ],
    ),
    Case(
        id="t73-09-answering-at-the-open-price",
        what="answering her charged as opening",
        edits=[
            (
                MESSAGES_RULES,
                "    return LedgerReason.THREAD_REOPEN if they_wrote else LedgerReason.THREAD_OPEN\n",
                "    return LedgerReason.THREAD_OPEN\n",
            )
        ],
        expect=["test_answering_her_costs_him_the_re_open_once"],
    ),
    Case(
        id="t73-10-private-messages-free",
        what="a private message after the first free",
        edits=[
            (
                MESSAGES_RULES,
                "        thread.origin is ThreadOrigin.DM and thread.status is not ThreadStatus.KNOTTED\n",
                "        False\n",
            )
        ],
        expect=[
            "test_a_private_message_costs_him_two_each_and_her_nothing",
            "test_a_retried_send_is_stored_once_and_charged_once",
        ],
    ),
    Case(
        id="t73-11-knot-charged",
        what="a private message's Knot still charging",
        edits=[
            (
                MESSAGES_RULES,
                "        thread.origin is ThreadOrigin.DM and thread.status is not ThreadStatus.KNOTTED\n",
                "        thread.origin is ThreadOrigin.DM\n",
            )
        ],
        expect=["test_a_knot_is_free"],
    ),
    Case(
        id="t73-12-no-dedupe",
        what="a retried send stored again",
        edits=[
            (
                MESSAGES_SERVICE,
                (
                    "        if existing is not None:\n"
                    "            return _again(existing, thread_id, user_id)\n"
                ),
                "        pass\n",
            ),
            (
                MESSAGES_SERVICE,
                (
                    "    if existing is not None:\n"
                    "        return _Sent(_again(existing, thread_id, user.id), new=False)\n"
                ),
                "    pass\n",
            ),
        ],
        expect=["test_a_retried_send_is_stored_once_and_charged_once"],
    ),
    Case(
        id="t73-13-deleted-reached",
        what="a message to a deleted account",
        edits=[
            (
                MESSAGES_SERVICE,
                "        if await repository.status_of(session, other_id) is UserStatus.DELETED:\n",
                "        if False:\n",
            )
        ],
        expect=["test_nothing_reaches_a_deleted_account"],
    ),
    Case(
        id="t73-14-no-filters",
        what="a send never passing the filters",
        edits=[
            (
                MESSAGES_SERVICE,
                "    await refuse_if_rejected(session, user_id, request.body)\n",
                "    pass\n",
            )
        ],
        expect=["test_abuse_and_asking_for_money_are_refused_and_kept_as_a_signal"],
    ),
    # t73-15 (a voice note let through before T-7.9) retired with T-7.9, which
    # lets hers through: a man's refusal is t79-01's.
    Case(
        id="t73-16-no-new-men-limit",
        what="writing first never counted among her new men",
        edits=[
            (
                MESSAGES_SERVICE,
                "            if thread.message_count == 0 and limits.counts_as_a_man(\n",
                "            if False and limits.counts_as_a_man(\n",
            )
        ],
        expect=["test_writing_first_to_a_man_counts_among_her_new_men"],
    ),
    Case(
        id="t73-17-answering-counted",
        what="answering him counted as writing first",
        edits=[
            (
                MESSAGES_SERVICE,
                "            if thread.message_count == 0 and limits.counts_as_a_man(\n",
                "            if thread.message_count >= 0 and limits.counts_as_a_man(\n",
            )
        ],
        expect=["test_answering_him_isnt_writing_first"],
    ),
    Case(
        id="t73-18-private-uncounted",
        what="her private messages never counted",
        edits=[
            (
                MESSAGES_SERVICE,
                "            if thread.origin is ThreadOrigin.DM:\n                private",
                "            if False:\n                private",
            )
        ],
        expect=["test_her_private_messages_are_counted"],
    ),
    Case(
        id="t73-19-place-kept",
        what="a failed send keeping her place",
        edits=[
            (
                MESSAGES_SERVICE,
                "    except BaseException:\n        await taken.give_back()\n        raise\n",
                "    except BaseException:\n        raise\n",
            )
        ],
        expect=["test_a_failed_send_gives_her_place_back"],
    ),
    Case(
        id="t73-20-clearing-ignored",
        what="messages before my clearing read",
        edits=[
            (
                MESSAGES_REPOSITORY,
                "    if since is not None:\n        query = query.where(Message.created_at > since)\n",
                "",
            )
        ],
        expect=["test_only_what_came_after_my_clearing"],
    ),
    Case(
        id="t73-21-voice-open-to-men",
        what="her voice note open to a man who hasn't unlocked it",
        edits=[
            (
                MESSAGES_RULES,
                "    return gender is not Gender.FEMALE and not unlocked\n",
                "    return False\n",
            )
        ],
        expect=["test_her_voice_note_is_locked_for_him_until_he_unlocks_it"],
    ),
    Case(
        id="t73-22-unlock-ignored",
        what="an unlocked voice note still locked",
        edits=[
            (
                MESSAGES_RULES,
                "    return gender is not Gender.FEMALE and not unlocked\n",
                "    return gender is not Gender.FEMALE\n",
            )
        ],
        expect=["test_her_voice_note_is_locked_for_him_until_he_unlocks_it"],
    ),
    Case(
        id="t73-23-deleted-sender-unnamed",
        what="a deleted account's messages not named as such",
        edits=[
            (
                MESSAGES_REPOSITORY,
                '            (sender == UserStatus.DELETED).label("from_deleted_account"),\n',
                '            (sender == UserStatus.BANNED).label("from_deleted_account"),\n',
            )
        ],
        expect=["test_a_deleted_accounts_messages_stay_and_say_so"],
    ),
    Case(
        id="t73-24-anyones-thread",
        what="anyone's Thread read and written to",
        edits=[
            (
                MESSAGES_REPOSITORY,
                (
                    "        Thread.id == thread_id,\n"
                    "        or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),\n"
                ),
                "        Thread.id == thread_id,\n",
            )
        ],
        expect=[
            "test_someone_elses_thread_is_not_found",
            "test_someone_elses_thread_or_one_across_a_block_is_not_found",
        ],
    ),
    Case(
        id="t73-25-across-a-block",
        what="a Thread read across a block",
        edits=[
            (
                MESSAGES_REPOSITORY,
                "        ~blocked_either_way(viewer_id, _other(viewer_id)),\n    )\n",
                "    )\n",
            )
        ],
        expect=["test_someone_elses_thread_or_one_across_a_block_is_not_found"],
    ),
    Case(
        id="t73-26-no-thread-lock",
        what="a send not holding the Thread's row",
        edits=[(MESSAGES_REPOSITORY, "    if lock:\n", "    if False:\n")],
        expect=["test_two_sends_at_once_are_both_counted"],
    ),
]

# --- T-8.3: a broken payment's claim, and P-420's record ---------------------------

CLAIMS = "app/modules/payments/claims.py"
CLAIM_SHAPE = (
    "alembic/versions/20261008_9a3d5384d962_refund_request_kinds_and_status.py"
)
REVERSALS = "alembic/versions/20261008_d4f1d16b2191_payment_reversals.py"
T83_SELECTION = [
    "tests/modules/payments",
    "tests/test_schema.py",
    "tests/test_app_role.py",
    "tests/test_migrations.py",
    "tests/core/test_razorpay.py",
    "tests/core/test_providers.py",
]
P420 = "test_a_reversal_that_took_nothing_never_takes_velas_bought_since"
GRANT = "test_a_grant_credits_the_purchase_under_the_webhooks_own_key"

T83: list[Case] = [
    Case(
        id="t83-01-repeat-read-from-the-ledger-only",
        what="P-420: a refund that took nothing isn't a repeat when redelivered",
        edits=[
            (
                WEBHOOKS,
                "    if await repository.reversal_recorded(\n        session, other.id\n    ) or await wallet_service.entry_for(\n",
                "    if await wallet_service.entry_for(\n",
            )
        ],
        expect=[
            f"{P420}[refund]",
            f"{P420}[dispute]",
            "test_a_refund_that_takes_nothing_delivered_five_times_at_once_is_handled_once",
        ],
    ),
    Case(
        id="t83-02-a-reversal-that-took-nothing-not-recorded",
        what="P-420: the record written only when something was taken",
        edits=[
            (
                PAY_REPO,
                '    `uq_payment_reversals_provider_ref`, never carries on."""\n',
                '    `uq_payment_reversals_provider_ref`, never carries on."""\n    if taken == 0:\n        return\n',
            )
        ],
        expect=[
            f"{P420}[refund]",
            f"{P420}[dispute]",
            "test_every_refund_handled_is_recorded_with_what_it_took",
        ],
    ),
    Case(
        id="t83-03-reversal-records-mutable",
        what="D-581: payment_reversals without its refuse_change() triggers",
        edits=[
            (
                REVERSALS,
                "    for name, when, level in GUARDS:\n",
                "    for name, when, level in ():\n",
            )
        ],
        expect=[
            "test_a_reversal_record_cannot_change_or_disappear",
            "test_reversal_records_cannot_be_truncated",
        ],
    ),
    Case(
        id="t83-04-app-role-keeps-update-and-delete",
        what="D-581: the app role may update and delete reversal records",
        edits=[
            (
                REVERSALS,
                '    op.execute(sa.text(f"revoke update, delete on payment_reversals from {APP_ROLE}"))\n',
                "",
            )
        ],
        expect=["test_no_refuse_change_trigger_is_reachable_by_the_app_role"],
    ),
    Case(
        id="t83-05-one-refund-recorded-twice",
        what="D-581: provider_ref not unique",
        edits=[
            (
                REVERSALS,
                '        sa.UniqueConstraint(\n            "provider_ref", name=op.f("uq_payment_reversals_provider_ref")\n        ),\n',
                "",
            ),
            (
                PAYMENT_MODELS,
                "    provider_ref: Mapped[str] = mapped_column(Text, nullable=False, unique=True)\n",
                "    provider_ref: Mapped[str] = mapped_column(Text, nullable=False)\n",
            ),
        ],
        expect=["test_a_refund_or_dispute_is_recorded_once"],
    ),
    Case(
        id="t83-06-missing-velas-granted-as-admin-grant",
        what="D-077: the repair credits admin_grant, not the webhook's purchase",
        edits=[
            (
                CLAIMS,
                "    outcome = await webhooks.capture_from_gateway(session, row, found)\n",
                '    from app.core.enums import LedgerReason\n    from app.modules.wallet import service as wallet_service\n\n    row.status, row.provider_payment_id, row.paid_at = (\n        type(row.status)("paid"), found.id, clock.now()\n    )\n    await wallet_service.credit(\n        session, row.user_id, row.credits + row.bonus_credits,\n        LedgerReason.ADMIN_GRANT, event=str(claim.id),\n    )\n    outcome = webhooks.Outcome.CAPTURED\n',
            )
        ],
        expect=[GRANT],
    ),
    Case(
        id="t83-07-a-credited-payment-granted-again",
        what="D-580: a grant on a row the webhook already credited",
        edits=[
            (
                CLAIMS,
                '    if row.provider_payment_id is not None:\n        raise _not_allowed("This payment\'s Velas were granted already.", "credited")\n',
                "",
            )
        ],
        expect=["test_a_grant_on_a_credited_payment_is_not_allowed"],
    ),
    Case(
        id="t83-08-a-grant-for-any-amount",
        what="rule 6: a captured payment of any amount is grantable",
        edits=[
            (
                PAY_RULES,
                "            if _untouched_capture(payment) and _for_the_order(payment, amount_paise)\n",
                "            if _untouched_capture(payment)\n",
            )
        ],
        expect=[
            "test_a_grant_with_no_matching_capture_at_the_gateway_is_not_allowed[another amount]"
        ],
    ),
    Case(
        id="t83-09-the-credited-payment-refunded",
        what="D-076 rule 3: money back for the payment whose Velas stand",
        edits=[(PAY_RULES, "            and payment.id != anchor\n", "")],
        expect=["test_the_credited_payment_is_never_refunded"],
    ),
    Case(
        id="t83-10-a-grantable-payment-refunded",
        what="D-050: money back for a payment a grant could still credit",
        edits=[
            (
                PAY_RULES,
                "            and not (anchor is None and _for_the_order(payment, amount_paise))\n",
                "",
            )
        ],
        expect=["test_a_payment_a_grant_could_credit_is_never_refunded"],
    ),
    Case(
        id="t83-11-a-refund-marks-the-credited-row",
        what="D-580: the duplicate's refund recorded as payments.status = refunded",
        edits=[
            (
                CLAIMS,
                "    _close(\n        claim,\n        ClaimStatus.REFUNDED,\n",
                '    payment.status = type(payment.status)("refunded")\n    _close(\n        claim,\n        ClaimStatus.REFUNDED,\n',
            )
        ],
        expect=["test_a_duplicate_charge_is_refunded_and_recorded_on_the_claim"],
    ),
    Case(
        id="t83-12-claim-lock-dropped",
        what="D-580: the claim read without FOR UPDATE",
        edits=[
            (
                PAY_REPO,
                "        .where(RefundRequest.id == claim_id)\n        .with_for_update()\n",
                "        .where(RefundRequest.id == claim_id)\n",
            )
        ],
        expect=["test_two_admins_resolving_one_claim_at_once_refund_once"],
    ),
    Case(
        id="t83-13-two-open-claims-on-one-payment",
        what="D-580: the one-open-claim index gone",
        edits=[
            (
                CLAIM_SHAPE,
                "        unique=True,\n        postgresql_where",
                "        unique=False,\n        postgresql_where",
            ),
        ],
        expect=[
            "test_a_second_open_claim_on_one_payment_already_exists",
            "test_a_payment_has_one_open_claim_at_a_time",
        ],
    ),
    Case(
        id="t83-14-anothers-payment-claimable",
        what="D-580: a claim on someone else's payment",
        edits=[
            (
                CLAIMS,
                "        if payment is None or payment.user_id != user.id:\n",
                "        if payment is None:\n",
            )
        ],
        expect=["test_another_mans_payment_and_none_are_the_same_not_found"],
    ),
    Case(
        id="t83-15-missing-velas-on-a-credited-payment",
        what="D-580: missing_velas filed on a payment that granted them",
        edits=[
            (
                CLAIMS,
                "        if reason is ClaimReason.MISSING_VELAS and payment.status in MONEY_MOVED:\n",
                "        if reason is ClaimReason.MISSING_VELAS and False and payment.status in MONEY_MOVED:\n",
            )
        ],
        expect=["test_missing_velas_on_a_payment_that_granted_them_is_not_allowed"],
    ),
    Case(
        id="t83-16-a-moderator-resolves",
        what="D-582: a moderator may resolve a claim",
        edits=[
            (
                ADMIN_ROUTER,
                "    body: RefundRequestResolution,\n    admin: Annotated[User, Depends(require_role(Role.ADMIN))],\n",
                "    body: RefundRequestResolution,\n    admin: Annotated[User, Depends(require_role(Role.MODERATOR, Role.ADMIN))],\n",
            )
        ],
        expect=["test_anyone_but_an_admin_is_forbidden[moderator]"],
    ),
    Case(
        id="t83-17-a-rejection-without-a-note",
        what="D-580: reject accepted with no note (the database still refuses: a 500)",
        edits=[
            (
                CLAIMS,
                "    if action is ClaimAction.REJECT and note is None:\n",
                "    if False:\n",
            )
        ],
        expect=["test_a_rejection_says_why"],
    ),
    Case(
        id="t83-18-a-resolution-not-audited",
        what="D-582: a resolution writes no audit_log",
        edits=[
            (
                CLAIMS,
                '        await admin_service.audit(\n            session,\n            admin_id,\n            "refund_requests.resolve",\n',
                '        if False:\n            await admin_service.audit(\n            session,\n            admin_id,\n            "refund_requests.resolve",\n',
            )
        ],
        expect=[GRANT],
    ),
    Case(
        id="t83-19-the-queue-not-audited",
        what="D-582: a list of claims writes no audit_log",
        edits=[
            (
                CLAIMS,
                '        await admin_service.audit(\n            session, admin_id, "refund_requests.list",',
                '        if False:\n            await admin_service.audit(\n            session, admin_id, "refund_requests.list",',
            )
        ],
        expect=["test_the_queue_is_open_claims_oldest_first_a_page_at_a_time_audited"],
    ),
    Case(
        id="t83-20-another-orders-payments-trusted",
        what="Razorpay's answer naming another order's payment trusted",
        edits=[(RAZORPAY, "            and payment.order_id == order_id\n", "")],
        expect=["test_payments_that_arent_the_orders_are_never_trusted[other-order]"],
    ),
    Case(
        id="t83-21-another-refund-trusted",
        what="Razorpay's refund of another payment trusted",
        edits=[
            (
                RAZORPAY,
                "    if of != payment_id or amount != amount_paise:\n",
                "    if amount != amount_paise:\n",
            )
        ],
        expect=[
            "test_a_refund_that_isnt_the_one_asked_for_is_never_trusted[other-payment]"
        ],
    ),
    Case(
        id="t83-22-the-receipt-not-the-claims",
        what="D-580: the refund's receipt isn't the claim's id, so Razorpay can't take it once",
        edits=[
            (
                CLAIMS,
                "            payment_id=found.id, amount_paise=found.amount_paise, receipt=str(claim.id)\n",
                "            payment_id=found.id, amount_paise=found.amount_paise, receipt=str(uuid4())\n",
            ),
            (CLAIMS, "from uuid import UUID\n", "from uuid import UUID, uuid4\n"),
        ],
        expect=["test_a_duplicate_charge_is_refunded_and_recorded_on_the_claim"],
    ),
]


# --- P-64: what a request publishes, seen through `client` --------------------------

P64_SELECTION = [
    "tests/test_harness.py",
    "tests/modules/threads/test_open.py",
    "tests/modules/messages/test_send.py",
]
INFRA = "tests/infra.py"

P64: list[Case] = [
    Case(
        id="p64-01-never-published",
        what="the stand-in for get_session publishing nothing",
        edits=[
            (
                INFRA,
                "        await events.publish(committed, connection.app.state.redis)\n",
                "        pass\n",
            )
        ],
        expect=["test_a_requests_committed_events_are_published_through_client"],
    ),
    Case(
        id="p64-02-never-kept",
        what="what a request published not kept for `published`",
        edits=[(INFRA, "        ActiveSession.published.extend(committed)\n", "")],
        expect=[
            "test_a_requests_committed_events_are_published_through_client",
            "test_a_man_opens_from_a_match_for_five_and_she_is_told",
            "test_a_message_is_stored_counted_and_both_told",
        ],
    ),
    Case(
        id="p64-03-the-tests-own-published",
        what="what the test itself committed published with the request",
        edits=[
            (
                INFRA,
                "        await session.commit()\n    events.take_committed(session)\n",
                "        await session.commit()\n",
            )
        ],
        expect=[
            "test_what_the_test_committed_itself_is_never_published",
            "test_a_man_opens_from_a_match_for_five_and_she_is_told",
        ],
    ),
]

# --- T-7.4: the socket side -------------------------------------------------------

T74_SELECTION = [
    "tests/modules/realtime",
    "tests/modules/auth/test_refresh.py",
    "tests/modules/auth/test_pin.py",
    "tests/bench/realtime",
]
REALTIME = "app/modules/realtime/service.py"
HUB = "app/modules/realtime/hub.py"
AUTH = "app/modules/auth/service.py"

T74: list[Case] = [
    Case(
        id="t74-01-ticket-twice",
        what="a ticket that opens a second socket",
        edits=[
            (
                REALTIME,
                "    raw = await redis.getdel(_key(ticket))\n",
                "    raw = await redis.get(_key(ticket))\n",
            )
        ],
        expect=["test_a_ticket_opens_once", "test_a_ticket_opens_one_socket_once"],
    ),
    Case(
        id="t74-02-ticket-kept-whole",
        what="a ticket kept in Redis as itself, not its hash",
        edits=[
            (
                REALTIME,
                "    return TICKET_PREFIX + hashlib.sha256(ticket.encode()).hexdigest()\n",
                "    return TICKET_PREFIX + ticket\n",
            )
        ],
        expect=["test_a_ticket_names_its_user_for_thirty_seconds_by_its_hash"],
    ),
    Case(
        id="t74-03-ticket-forever",
        what="a ticket that never expires",
        edits=[
            (
                REALTIME,
                "    await redis.set(_key(ticket), str(user_id), ex=TICKET_TTL_S)\n",
                "    await redis.set(_key(ticket), str(user_id))\n",
            )
        ],
        expect=["test_a_ticket_names_its_user_for_thirty_seconds_by_its_hash"],
    ),
    Case(
        id="t74-04-any-origin",
        what="a socket opened from any origin",
        edits=[
            (
                REALTIME,
                '    if websocket.headers.get("origin") not in app.state.settings.CORS_ORIGINS:\n',
                "    if False:\n",
            )
        ],
        expect=["test_only_the_webs_own_origin_opens_one"],
    ),
    Case(
        id="t74-05-no-ticket-asked",
        what="a socket opened without a ticket",
        edits=[(REALTIME, "    if user_id is None:\n", "    if False:\n")],
        expect=["test_no_ticket_no_socket", "test_a_ticket_opens_one_socket_once"],
    ),
    Case(
        id="t74-06-no-pong",
        what="a ping never answered",
        edits=[
            (
                REALTIME,
                "        if type_ == PING:\n",
                "        if False:\n",
            )
        ],
        expect=["test_ping_is_answered_pong"],
    ),
    Case(
        id="t74-07-never-idle",
        what="a silent socket kept open",
        edits=[
            (
                REALTIME,
                "            socket.close(CLOSE_IDLE)\n            return\n",
                "            continue\n",
            )
        ],
        expect=["test_a_silent_socket_is_closed"],
    ),
    Case(
        id="t74-08-close-forwarded",
        what="the server's own close sent on as an event",
        edits=[
            (
                HUB,
                "        if _type_of(text) == events.CLOSE_SOCKETS:\n",
                "        if False:\n",
            )
        ],
        expect=[
            "test_socket_close_closes_every_socket_of_that_user_alone",
            "test_deleting_the_account_closes_its_sockets",
            "test_the_hub_never_forwards_its_own_close",
        ],
    ),
    Case(
        id="t74-09-never-unsubscribed",
        what="Redis held for a user with no socket left",
        edits=[
            (
                HUB,
                "                    await self._pubsub.unsubscribe(_channel(user_id))\n",
                "                    pass\n",
            )
        ],
        expect=["test_the_last_socket_gone_the_hub_lets_redis_go"],
    ),
    Case(
        id="t74-10-one-socket-told",
        what="an event reaching one of a user's sockets",
        edits=[
            (
                HUB,
                "        for socket in held:\n            socket.offer(text)\n",
                "        for socket in held[:1]:\n            socket.offer(text)\n",
            )
        ],
        expect=["test_an_event_reaches_every_socket_of_its_user_and_nobody_else"],
    ),
    Case(
        id="t74-11-outbox-unbounded",
        what="a slow socket's outbox without a bound",
        edits=[
            (
                HUB,
                "        self.outbox: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAX)\n",
                "        self.outbox: asyncio.Queue[str] = asyncio.Queue()\n",
            )
        ],
        expect=["test_a_slow_socket_is_closed_never_waited_for"],
    ),
    Case(
        id="t74-12-shutdown-leaves-sockets",
        what="the hub not closed with the app",
        edits=[("app/main.py", "        await hub.aclose()\n", "        pass\n")],
        expect=["test_shutting_down_closes_every_socket"],
    ),
    Case(
        id="t74-13-reuse-keeps-sockets",
        what="a replayed refresh leaving the sockets open",
        edits=[
            (
                AUTH,
                "            )\n            events.close_sockets(session, current.user_id)\n",
                "            )\n",
            )
        ],
        expect=["test_reuse_more_than_ten_seconds_later_revokes_the_family"],
    ),
    Case(
        id="t74-14-logout-keeps-sockets",
        what="a sign-out leaving the sockets open",
        edits=[
            (
                AUTH,
                "        )\n        events.close_sockets(session, current.user_id)\n",
                "        )\n",
            )
        ],
        expect=["test_logout_revokes_the_whole_family_but_not_another_devices"],
    ),
    Case(
        id="t74-15-deletion-keeps-sockets",
        what="a deleted account's sockets left open",
        edits=[
            (
                AUTH,
                (
                    "    await repository.revoke_every_session(session, user_id=user_id, at=clock.now())\n"
                    "    events.close_sockets(session, user_id)\n"
                ),
                "    await repository.revoke_every_session(session, user_id=user_id, at=clock.now())\n",
            )
        ],
        expect=["test_deleting_the_account_closes_its_sockets"],
    ),
    Case(
        id="t74-16-locked-pin-keeps-sockets",
        what="a PIN already locked leaving the sockets open",
        edits=[
            (
                AUTH,
                "            events.close_sockets(session, user_id)\n    if tries is None:\n",
                "    if tries is None:\n",
            )
        ],
        expect=["test_once_locked_even_the_right_pin_is_refused_and_not_counted"],
    ),
    Case(
        id="t74-17-fifth-pin-keeps-sockets",
        what="the fifth wrong PIN leaving the sockets open",
        edits=[
            (
                AUTH,
                "            events.close_sockets(session, user_id)\n        raise _session_revoked()\n",
                "        raise _session_revoked()\n",
            )
        ],
        expect=["test_five_wrong_pins_revoke_every_session_of_the_user"],
    ),
    Case(
        id="t74-18-bench-judges-open-only",
        what="the load test blind to memory after the events",
        edits=[
            (
                "bench/realtime/sockets.py",
                "    if peak_mb >= LIMIT_MB:\n",
                "    if peak_mb > 10**9:\n",
            )
        ],
        expect=["test_each_shortfall_is_named"],
    ),
]


# --- P-56: a charge refused when its price isn't the one shown (D-600) ---------------

P56_SELECTION = [
    "tests/modules/pricing/test_service.py",
    "tests/modules/swipes/test_swipe.py",
    "tests/modules/threads/test_open.py",
    "tests/modules/messages/test_send.py",
]
PRICING_SERVICE = "app/modules/pricing/service.py"

P56: list[Case] = [
    Case(
        id="p56-01-never-compared",
        what="the shown price never compared: a man charged what he wasn't shown",
        edits=[
            (
                PRICING_SERVICE,
                "    if price != shown:\n        raise price_changed(price)\n",
                "",
            )
        ],
        expect=[
            "test_a_price_changed_since_it_was_shown_is_refused_and_nothing_debited",
            "test_a_lower_price_than_shown_is_refused_too",
            "test_a_man_shown_no_price_is_never_charged",
            "test_a_woman_shown_a_price_is_refused",
            "test_a_super_like_at_a_price_he_wasnt_shown_is_refused_and_writes_nothing",
            "test_a_thread_at_a_price_he_wasnt_shown_opens_nothing",
            "test_a_private_message_shown_at_the_wrong_price_sends_nothing",
            "test_a_paid_send_at_a_price_he_wasnt_shown_sends_nothing",
        ],
    ),
    Case(
        id="p56-02-absent-skips",
        what="a request without shown_price let through: the check failing open",
        edits=[
            (
                PRICING_SERVICE,
                "    if price != shown:\n",
                "    if shown and price != shown:\n",
            )
        ],
        expect=[
            "test_a_man_shown_no_price_is_never_charged",
            "test_a_super_like_at_a_price_he_wasnt_shown_is_refused_and_writes_nothing[None]",
            "test_a_super_like_at_a_price_he_wasnt_shown_is_refused_and_writes_nothing[0]",
            "test_a_thread_at_a_price_he_wasnt_shown_opens_nothing[None-5]",
            "test_a_paid_send_at_a_price_he_wasnt_shown_sends_nothing[None-dm-2]",
            "test_a_paid_send_at_a_price_he_wasnt_shown_sends_nothing[None-match-5]",
        ],
    ),
    Case(
        id="p56-03-super-like-not-passed",
        what="a Super Like comparing the price with itself, not with what was shown",
        edits=[
            (
                "app/modules/swipes/service.py",
                "            shown=shown_price,\n",
                "            shown=await pricing_service.price_for(\n                session, user, LedgerReason.SUPER_LIKE\n            ),\n",
            )
        ],
        expect=[
            "test_a_super_like_at_a_price_he_wasnt_shown_is_refused_and_writes_nothing"
        ],
    ),
    Case(
        id="p56-04-thread-open-not-passed",
        what="opening a Thread comparing the price with itself",
        edits=[
            (
                "app/modules/threads/service.py",
                "        shown=request.shown_price,\n",
                "        shown=await pricing_service.price_for(\n            session, user, rules.OPEN_PRICE[origin]\n        ),\n",
            )
        ],
        expect=[
            "test_a_thread_at_a_price_he_wasnt_shown_opens_nothing",
            "test_a_private_message_shown_at_the_wrong_price_sends_nothing",
        ],
    ),
    Case(
        id="p56-05-answer-not-passed",
        what="his first message where she opened comparing the price with itself",
        edits=[
            (
                "app/modules/messages/service.py",
                "            answer,\n            shown=request.shown_price,\n",
                "            answer,\n            shown=await pricing_service.price_for(session, user, answer),\n",
            )
        ],
        expect=[
            "test_a_paid_send_at_a_price_he_wasnt_shown_sends_nothing[None-match-5]"
        ],
    ),
    Case(
        id="p56-06-private-message-not-passed",
        what="a private message comparing the price with itself",
        edits=[
            (
                "app/modules/messages/service.py",
                "            LedgerReason.DM_MESSAGE,\n            shown=request.shown_price,\n",
                "            LedgerReason.DM_MESSAGE,\n            shown=await pricing_service.price_for(\n                session, user, LedgerReason.DM_MESSAGE\n            ),\n",
            )
        ],
        expect=["test_a_paid_send_at_a_price_he_wasnt_shown_sends_nothing[None-dm-2]"],
    ),
]

# --- T-6.5: a man's swipes left on the feed ------------------------------------------

T65_SELECTION = ["tests/modules/discovery/test_feed.py"]
DISCOVERY_SERVICE = "app/modules/discovery/service.py"

T65: list[Case] = [
    Case(
        id="t65-01-a-woman-given-a-count",
        what="D-492: the feed giving a woman, who has no cap, a number",
        edits=[
            (
                DISCOVERY_SERVICE,
                "    if not swipe_rules.capped(user.gender):\n        return None\n",
                "",
            )
        ],
        expect=["test_a_womans_feed_has_no_count"],
    ),
    Case(
        id="t65-02-the-count-never-taken",
        what="the feed saying the whole cap, whatever was swiped today",
        edits=[
            (
                DISCOVERY_SERVICE,
                "    return await swipe_counter.left(redis, user.id, clock.today_ist(), limit)\n",
                "    return limit\n",
            )
        ],
        expect=["test_a_mans_feed_says_his_swipes_left_before_and_after_a_swipe"],
    ),
]

# --- P-79: an approved private photo's scored copy, out of the upload URL's reach ---

P79_SELECTION = [
    "tests/modules/photos/test_moderate.py",
    "tests/modules/photos/test_manage.py",
    "tests/modules/photos/test_scored_copy_migration.py",
    "tests/core/test_storage_keys.py",
    "tests/modules/account/test_erasure.py",
    "tests/modules/users/test_dob_gender.py",
]
PHOTOS_SERVICE = "app/modules/photos/service.py"
STORAGE_KEYS = "app/core/storage_keys.py"
SCORED_COPY = "alembic/versions/20261008_8243172d0af6_a_private_photos_scored_copy.py"
KEPT_SCORED = (
    "test_an_approved_private_photo_is_kept_scored_where_no_upload_url_reaches"
)
SECOND_PUT = "test_a_private_photos_scored_copy_survives_a_second_put_before_or_after"

P79: list[Case] = [
    Case(
        id="p79-01-the-scored-copy-never-written",
        what="the row names a scored copy that moderation never stored",
        edits=[
            (
                PHOTOS_SERVICE,
                (
                    "            key = scored_key(locked.user_id, locked.id)\n"
                    "            await _stored(\n"
                    "                storage.put_bytes(\n"
                    '                    settings.R2_BUCKET_PRIVATE, key, clean.data, "image/jpeg"\n'
                    "                )\n"
                    "            )\n"
                ),
                "            key = scored_key(locked.user_id, locked.id)\n",
            )
        ],
        expect=[KEPT_SCORED, SECOND_PUT],
    ),
    Case(
        id="p79-02-the-scored-copy-at-the-uploads-key",
        what="P-79's hole: the scored copy written over the upload, as before",
        edits=[
            (
                PHOTOS_SERVICE,
                "            key = scored_key(locked.user_id, locked.id)\n",
                "            key = locked.raw_key\n",
            )
        ],
        expect=[KEPT_SCORED, SECOND_PUT],
    ),
    Case(
        id="p79-03-the-key-under-the-upload-prefix",
        what="the scored key built as the upload's key, which the PUT URL covers",
        edits=[
            (
                STORAGE_KEYS,
                '    return f"scored/{_id(user_id)}/{_id(photo_id)}.jpg"\n',
                '    return f"raw/{_id(user_id)}/{_id(photo_id)}"\n',
            )
        ],
        expect=[
            "test_each_kind_of_file_has_its_shape",
            "test_a_scored_copy_is_never_under_the_upload_prefix",
            KEPT_SCORED,
            SECOND_PUT,
        ],
    ),
    Case(
        id="p79-04-every-approved-kind-scored",
        what="a scored copy for the face photo too, which nobody else is shown",
        edits=[
            (
                PHOTOS_SERVICE,
                "        if locked.kind is PhotoKind.PRIVATE:\n",
                "        if locked.kind is not PhotoKind.PUBLIC:\n",
            )
        ],
        expect=[
            "test_only_an_approved_private_photo_gets_a_scored_copy[verification-approved]"
        ],
    ),
    Case(
        id="p79-05-the-owner-shown-the-upload",
        what="an approved private photo's owner given a link to the upload",
        edits=[
            (
                PHOTOS_SERVICE,
                (
                    "    elif photo.status is ReviewStatus.APPROVED and photo.scored_key:\n"
                    "        url = await storage.presign_get(settings.R2_BUCKET_PRIVATE, photo.scored_key)\n"
                ),
                "",
            )
        ],
        expect=[
            "test_the_owner_sees_every_live_photo_and_where_to_view_it",
            SECOND_PUT,
        ],
    ),
    Case(
        id="p79-06-erasure-leaves-the-scored-copy",
        what="D-500's erasure without the scored copy in its file list",
        edits=[(ERASURE96, '    (Photo, "scored_key", "private"),\n', "")],
        expect=[
            "test_every_storage_key_on_an_erased_table_is_in_the_file_list",
            "test_an_account_deleted_29_days_ago_is_erased_and_kept_exactly_as_d051_says",
        ],
    ),
    Case(
        id="p79-07-underage-leaves-the-scored-copy",
        what="D-078's deletion without the scored copy in its file list",
        edits=[
            (
                "app/modules/users/repository.py",
                '    FileColumn(Photo, "scored_key", "private"),\n',
                "",
            )
        ],
        expect=[
            "test_every_storage_key_on_a_deleted_table_is_in_the_file_list",
            "test_under_eighteen_queues_its_files_deletion_before_the_rows_go",
        ],
    ),
    Case(
        id="p79-08-the-downgrade-drops-scored-copies",
        what="the column dropped while files hang off it, out of every deletion's sight",
        edits=[
            (
                SCORED_COPY,
                "    if held:\n",
                "    if False:\n",
            )
        ],
        expect=["test_the_downgrade_refuses_while_a_scored_copy_exists"],
    ),
]

# --- T-6.7: liked you, the paid reveal, the blur ------------------------------------

LIKES_SERVICE = "app/modules/likes/service.py"
LIKES_REPO = "app/modules/likes/repository.py"
PHOTOS_SERVICE = "app/modules/photos/service.py"
T67_SELECTION = [
    "tests/modules/likes",
    "tests/core/test_images_blur.py",
    "tests/modules/photos/test_blur.py",
    "tests/modules/account/test_erasure.py",
    "tests/modules/pricing/test_debit_callers.py",
]
NAMES_NOBODY = "test_a_man_sees_who_liked_him_as_a_blur_and_nothing_that_names_them"
ANSWERED = "test_only_likes_not_yet_answered_from_someone_i_could_swipe_back"

T67: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t67-01-shown-unpaid",
            what="D-542: a man shown everyone who liked him, unrevealed or not",
            edits=[
                (
                    LIKES_SERVICE,
                    "        shown = [row.liker_id for row in rows if everyone or row.revealed]\n",
                    "        shown = [row.liker_id for row in rows]\n",
                )
            ],
            expect=[NAMES_NOBODY],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-02-handle-is-the-id",
            what="D-542: the handle the liker's own id, which opens their profile free",
            edits=[
                (
                    LIKES_REPO,
                    '    return func.encode(func.substring(digest, 1, rules.HANDLE_HEX // 2), "hex")\n',
                    '    return func.replace(cast(liker, Text), "-", "")\n',
                )
            ],
            expect=[NAMES_NOBODY],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-03-reveal-row-not-once",
            what="two reveals at once: the second's row a unique violation, not nothing",
            edits=[
                (
                    LIKES_REPO,
                    '        .on_conflict_do_nothing(index_elements=["viewer_id", "liker_id"])\n',
                    "",
                )
            ],
            expect=[
                "test_two_reveals_at_once_pay_once_and_both_see_him",
                "test_revealing_again_charges_nothing",
            ],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-05-a-literal-price",
            what="rule 5, D-004: the reveal debited a literal 1, past pricing",
            edits=[
                (
                    LIKES_SERVICE,
                    "            await pricing_service.charge(\n                session,\n                user,\n                LedgerReason.LIKED_YOU_REVEAL,\n",
                    "            await wallet_service.debit(\n                session,\n                user.id,\n                1,\n                LedgerReason.LIKED_YOU_REVEAL,\n",
                ),
                (
                    LIKES_SERVICE,
                    "from app.modules.pricing import service as pricing_service\n",
                    "from app.modules.pricing import service as pricing_service\nfrom app.modules.wallet import service as wallet_service\n",
                ),
            ],
            expect=[
                "test_a_man_pays_the_rows_price_once_and_sees_who_it_was",
                "test_a_woman_pays_nothing",
                "test_only_charge_reaches_the_debit",
            ],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-06-answered-likes-listed",
            what="a like the viewer already swiped back on still listed",
            edits=[
                (
                    LIKES_REPO,
                    "            ~exists().where(\n                mine.swiper_id == viewer.id, mine.target_id == Swipe.swiper_id\n            ),\n",
                    "",
                )
            ],
            expect=[ANSWERED],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-07-not-mutual",
            what="D-492: likers the viewer couldn't swipe back listed",
            edits=[
                (
                    LIKES_REPO,
                    "            *visible_to(viewer, mutual=True),\n",
                    "            *visible_to(viewer, mutual=False),\n",
                )
            ],
            expect=[ANSWERED],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-08-a-woman-blurred",
            what="D-002: a woman made to reveal who liked her",
            edits=[
                (
                    "app/modules/likes/rules.py",
                    "    return gender is Gender.FEMALE\n",
                    "    return False\n",
                )
            ],
            expect=["test_a_woman_sees_everyone_who_liked_her_free"],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-09-no-blur",
            what="D-543: the 'blur' the photo itself",
            edits=[
                (
                    "app/core/images.py",
                    '    spread.save(out, "JPEG", quality=BLUR_QUALITY)\n',
                    "    out.write(data)\n",
                )
            ],
            expect=[
                "test_a_face_found_in_the_photo_is_found_in_no_blur_of_it",
                "test_a_blur_holds_no_more_than_its_few_pixels",
            ],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-10-blur-key-from-the-photos-id",
            what="D-543: the blur's key derived from the photo's id",
            edits=[
                (
                    PHOTOS_SERVICE,
                    "    key = blurred_photo_key(uuid4())\n",
                    "    key = blurred_photo_key(photo_id)\n",
                )
            ],
            expect=["test_an_approved_public_photo_gets_a_blur_under_a_key_of_its_own"],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-11-blur-kept-after-removal",
            what="D-543: a removed photo's blur left in the public bucket",
            edits=[
                (
                    PHOTOS_SERVICE,
                    "    for key in (public_key, blur_key):\n",
                    "    for key in (public_key,):\n",
                )
            ],
            expect=["test_removing_a_photo_removes_its_blur"],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-12-blur-kept-at-erasure",
            what="D-503: the blur left out of the erasure's files",
            edits=[
                (
                    "app/modules/account/erasure.py",
                    '    (Photo, "blur_key", "public"),\n',
                    "",
                )
            ],
            expect=["test_every_storage_key_on_an_erased_table_is_in_the_file_list"],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-13-orphan-blur",
            what="D-543: a blur written for a photo removed meanwhile, left behind",
            edits=[
                (
                    PHOTOS_SERVICE,
                    '    await storage.delete(settings.R2_BUCKET_PUBLIC, key)\n    return "changed while it was blurred: its blur removed"\n',
                    '    return "changed while it was blurred: its blur removed"\n',
                )
            ],
            expect=["test_a_photo_removed_while_it_was_blurred_keeps_no_blur"],
        ),
        T67_SELECTION,
    ),
    (
        Case(
            id="t67-14-shown-price-ignored",
            what="P-56: the reveal charged at whatever price, not the one shown",
            edits=[
                (
                    "app/modules/likes/router.py",
                    "session, user, handle, shown_price=body.shown_price, settings=settings",
                    "session, user, handle, shown_price=1, settings=settings",
                )
            ],
            expect=[
                "test_a_price_not_the_one_shown_is_refused_with_nothing_charged_or_written"
            ],
        ),
        T67_SELECTION,
    ),
]

# --- T-7.8: clearing --------------------------------------------------------------

T78_SELECTION = [
    "tests/modules/threads/test_clear.py",
    "tests/modules/threads/test_clear_race.py",
]
THREADS_SCHEMAS = "app/modules/threads/schemas.py"
THREADS_ROUTER = "app/modules/threads/router.py"
CLEAR_TEST = "test_clear.py::"
UNTOUCHED = "test_after_he_clears_she_sees_everything_and_nothing_is_touched"
CHOSEN = "test_chosen_ids_clear_mine_and_skip_the_rest"
EXPIRED = "test_clear_expired_takes_those_in_my_list_expired_by_the_clock"
ONLY_MINE = "test_only_my_threads_and_never_across_a_block"

T78: list[Case] = [
    Case(
        id="t78-01-anyones-thread",
        what="D-006: a clearing reaching a Thread that isn't yours",
        edits=[
            (
                THREADS_REPOSITORY,
                (
                    "    return and_(\n"
                    "        or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),\n"
                ),
                "    return and_(\n        true(),\n",
            )
        ],
        expect=[f"{ONLY_MINE}[theirs-clear]", CHOSEN, EXPIRED],
    ),
    Case(
        id="t78-02-across-a-block",
        what="a clearing reaching a Thread across a block, either way",
        edits=[
            (
                THREADS_REPOSITORY,
                (
                    "        ~blocked_either_way(viewer_id, _other(viewer_id)),\n    )\n"
                    "\n\nasync def lock_mine("
                ),
                "    )\n\n\nasync def lock_mine(",
            )
        ],
        expect=[
            f"{ONLY_MINE}[blocked by me-clear]",
            f"{ONLY_MINE}[blocking me-clear]",
            CHOSEN,
            EXPIRED,
        ],
    ),
    Case(
        id="t78-03-stamped-at-the-tap",
        what="D-610: the clearing stamped with its own time, not the newest message",
        edits=[
            (
                THREADS_REPOSITORY,
                "func.coalesce(newest, Thread.created_at)",
                "func.now()",
            )
        ],
        expect=[
            "test_a_message_begun_before_a_clearing_and_written_after_shows",
            "test_cleared_at_is_the_newest_message_never_the_tap",
        ],
    ),
    Case(
        id="t78-04-no-lock",
        what="D-610: a clearing that never holds the Thread, so never waits for a send",
        edits=[
            (
                THREADS_REPOSITORY,
                (
                    "        .where(Thread.id.in_(thread_ids), _mine(viewer_id))\n"
                    "        .order_by(Thread.id)\n"
                    "        .with_for_update(of=Thread)\n"
                ),
                (
                    "        .where(Thread.id.in_(thread_ids), _mine(viewer_id))\n"
                    "        .order_by(Thread.id)\n"
                ),
            )
        ],
        expect=[
            "test_a_message_waiting_on_a_clearing_shows",
            "test_a_message_a_clearing_waited_on_is_hidden",
        ],
    ),
    Case(
        id="t78-05-expired-means-any",
        what="'Clear expired' clearing live Threads and Knots too",
        edits=[
            (
                THREADS_REPOSITORY,
                (
                    "            or_(\n"
                    "                Thread.status == ThreadStatus.EXPIRED,\n"
                    "                and_(Thread.status == ThreadStatus.ACTIVE, Thread.expires_at <= now),\n"
                    "            ),\n"
                ),
                "",
            )
        ],
        expect=[EXPIRED],
    ),
    Case(
        id="t78-06-expired-by-status-alone",
        what="D-560: 'Clear expired' reading the status column, never the clock",
        edits=[
            (
                THREADS_REPOSITORY,
                "                and_(Thread.status == ThreadStatus.ACTIVE, Thread.expires_at <= now),\n",
                "",
            )
        ],
        expect=[EXPIRED],
    ),
    Case(
        id="t78-07-expired-past-the-list",
        what="'Clear expired' counting Threads already hidden from my list",
        edits=[
            (
                THREADS_REPOSITORY,
                (
                    "            or_(Thread.last_message_at > cleared, cleared.is_(None)),\n"
                    "        )\n"
                    "        .order_by(Thread.id)\n"
                ),
                "        )\n        .order_by(Thread.id)\n",
            )
        ],
        expect=[EXPIRED],
    ),
    Case(
        id="t78-08-restore-for-both",
        what="D-006: undoing my clearing undoing theirs too",
        edits=[
            (
                THREADS_REPOSITORY,
                "            ThreadClear.user_id == viewer_id, ThreadClear.thread_id == thread_id\n",
                "            ThreadClear.thread_id == thread_id\n",
            )
        ],
        expect=["test_restoring_mine_leaves_hers"],
    ),
    Case(
        id="t78-09-restore-anyones",
        what="a restore answering for a Thread that isn't yours, or across a block",
        edits=[
            (
                THREADS_SERVICE,
                (
                    "        if await repository.my_thread(session, thread_id, user.id) is None:\n"
                    "            raise _not_found()\n"
                    "        await repository.restore("
                ),
                "        await repository.restore(",
            )
        ],
        expect=[
            f"{ONLY_MINE}[theirs-restore]",
            f"{ONLY_MINE}[nobody's-restore]",
            f"{ONLY_MINE}[blocked by me-restore]",
            f"{ONLY_MINE}[blocking me-restore]",
        ],
    ),
    Case(
        id="t78-10-clearing-marks-read",
        what="rule 12: a clearing touching the messages (her 'Read' changes)",
        edits=[
            (
                THREADS_REPOSITORY,
                (
                    "            set_={ThreadClear.cleared_at: upsert.excluded.cleared_at},\n"
                    "        )\n"
                    "    )\n"
                ),
                (
                    "            set_={ThreadClear.cleared_at: upsert.excluded.cleared_at},\n"
                    "        )\n"
                    "    )\n"
                    "    await session.execute(\n"
                    "        update(Message)\n"
                    "        .where(Message.thread_id.in_(thread_ids))\n"
                    "        .values(read_at=func.now())\n"
                    "    )\n"
                ),
            )
        ],
        expect=[UNTOUCHED],
    ),
    Case(
        id="t78-11-clearing-tells",
        what="D-006: a clearing announced as an event",
        edits=[
            (
                THREADS_SERVICE,
                "        await repository.clear(session, user.id, [thread_id])\n",
                (
                    "        await repository.clear(session, user.id, [thread_id])\n"
                    '        events.queue(session, user.id, "thread.cleared", {})\n'
                ),
            )
        ],
        expect=[UNTOUCHED],
    ),
    Case(
        id="t78-12-both-at-once",
        what="a bulk body with both thread_ids and expired taken",
        edits=[
            (
                THREADS_SCHEMAS,
                "        if (self.thread_ids is None) == (self.expired is None):\n",
                "        if self.thread_ids is None and self.expired is None:\n",
            )
        ],
        expect=[f"{CLEAR_TEST}test_a_bad_body_is_a_validation_error[body3]"],
    ),
    Case(
        id="t78-13-expired-false",
        what="a bulk body of expired: false taken",
        edits=[
            (
                THREADS_SCHEMAS,
                (
                    "        if self.expired is False:\n"
                    '            raise ValueError("expired can only be true")\n'
                ),
                "",
            )
        ],
        expect=[f"{CLEAR_TEST}test_a_bad_body_is_a_validation_error[body2]"],
    ),
    Case(
        id="t78-14-no-cap",
        what="a bulk body of any number of ids taken",
        edits=[
            (
                THREADS_SCHEMAS,
                "        default=None, min_length=1, max_length=CLEAR_MAX\n",
                "        default=None, min_length=1\n",
            )
        ],
        expect=[f"{CLEAR_TEST}test_a_bad_body_is_a_validation_error[body4]"],
    ),
    Case(
        id="t78-15-no-rate-limit",
        what="rule 9: clearing without a rate limit",
        edits=[
            (
                THREADS_ROUTER,
                'user_rate_limit("threads_clear", limit=CLEARS_PER_MINUTE, window_s=60)',
                'user_rate_limit("threads_clear", limit=10_000, window_s=60)',
            )
        ],
        expect=["test_clearing_and_restoring_share_one_rate_limit"],
    ),
]

# --- T-6.8: the public link and its page --------------------------------------------

T68_SELECTION = [
    "tests/modules/discovery/test_shared_profile.py",
    "tests/modules/account/test_settings.py",
]

T68: list[tuple[Case, list[str]]] = [
    (
        Case(
            id="t68-01-public-without-asking",
            what="D-544: /@username shown without its owner turning the link on",
            edits=[
                (
                    DISCOVERY_REPO,
                    "                Profile.public_link.is_(True),\n",
                    "",
                ),
            ],
            expect=["test_a_fresh_account_is_not_found_until_she_turns_the_link_on"],
        ),
        T68_SELECTION,
    ),
    (
        Case(
            id="t68-02-on-by-default",
            what="D-544: the public link on for everyone, those already here included",
            edits=[
                (
                    "app/modules/profiles/models.py",
                    "    public_link: Mapped[bool] = mapped_column(\n        Boolean, nullable=False, server_default=false()\n",
                    "    public_link: Mapped[bool] = mapped_column(\n        Boolean, nullable=False, server_default=true()\n",
                ),
                (
                    "alembic/versions/20261008_959e7af5110e_a_public_link_off_by_default.py",
                    'server_default=sa.text("false")',
                    'server_default=sa.text("true")',
                ),
            ],
            expect=[
                "test_a_fresh_account_is_not_found_until_she_turns_the_link_on",
                "test_each_switch_sets_itself_and_nothing_else",
            ],
        ),
        T68_SELECTION,
    ),
    (
        Case(
            id="t68-03-hidden-shown",
            what="a hidden profile on its public page",
            edits=[
                (
                    DISCOVERY_REPO,
                    "                Profile.is_hidden.is_(False),\n",
                    "",
                ),
            ],
            expect=["test_every_refusal_is_the_same_not_found"],
        ),
        T68_SELECTION,
    ),
    (
        Case(
            id="t68-04-shadowed-shown",
            what="D-031: a shadowed profile's page shown to the internet",
            edits=[
                (
                    DISCOVERY_REPO,
                    "                ~_in_band(User.id, FraudBand.SHADOW),\n",
                    "",
                ),
            ],
            expect=["test_every_refusal_is_the_same_not_found"],
        ),
        T68_SELECTION,
    ),
    (
        Case(
            id="t68-05-a-hidden-age-shown",
            what="her age on the public page though she hides it",
            edits=[
                (
                    "app/modules/discovery/service.py",
                    "        if row.hide_age or row.dob is None\n        else users_service.age_on(row.dob, clock.today_ist()),\n        city=row.city,\n",
                    "        if row.dob is None\n        else users_service.age_on(row.dob, clock.today_ist()),\n        city=row.city,\n",
                ),
            ],
            expect=["test_a_hidden_age_and_no_photo"],
        ),
        T68_SELECTION,
    ),
    (
        Case(
            id="t68-06-unlimited",
            what="the public page's API with no limit per address",
            edits=[
                (
                    "app/modules/discovery/router.py",
                    "SHARED_PER_MINUTE = 60\n",
                    "SHARED_PER_MINUTE = 10**6\n",
                ),
            ],
            expect=["test_it_is_limited_to_60_a_minute_per_address"],
        ),
        T68_SELECTION,
    ),
]

# --- T-7.5: read receipts and typing (D-670) -----------------------------------------

T75_SELECTION = [
    "tests/modules/messages/test_read.py",
    "tests/modules/realtime",
]
OPENER = "app/core/db.py"
READ_ANCHOR = (
    "        thread = await repository.thread_of(session, thread_id, user_id)\n"
    "        if thread is None:\n"
    "            raise _not_found()\n"
    "        since = await repository.cleared_at(session, thread_id, user_id)\n"
)
TYPING_ANCHOR = (
    "        thread = await repository.thread_of(session, thread_id, user_id)\n"
    "    return None if thread is None else _other_of(thread, user_id)\n"
)
CEILING = (
    "        ceiling = await ratelimit.hit(\n"
    '            self._redis, "ws_typing", user, limit=TYPING_PER_MINUTE, window_s=60\n'
    "        )\n"
    "        if not ceiling.allowed:\n"
    "            return\n"
)

T75: list[Case] = [
    Case(
        id="t75-01-read-across-a-block",
        what="a read across a block marks and tells",
        edits=[
            (
                MESSAGES_SERVICE,
                READ_ANCHOR,
                READ_ANCHOR.replace(
                    "repository.thread_of(session, thread_id, user_id)",
                    "session.get(Thread, thread_id)",
                ).replace(
                    "        if thread is None:\n",
                    "        if thread is None or user_id not in (\n"
                    "            thread.user_low, thread.user_high\n"
                    "        ):\n",
                ),
            )
        ],
        expect=["test_across_a_block_nothing_is_read_and_nobody_told"],
    ),
    Case(
        id="t75-02-read-anyones-thread",
        what="anyone marks any Thread read",
        edits=[
            (
                MESSAGES_SERVICE,
                READ_ANCHOR,
                READ_ANCHOR.replace(
                    "repository.thread_of(session, thread_id, user_id)",
                    "session.get(Thread, thread_id)",
                ),
            )
        ],
        expect=["test_someone_elses_thread_is_not_found"],
    ),
    Case(
        id="t75-03-read-marks-mine",
        what="a read marks the reader's own messages",
        edits=[(MESSAGES_REPOSITORY, "        Message.sender_id != reader_id,\n", "")],
        expect=["test_my_own_messages_are_never_marked"],
    ),
    Case(
        id="t75-04-read-at-moves",
        what="a second read moves read_at on",
        edits=[(MESSAGES_REPOSITORY, "        Message.read_at.is_(None),\n", "")],
        expect=["test_a_read_at_once_set_never_moves_and_a_second_read_tells_nobody"],
    ),
    Case(
        id="t75-05-read-past-the-one-named",
        what="a read marks messages after the one named",
        edits=[
            (
                MESSAGES_REPOSITORY,
                "        tuple_(Message.created_at, Message.id) <= up_to,\n",
                "",
            )
        ],
        expect=["test_their_messages_up_to_the_one_named_are_read_and_they_alone_told"],
    ),
    Case(
        id="t75-06-read-before-the-clearing",
        what="a read marks what the reader's clearing hid",
        edits=[
            (
                MESSAGES_REPOSITORY,
                "        conditions.append(Message.created_at > since)\n",
                "        pass\n",
            )
        ],
        expect=["test_nothing_before_my_clearing_is_marked"],
    ),
    Case(
        id="t75-07-read-up-to-a-hidden-message",
        what="a read names a message the clearing hid",
        edits=[
            (
                MESSAGES_SERVICE,
                "        if target is None or (since is not None and target.created_at <= since):\n",
                "        if target is None:\n",
            )
        ],
        expect=["test_a_message_before_my_clearing_is_not_found"],
    ),
    Case(
        id="t75-08-read-up-to-another-threads-message",
        what="a read names a message from another Thread",
        edits=[
            (
                MESSAGES_REPOSITORY,
                "        select(Message).where(Message.id == message_id, Message.thread_id == thread_id)\n",
                "        select(Message).where(Message.id == message_id)\n",
            )
        ],
        expect=["test_a_message_from_another_thread_or_none_is_not_found"],
    ),
    Case(
        id="t75-09-receipt-to-the-reader",
        what="message.read told to the reader, not the sender",
        edits=[
            (
                MESSAGES_SERVICE,
                "            _other_of(thread, user_id),\n            MESSAGE_READ,\n",
                "            user_id,\n            MESSAGE_READ,\n",
            )
        ],
        expect=[
            "test_their_messages_up_to_the_one_named_are_read_and_they_alone_told",
            "test_the_receipt_reaches_his_socket",
        ],
    ),
    Case(
        id="t75-10-receipt-for-nothing",
        what="a read that marks nothing still tells",
        edits=[
            (
                MESSAGES_SERVICE,
                "        if not marked:\n            return\n        _, newest = max(marked)\n",
                "        newest = max(marked)[1] if marked else request.up_to_message_id\n",
            )
        ],
        expect=["test_my_own_messages_are_never_marked"],
    ),
    Case(
        id="t75-11-receipt-carries-the-hour",
        what="message.read carries the Thread's expiry (D-554)",
        edits=[
            (
                MESSAGES_SERVICE,
                '                "up_to_message_id": str(newest),\n',
                (
                    '                "up_to_message_id": str(newest),\n'
                    '                "expires_at": str(thread.expires_at),\n'
                ),
            )
        ],
        expect=["test_their_messages_up_to_the_one_named_are_read_and_they_alone_told"],
    ),
    Case(
        id="t75-12-typing-across-a-block",
        what="typing heard across a block",
        edits=[
            (
                MESSAGES_SERVICE,
                TYPING_ANCHOR,
                (
                    "        thread = await session.get(Thread, thread_id)\n"
                    "    if thread is None or user_id not in (thread.user_low, thread.user_high):\n"
                    "        return None\n"
                    "    return _other_of(thread, user_id)\n"
                ),
            )
        ],
        expect=["test_nothing_is_heard_across_a_block"],
    ),
    Case(
        id="t75-13-typing-in-anyones-thread",
        what="typing relayed in a Thread that isn't the typist's",
        edits=[
            (
                MESSAGES_SERVICE,
                TYPING_ANCHOR,
                (
                    "        thread = await session.get(Thread, thread_id)\n"
                    "    return None if thread is None else _other_of(thread, user_id)\n"
                ),
            )
        ],
        expect=["test_anything_else_is_dropped_and_the_socket_stays_open"],
    ),
    Case(
        id="t75-14-typing-unthrottled",
        what="every typing relayed, no 3 s throttle",
        edits=[
            (
                REALTIME,
                "        if not throttle.allowed:\n            return\n",
                "",
            )
        ],
        expect=["test_one_a_thread_every_three_seconds"],
    ),
    Case(
        id="t75-15-typing-no-ceiling",
        what="no ceiling across Threads",
        edits=[(REALTIME, CEILING, "")],
        expect=["test_forty_a_minute_in_all_then_nothing_is_read"],
    ),
    Case(
        id="t75-16-typing-ceiling-after-the-read",
        what="the ceiling counted only after the database said yes",
        edits=[
            (REALTIME, CEILING, ""),
            (
                REALTIME,
                "        if other is None:\n            return\n",
                "        if other is None:\n            return\n" + CEILING,
            ),
        ],
        expect=["test_forty_a_minute_in_all_then_nothing_is_read"],
    ),
    Case(
        id="t75-17-typing-echoed",
        what="typing echoed to the typist's own sockets",
        edits=[
            (
                REALTIME,
                '            [events.Event(other, TYPING, {"thread_id": str(thread_id)})], self._redis\n',
                (
                    "            [\n"
                    '                events.Event(u, TYPING, {"thread_id": str(thread_id)})\n'
                    "                for u in (other, self._user_id)\n"
                    "            ],\n"
                    "            self._redis,\n"
                ),
            )
        ],
        expect=["test_the_other_person_hears_it_and_the_typist_doesnt"],
    ),
    Case(
        id="t75-18-typing-names-the-typist",
        what="typing carries more than its Thread",
        edits=[
            (
                REALTIME,
                '[events.Event(other, TYPING, {"thread_id": str(thread_id)})]',
                '[events.Event(other, TYPING, {"thread_id": str(thread_id), "user_id": user})]',
            )
        ],
        expect=["test_the_other_person_hears_it_and_the_typist_doesnt"],
    ),
    Case(
        id="t75-19-opener-publishes-nothing",
        what="the socket's session drops its committed events",
        edits=[
            (
                OPENER,
                "            await events.publish(committed, redis)\n",
                "            pass\n",
            )
        ],
        expect=["test_the_opener_hands_its_connection_back_and_publishes_after"],
    ),
    Case(
        id="t75-20-opener-keeps-its-connection",
        what="the socket's session never closed, its connection held (D-557)",
        edits=[
            (
                OPENER,
                "            async with sessions() as session:\n",
                "            session = await sessions().__aenter__()\n            if True:\n",
            )
        ],
        expect=["test_the_opener_hands_its_connection_back_and_publishes_after"],
    ),
]

# --- T-8.5: kudos, once ever, only after talking (D-007, D-680) -----------------------

T85_SELECTION = ["tests/modules/kudos"]
KUDOS_SERVICE = "app/modules/kudos/service.py"
KUDOS_REPOSITORY = "app/modules/kudos/repository.py"

T85: list[Case] = [
    Case(
        id="t85-01-a-block-ignored",
        what="kudos given across a block, either way",
        edits=[(KUDOS_REPOSITORY, "            ~blocked_either_way(a, b),\n", "")],
        expect=[
            "test_a_block_either_way_is_not_found[giver]",
            "test_a_block_either_way_is_not_found[recipient]",
        ],
    ),
    Case(
        id="t85-02-a-deleted-account-reached",
        what="D-555: kudos reaching someone who deleted their account",
        edits=[
            (
                KUDOS_SERVICE,
                "        if await repository.status_of(session, request.to_id) is UserStatus.DELETED:\n",
                "        if False:\n",
            )
        ],
        expect=["test_nothing_reaches_a_deleted_account"],
    ),
    Case(
        id="t85-03-the-least-a-literal",
        what="kudos_min_messages written into the code, never read from app_config",
        edits=[
            (
                KUDOS_SERVICE,
                "    least = await admin_service.config_int(session, MIN_MESSAGES_KEY, cache=config)\n",
                "    least = 6\n",
            )
        ],
        # The rule is shared with the profile's kudos state (T-8.8, D-790).
        expect=[
            "test_give.py::test_the_least_is_read_from_app_config",
            "test_state.py::test_the_least_is_read_from_app_config",
        ],
    ),
    Case(
        id="t85-04-too-early-allowed",
        what="kudos given before the Thread has its six messages",
        edits=[
            (
                KUDOS_SERVICE,
                "    if thread.message_count < least:\n",
                "    if thread.message_count < 0:\n",
            )
        ],
        expect=[
            "test_give.py::test_six_messages_are_enough_and_five_too_few",
            "test_state.py::test_five_messages_are_too_early_and_six_enough",
        ],
    ),
    Case(
        id="t85-05-only-the-giver-has-written",
        what="D-680: kudos from someone the other never answered",
        edits=[
            (
                KUDOS_SERVICE,
                "    for writer in (a, b):\n",
                "    for writer in (a,):\n",
            )
        ],
        expect=[
            "test_give.py::test_a_one_sided_thread_is_too_early_for_either",
            "test_state.py::test_a_one_sided_thread_is_too_early_for_either",
        ],
    ),
    Case(
        id="t85-06-only-the-recipient-has-written",
        what="D-680: kudos from someone who never wrote a word",
        edits=[
            (
                KUDOS_SERVICE,
                "    for writer in (a, b):\n",
                "    for writer in (b,):\n",
            )
        ],
        expect=[
            "test_give.py::test_a_one_sided_thread_is_too_early_for_either",
            "test_state.py::test_a_one_sided_thread_is_too_early_for_either",
        ],
    ),
    Case(
        id="t85-07-a-second-kudos-a-500",
        what="a second kudos to the same person failing on the key, not refused",
        edits=[
            (
                KUDOS_REPOSITORY,
                "        .on_conflict_do_nothing(index_elements=[Kudos.from_id, Kudos.to_id])\n",
                "",
            )
        ],
        expect=[
            "test_a_second_kudos_to_them_already_exists[great_conversation]",
            "test_a_second_kudos_to_them_already_exists[really_thoughtful]",
            "test_two_kudos_at_once_are_one",
        ],
    ),
    Case(
        id="t85-08-mine-are-those-given",
        what="GET /me/kudos counting the kudos I gave, not those I was given",
        edits=[
            (
                KUDOS_REPOSITORY,
                "        .where(Kudos.to_id == user_id)\n",
                "        .where(Kudos.from_id == user_id)\n",
            )
        ],
        expect=["test_mine_are_counts_by_kind_of_those_received_only"],
    ),
    Case(
        id="t85-09-mine-list-kinds-never-given",
        what="GET /me/kudos listing kinds nobody gave, at zero",
        edits=[
            (
                KUDOS_SERVICE,
                "        Kudos(kind=kind, count=counts[kind]) for kind in KudosKind if kind in counts\n",
                "        Kudos(kind=kind, count=counts.get(kind, 0)) for kind in KudosKind\n",
            )
        ],
        expect=[
            "test_mine_are_counts_by_kind_of_those_received_only",
            "test_none_yet_is_an_empty_list",
        ],
    ),
    Case(
        id="t85-10-no-rate-limit",
        what="POST /kudos with only the 300 a minute every route has",
        edits=[
            (
                "app/modules/kudos/router.py",
                '    dependencies=[\n        Depends(user_rate_limit("kudos_give", limit=GIVES_PER_MINUTE, window_s=60))\n    ],\n',
                "",
            )
        ],
        expect=["test_giving_is_rate_limited_at_ten_a_minute"],
    ),
]

# --- T-7.9: voice notes, their upload, length and unlock --------------------------

T79_SELECTION = [
    "tests/modules/messages",
    "tests/modules/media",
    "tests/core/test_audio.py",
    "tests/core/test_storage_keys.py",
]
MEDIA_SERVICE = "app/modules/media/service.py"
AUDIO = "app/core/audio.py"

T79: list[Case] = [
    Case(
        id="t79-01-voice-from-a-man",
        what="a man's voice note let through (D-010's allowlist)",
        edits=[
            (
                MESSAGES_RULES,
                "    return gender is Gender.FEMALE\n",
                "    return gender is not None\n",
            )
        ],
        expect=["test_a_man_cant_send_one", "test_a_man_is_not_allowed"],
    ),
    Case(
        id="t79-02-upload-url-for-a-man",
        what="the upload URL not asking who asks",
        edits=[
            (
                MEDIA_SERVICE,
                (
                    "    if not messages_rules.may_send_voice(user.gender):\n"
                    '        raise AppError("NOT_ALLOWED", "That can\'t be sent here.", status=422)\n'
                ),
                "",
            )
        ],
        expect=["test_a_man_is_not_allowed"],
    ),
    Case(
        id="t79-03-upload-url-any-type",
        what="the upload URL signing any type",
        edits=[
            (
                MEDIA_SERVICE,
                (
                    "    if content_type not in audio.ACCEPTED_TYPES:\n"
                    "        raise messages_service.unsupported_audio()\n"
                    "    kind = next(t for t in audio.ACCEPTED_TYPES if t == content_type)\n"
                ),
                '    kind = "audio/webm"\n',
            )
        ],
        expect=["test_any_other_type_is_refused_saying_which_are_accepted"],
    ),
    Case(
        id="t79-04-upload-url-any-thread",
        what="the upload URL for a Thread not hers",
        edits=[
            (
                MEDIA_SERVICE,
                (
                    "        if thread is None:\n"
                    '            raise AppError("NOT_FOUND", "Not found.", status=404)\n'
                ),
                "        pass\n",
            )
        ],
        expect=[
            "test_a_thread_not_hers_is_not_found",
            "test_across_a_block_is_not_found",
        ],
    ),
    Case(
        id="t79-05-another-threads-key",
        what="a key from another Thread's upload URL accepted",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if parsed is None or parsed.thread_id != thread_id:\n",
                "    if parsed is None:\n",
            )
        ],
        expect=["test_a_key_her_url_didnt_give_for_this_thread_is_refused"],
    ),
    Case(
        id="t79-06-size-after-reading",
        what="an upload's size not asked before its bytes are read",
        edits=[
            (
                MESSAGES_SERVICE,
                "        if info.size > MAX_VOICE_BYTES:\n            raise _audio_too_large()\n",
                "        assert info\n",
            )
        ],
        expect=["test_over_2_mb_is_refused_before_a_byte_is_read"],
    ),
    Case(
        id="t79-07-bytes-size-unchecked",
        what="the bytes read not held to 2 MB",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if len(data) > MAX_VOICE_BYTES:\n        raise _audio_too_large()\n",
                "",
            )
        ],
        expect=["test_a_file_grown_since_its_size_was_asked_is_refused"],
    ),
    Case(
        id="t79-08-type-not-sniffed",
        what="the bytes not held to the type the URL was signed for",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if audio.sniff(data[: audio.SNIFF_BYTES]) != parsed.kind:\n",
                "    if audio.sniff(data[: audio.SNIFF_BYTES]) is None and False:\n",
            )
        ],
        expect=["test_bytes_that_arent_the_signed_audio_are_refused"],
    ),
    Case(
        id="t79-09-a-minute-and-more",
        what="a voice note over a minute let through",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if seconds > MAX_VOICE_SECONDS:\n",
                "    if seconds > MAX_VOICE_SECONDS + 1:\n",
            )
        ],
        expect=["test_over_a_minute_is_refused"],
    ),
    Case(
        id="t79-10-clients-length",
        what="the client's duration_s stored over the measured one",
        edits=[
            (
                MESSAGES_SERVICE,
                "        duration_s=voice.duration_s,\n",
                "        duration_s=request.duration_s or voice.duration_s,\n",
            )
        ],
        expect=["test_her_voice_note_is_kept_as_measured"],
    ),
    Case(
        id="t79-11-upload-key-kept",
        what="the message keeping the upload's key, which her URL can still write",
        edits=[
            (
                MESSAGES_SERVICE,
                "        media_key=voice.media_key,\n",
                "        media_key=voice.upload_key,\n",
            )
        ],
        expect=["test_her_voice_note_is_kept_as_measured"],
    ),
    Case(
        id="t79-12-kept-key-reused",
        what="each check writing to the same kept key",
        edits=[
            (
                MESSAGES_SERVICE,
                "    media_key = voice_key(thread_id, uuid4(), parsed.kind)\n",
                "    media_key = voice_key(thread_id, parsed.message_id, parsed.kind)\n",
            )
        ],
        expect=["test_a_put_again_after_the_send_changes_nothing_kept"],
    ),
    Case(
        id="t79-13-one-upload-two-notes",
        what="one upload sent twice not refused as ALREADY_EXISTS",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if await repository.message_exists(session, voice.message_id):\n",
                "    if False:\n",
            )
        ],
        expect=["test_a_put_again_after_the_send_changes_nothing_kept"],
    ),
    Case(
        id="t79-14-told-unlocked",
        what="message.new telling him her voice note is unlocked",
        edits=[
            (
                MESSAGES_SERVICE,
                "        locked = user_id == recipient_id and rules.locked_for(\n",
                "        locked = False and rules.locked_for(\n",
            )
        ],
        expect=["test_her_voice_note_is_kept_as_measured"],
    ),
    Case(
        id="t79-15-recipient-gender-unsaid",
        what="the send not saying the recipient's gender (a woman told it's locked)",
        edits=[
            (
                MESSAGES_SERVICE,
                "        recipient_gender=await repository.gender_of(session, other_id),\n",
                "",
            )
        ],
        expect=["test_a_woman_receiving_one_hears_it_free"],
    ),
    Case(
        id="t79-16-upload-left-behind",
        what="the upload not dropped once sent",
        edits=[
            (
                MESSAGES_SERVICE,
                "        await _drop_upload(storage, settings, voice.upload_key)\n",
                "        pass\n",
            )
        ],
        expect=["test_her_voice_note_is_kept_as_measured"],
    ),
    Case(
        id="t79-17-unlock-free",
        what="an unlock charging nothing",
        edits=[
            (
                MESSAGES_SERVICE,
                (
                    "            await pricing_service.charge(\n"
                    "                session,\n"
                    "                user,\n"
                    "                LedgerReason.VOICE_UNLOCK,\n"
                ),
                (
                    "            await pricing_service.price_for(\n"
                    "                session,\n"
                    "                user,\n"
                    "                LedgerReason.VOICE_UNLOCK,\n"
                ),
            ),
            (
                MESSAGES_SERVICE,
                "                shown=shown,\n                ref=Ref(RefType.MESSAGE, row.id),\n",
                "",
            ),
        ],
        expect=["test_he_pays_five_once_and_hears_it"],
    ),
    Case(
        id="t79-18-unlock-every-time",
        what="every unlock charging, recorded or not",
        edits=[
            (
                MESSAGES_SERVICE,
                "        ) and await repository.add_unlock(session, user_id, row.id):\n",
                "        ) and (await repository.add_unlock(session, user_id, row.id) or True):\n",
            )
        ],
        expect=["test_unlocking_again_charges_nothing"],
    ),
    Case(
        id="t79-19-unlock-unlocked",
        what="an unlock recorded for someone it was never locked for",
        edits=[
            (
                MESSAGES_SERVICE,
                "        if rules.locked_for(\n            row, user_id, gender, unlocked=False\n        ) and",
                "        if True and",
            )
        ],
        expect=[
            "test_its_sender_hears_it_free_with_nothing_recorded",
            "test_a_woman_receiving_one_hears_it_free_with_nothing_recorded",
        ],
    ),
    Case(
        id="t79-20-shown-ignored",
        what="the unlock not comparing the price he was shown (P-56)",
        edits=[
            (
                MESSAGES_SERVICE,
                "                shown=shown,\n                ref=Ref(RefType.MESSAGE, row.id),\n",
                "                shown=5,\n                ref=Ref(RefType.MESSAGE, row.id),\n",
            )
        ],
        expect=["test_a_price_he_wasnt_shown_is_refused_and_nothing_written"],
    ),
    Case(
        id="t79-21-anyones-voice-note",
        what="a voice note reached in a Thread not theirs",
        edits=[
            (
                MESSAGES_REPOSITORY,
                (
                    "            Message.kind == MessageKind.VOICE,\n"
                    "            or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),\n"
                ),
                "            Message.kind == MessageKind.VOICE,\n",
            )
        ],
        expect=["test_a_text_or_anyone_elses_note_is_not_found"],
    ),
    Case(
        id="t79-22-voice-across-a-block",
        what="a voice note reached across a block",
        edits=[
            (
                MESSAGES_REPOSITORY,
                (
                    "            or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),\n"
                    "            ~blocked_either_way(viewer_id, _other(viewer_id)),\n"
                    "        )\n"
                    "    )\n"
                    "    return found\n"
                    "\n"
                    "\n"
                    "async def add_unlock("
                ),
                (
                    "            or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),\n"
                    "        )\n"
                    "    )\n"
                    "    return found\n"
                    "\n"
                    "\n"
                    "async def add_unlock("
                ),
            )
        ],
        expect=[
            "tests/modules/messages/test_unlock.py::test_across_a_block_is_not_found"
        ],
    ),
    Case(
        id="t79-23-file-while-locked",
        what="a locked voice note's file handed out",
        edits=[
            (
                MESSAGES_SERVICE,
                "        if rules.locked_for(row, user.id, user.gender, unlocked):\n",
                "        if False:\n",
            )
        ],
        expect=["test_locked_its_file_is_not_allowed"],
    ),
    Case(
        id="t79-24-anyones-unlock",
        what="another man's unlock opening the file for him",
        edits=[
            (
                MESSAGES_REPOSITORY,
                "                MessageUnlock.user_id == user_id, MessageUnlock.message_id == message_id\n",
                "                MessageUnlock.message_id == message_id\n",
            )
        ],
        expect=["test_another_mans_unlock_opens_nothing_for_him"],
    ),
    Case(
        id="t79-25-unlock-conflict-raises",
        what="a second unlock breaking on the primary key",
        edits=[
            (
                MESSAGES_REPOSITORY,
                "        .on_conflict_do_nothing()\n",
                "",
            )
        ],
        expect=[
            "test_two_unlocks_at_once_record_one_and_charge_once",
            "test_unlocking_again_charges_nothing",
        ],
    ),
    Case(
        id="t79-26-webm-header-wins",
        what="a WebM's stated duration believed over its blocks",
        edits=[
            (
                AUDIO,
                "    return max(stated, Fraction(last_tick)) * scale / 1_000_000_000\n",
                "    return (stated or Fraction(last_tick)) * scale / 1_000_000_000\n",
            )
        ],
        expect=["test_the_longest_length_stated_wins"],
    ),
    Case(
        id="t79-27-mp4-fragments-ignored",
        what="an MP4's fragments not counted",
        edits=[
            (
                AUDIO,
                "        lengths.append(Fraction(finish, scales[track_id]))\n",
                "        pass\n",
            )
        ],
        expect=[
            "test_fragmented_mp4_lasts_to_where_its_fragments_end",
            "test_the_longest_length_stated_wins",
        ],
    ),
    Case(
        id="t79-28-webm-video",
        what="a WebM with a video track measured as audio",
        edits=[
            (
                AUDIO,
                (
                    "            if _uint(data, start, size) != _AUDIO_TRACK:\n"
                    '                raise ValueError("not an audio track")\n'
                ),
                "",
            )
        ],
        expect=["test_a_file_whose_length_cant_be_told_is_refused"],
    ),
    Case(
        id="t79-29-mp4-video",
        what="an MP4 with a video track measured as audio",
        edits=[
            (
                AUDIO,
                '    if data[hdlr[0] + 8 : hdlr[0] + 12] != b"soun":\n',
                '    if data[hdlr[0] + 8 : hdlr[0] + 12] == b"none":\n',
            )
        ],
        expect=["test_a_file_whose_length_cant_be_told_is_refused"],
    ),
    Case(
        id="t79-30-ogg-pre-skip",
        what="Opus's pre-skip counted as sound",
        edits=[
            (
                AUDIO,
                "    return Fraction(last - pre_skip, _OPUS_RATE)\n",
                "    return Fraction(last, _OPUS_RATE)\n",
            )
        ],
        expect=["test_ogg_opus_lasts_to_its_last_granule_less_the_pre_skip"],
    ),
    Case(
        id="t79-31-ogg-two-streams",
        what="an Ogg with a second stream measured as one",
        edits=[
            (
                AUDIO,
                "    if any(other != serial for _, other, _ in _ogg_pages(data)):\n",
                "    if False:\n",
            )
        ],
        expect=["test_a_file_whose_length_cant_be_told_is_refused"],
    ),
    Case(
        id="t79-32-empty-file-escapes",
        what="an empty file escaping the refusal",
        edits=[(AUDIO, "        StopIteration,\n", "")],
        expect=["test_a_file_whose_length_cant_be_told_is_refused"],
    ),
    Case(
        id="t79-33-zero-seconds",
        what="a fraction of a second kept as 0",
        edits=[
            (
                AUDIO,
                "    return max(1, int(seconds + Fraction(1, 2)))\n",
                "    return int(seconds + Fraction(1, 2))\n",
            )
        ],
        expect=["test_lengths_are_kept_to_the_nearest_second"],
    ),
    Case(
        id="t79-34-storage-before-the-thread",
        what="storage asked about an upload before the Thread is known to be hers",
        edits=[
            (
                MESSAGES_SERVICE,
                (
                    "    if request.kind is MessageKind.VOICE:\n"
                    "        if not rules.may_send_voice(gender):\n"
                ),
                (
                    "    if request.media_key is not None:\n"
                    "        await storage.head(settings.R2_BUCKET_PRIVATE, request.media_key)\n"
                    "    if request.kind is MessageKind.VOICE:\n"
                    "        if not rules.may_send_voice(gender):\n"
                ),
            )
        ],
        expect=["test_a_thread_not_hers_is_not_found_before_storage_is_asked"],
    ),
    Case(
        id="t79-35-any-upload-key",
        what="a key of any shape read as an upload's",
        edits=[
            (
                "app/core/storage_keys.py",
                '_VOICE_UPLOAD = re.compile(rf"voice-uploads/({_UUID})/({_UUID})\\.([a-z0-9]+)")\n',
                '_VOICE_UPLOAD = re.compile(rf"voice(?:-uploads)?/({_UUID})/({_UUID})\\.([a-z0-9]+)")\n',
            )
        ],
        expect=["test_a_key_the_upload_url_never_gave_reads_as_none"],
    ),
]


# --- T-8.9: gifts (D-650, D-652, D-653) --------------------------------------------

T89_SELECTION = [
    "tests/modules/gifts",
    "tests/test_schema.py",
]
GIFTS_SERVICE = "app/modules/gifts/service.py"
GIFTS_REPO = "app/modules/gifts/repository.py"
GIFTS_RULES = "app/modules/gifts/rules.py"
GIFTS_MODELS = "app/modules/gifts/models.py"
GIFTS_KEY = "alembic/versions/20261008_5978faceb05b_gift_sends_idempotency_key.py"
REACH = (
    "    if recipient_id == user.id or not await discovery_service.can_reach(\n"
    "        session, user, recipient_id, mutual=True\n"
    "    ):\n"
)

T89: list[Case] = [
    Case(
        id="t89-01-a-woman-sends",
        what="D-016: a woman's send let through",
        edits=[
            (
                GIFTS_SERVICE,
                "    if user.gender is not Gender.MALE:\n        raise _not_allowed()\n    async with session.begin():\n",
                "    async with session.begin():\n",
            )
        ],
        expect=["test_a_woman_sending_is_not_allowed"],
    ),
    Case(
        id="t89-02-reach-never-asked",
        what="D-653: anyone sent a gift, across a block, hidden or not done",
        edits=[(GIFTS_SERVICE, REACH, "    if recipient_id == user.id:\n")],
        expect=[
            "test_a_block_either_way_is_not_found_never_revealed[she blocked him]",
            "test_a_block_either_way_is_not_found_never_revealed[he blocked her]",
            "test_someone_he_cant_reach_is_not_found[not done]",
            "test_someone_he_cant_reach_is_not_found[hidden]",
            "test_someone_he_cant_reach_is_not_found[paused]",
            "test_someone_he_cant_reach_is_not_found[frozen by moderation]",
            "test_someone_he_cant_reach_is_not_found[seeking women]",
        ],
    ),
    Case(
        id="t89-03-reach-not-mutual",
        what="D-653: a woman who doesn't want men sent one anyway",
        edits=[
            (
                GIFTS_SERVICE,
                "        session, user, recipient_id, mutual=True\n",
                "        session, user, recipient_id, mutual=False\n",
            )
        ],
        expect=["test_someone_he_cant_reach_is_not_found[seeking women]"],
    ),
    Case(
        id="t89-04-a-man-gifted",
        what="D-016: a gift to a man he can reach",
        edits=[
            (
                GIFTS_SERVICE,
                "    if await threads_repository.gender_of(session, recipient_id) is not Gender.FEMALE:\n        raise _not_allowed()\n",
                "",
            )
        ],
        expect=["test_a_man_he_can_reach_is_not_allowed"],
    ),
    Case(
        id="t89-05-a-retired-gift-sold",
        what="D-252: smile and wave, retired, sold again",
        edits=[
            (
                GIFTS_SERVICE,
                "    if gift is None or not gift.active:\n",
                "    if gift is None:\n",
            )
        ],
        expect=[
            "test_a_gift_not_on_sale_is_not_found[smile]",
            "test_a_gift_not_on_sale_is_not_found[wave]",
        ],
    ),
    Case(
        id="t89-06-no-cooldown",
        what="D-016: the same gift to the same woman, again and again",
        edits=[
            (
                GIFTS_SERVICE,
                "    if wait := rules.cooldown_left(last, now, hours):\n        raise rules.cooldown(wait)\n",
                "",
            )
        ],
        expect=[
            "test_the_same_gift_to_the_same_woman_waits_the_cooldown",
            "test_a_paid_send_waits_the_cooldown_too",
        ],
    ),
    Case(
        id="t89-07-cooldown-a-literal",
        what="the cooldown's hours written in the code, not read from app_config",
        edits=[
            (
                GIFTS_SERVICE,
                "    hours = await admin_service.config_int(session, rules.COOLDOWN_KEY, cache=config)\n",
                "    hours = 24\n",
            )
        ],
        expect=["test_the_same_gift_to_the_same_woman_waits_the_cooldown"],
    ),
    Case(
        id="t89-08-every-send-free",
        what="D-231: past the week's fifteen, still free",
        edits=[
            (
                GIFTS_SERVICE,
                "    price = rules.price_of(gift.credits, free_used=used, free_limit=limit)\n",
                "    price = 0\n",
            )
        ],
        expect=[
            "test_fifteen_free_sends_write_no_ledger_row_and_the_sixteenth_pays_the_row",
            "test_the_free_sends_are_the_setting_never_a_number",
            "test_too_few_velas_takes_the_send_back_too",
        ],
    ),
    Case(
        id="t89-09-free-sends-a-literal",
        what="the week's free sends written in the code, not read from app_config",
        edits=[
            (
                GIFTS_SERVICE,
                "    limit = await admin_service.config_int(session, rules.FREE_WEEKLY_KEY, cache=config)\n",
                "    limit = 15\n",
            )
        ],
        expect=[
            "test_the_free_sends_are_the_setting_never_a_number",
            "test_send.py::test_the_week_starts_monday_at_midnight_ist",
        ],
    ),
    Case(
        id="t89-10-the-week-in-utc",
        what="D-650: the week read from the UTC date, not India's",
        edits=[
            (
                GIFTS_RULES,
                "    today = now.astimezone(IST).date()\n",
                "    today = now.date()\n",
            )
        ],
        expect=[
            "test_send.py::test_the_week_starts_monday_at_midnight_ist",
            "test_rules.py::test_the_week_starts_monday_at_midnight_ist",
        ],
    ),
    Case(
        id="t89-11-free-sends-never-come-back",
        what="D-650: free sends counted forever, not from this week's Monday",
        edits=[
            (
                GIFTS_REPO,
                "            GiftSend.credits_charged == 0,\n            GiftSend.created_at >= since,\n",
                "            GiftSend.credits_charged == 0,\n",
            )
        ],
        expect=["test_send.py::test_the_week_starts_monday_at_midnight_ist"],
    ),
    Case(
        id="t89-12-price-a-literal",
        what="D-016: the price from a table in the code, not the gifts row",
        edits=[
            (
                GIFTS_SERVICE,
                "    price = rules.price_of(gift.credits, free_used=used, free_limit=limit)\n",
                '    price = rules.price_of(\n        {"coffee": 5, "rose": 10, "chocolate": 15, "teddy": 20}[gift.id],\n        free_used=used,\n        free_limit=limit,\n    )\n',
            )
        ],
        expect=[
            "test_fifteen_free_sends_write_no_ledger_row_and_the_sixteenth_pays_the_row",
            "test_the_catalogue_is_held_a_minute_and_a_send_reads_the_row",
        ],
    ),
    Case(
        id="t89-13-shown-never-compared",
        what="D-600: a man charged a price he wasn't shown",
        edits=[
            (
                GIFTS_SERVICE,
                "    if price != request.shown_price:\n        raise pricing_service.price_changed(price)\n",
                "",
            )
        ],
        expect=[
            "test_a_price_other_than_the_one_shown_is_refused_with_nothing_written",
            "test_send.py::test_the_week_starts_monday_at_midnight_ist",
            "test_the_catalogue_is_held_a_minute_and_a_send_reads_the_row",
        ],
    ),
    Case(
        id="t89-14-absent-skips",
        what="D-600: a send without shown_price let through, failing open",
        edits=[
            (
                GIFTS_SERVICE,
                "    if price != request.shown_price:\n",
                "    if request.shown_price and price != request.shown_price:\n",
            )
        ],
        expect=[
            "test_a_price_other_than_the_one_shown_is_refused_with_nothing_written[0-rose-None-10]",
            "test_send.py::test_the_week_starts_monday_at_midnight_ist",
        ],
    ),
    Case(
        id="t89-15-never-debited",
        what="rule 5: a paid send with no debit",
        edits=[
            (
                GIFTS_SERVICE,
                "    if price > 0:\n        await wallet_service.debit(\n            session,\n            user.id,\n            price,\n            LedgerReason.GIFT,\n            ref=Ref(RefType.GIFT_SEND, row.id),\n        )\n",
                "",
            )
        ],
        expect=[
            "test_fifteen_free_sends_write_no_ledger_row_and_the_sixteenth_pays_the_row",
            "test_too_few_velas_takes_the_send_back_too",
            "test_the_same_key_again_is_the_same_send_charged_once",
        ],
    ),
    Case(
        id="t89-16-a-refused-debit-kept-the-send",
        what="rule 5: the send kept when its debit is refused",
        edits=[
            (
                GIFTS_SERVICE,
                "    if price > 0:\n        await wallet_service.debit(\n            session,\n            user.id,\n            price,\n            LedgerReason.GIFT,\n            ref=Ref(RefType.GIFT_SEND, row.id),\n        )\n",
                "    if price > 0:\n        try:\n            await wallet_service.debit(\n                session,\n                user.id,\n                price,\n                LedgerReason.GIFT,\n                ref=Ref(RefType.GIFT_SEND, row.id),\n            )\n        except AppError:\n            pass\n",
            )
        ],
        expect=["test_too_few_velas_takes_the_send_back_too"],
    ),
    Case(
        id="t89-17-the-key-never-looked-up",
        what="D-653: a retry with the same key, a second send",
        edits=[
            (
                GIFTS_SERVICE,
                "    existing = await repository.by_key(session, user.id, key)\n",
                "    existing = None\n",
            )
        ],
        expect=[
            "test_the_same_key_again_is_the_same_send_charged_once",
            "test_one_key_twice_at_once_is_one_send",
        ],
    ),
    Case(
        id="t89-18-a-key-reused-for-another-gift",
        what="D-653: a key sent again for another gift returns the first",
        edits=[
            (
                GIFTS_SERVICE,
                "        if (existing.recipient_id, existing.gift_id) != (\n",
                "        if False and (existing.recipient_id, existing.gift_id) != (\n",
            )
        ],
        expect=[
            "test_the_same_key_for_another_send_already_exists[another gift]",
            "test_the_same_key_for_another_send_already_exists[another woman]",
        ],
    ),
    Case(
        id="t89-19-no-sender-lock",
        what="D-653: two sends at once, each counting the same free sends",
        edits=[
            (
                GIFTS_REPO,
                '    await session.execute(\n        text("SELECT pg_advisory_xact_lock(:lock, hashtext(CAST(:s AS text)))"),\n        {"lock": SENDER_LOCK, "s": str(sender_id)},\n    )\n',
                "    return None\n",
            )
        ],
        expect=[
            "test_two_sends_at_once_share_one_free_send",
            "test_one_key_twice_at_once_is_one_send",
        ],
    ),
    Case(
        id="t89-20-an-expired-thread-linked",
        what="an expired Thread linked to a gift, by its status or by the clock",
        edits=[
            (
                GIFTS_SERVICE,
                "    if thread is None or threads_rules.has_expired(thread, now):\n",
                "    if thread is None:\n",
            )
        ],
        expect=[
            "test_a_live_thread_is_linked_and_none_is_ever_opened[expired-False]",
            "test_a_live_thread_is_linked_and_none_is_ever_opened[expired by the clock-False]",
        ],
    ),
    Case(
        id="t89-21-she-is-never-told",
        what="gift.received never queued",
        edits=[
            (
                GIFTS_SERVICE,
                "    events.queue(session, recipient_id, GIFT_RECEIVED, payload)\n",
                "",
            )
        ],
        expect=["test_a_free_send_moves_no_vela_and_she_is_told"],
    ),
    Case(
        id="t89-22-gifts-across-a-block-listed",
        what="her list showing gifts from someone a block stands between",
        edits=[
            (
                GIFTS_REPO,
                "            ~blocked_either_way(recipient_id, sender.id),\n",
                "",
            )
        ],
        expect=[
            "test_gifts_from_across_a_block_are_left_out[she blocked him]",
            "test_gifts_from_across_a_block_are_left_out[he blocked her]",
        ],
    ),
    Case(
        id="t89-23-show-gifts-ignored",
        what="show_gifts off, her counts shown anyway",
        edits=[
            (
                GIFTS_SERVICE,
                "            if not await repository.shows_gifts(session, user_id):\n                return schemas.GiftCounts(counts=[])\n",
                "",
            )
        ],
        expect=["test_show_gifts_off_hides_them_from_all_but_her"],
    ),
    Case(
        id="t89-24-counts-across-a-block",
        what="D-493: her counts read across a block",
        edits=[
            (
                GIFTS_SERVICE,
                "            if not await discovery_service.can_reach(\n                session, user, user_id, mutual=False\n            ):\n                raise _not_found()\n",
                "",
            )
        ],
        expect=["test_counts_across_a_block_are_not_found"],
    ),
    Case(
        id="t89-25-catalogue-never-held",
        what="P-47: the catalogue read on every request",
        edits=[
            (
                GIFTS_SERVICE,
                "    if cache.gifts is not None and cache.at is not None and now - cache.at < CACHED_FOR:\n",
                "    if False:\n",
            )
        ],
        expect=["test_the_catalogue_is_held_a_minute_and_a_send_reads_the_row"],
    ),
    Case(
        id="t89-26-catalogue-held-forever",
        what="P-47: the catalogue never read again",
        edits=[
            (
                GIFTS_SERVICE,
                "    if cache.gifts is not None and cache.at is not None and now - cache.at < CACHED_FOR:\n",
                "    if cache.gifts is not None:\n",
            )
        ],
        expect=["test_the_catalogue_is_held_a_minute_and_a_send_reads_the_row"],
    ),
    Case(
        id="t89-27-retired-gifts-shown",
        what="D-252: smile and wave on sale in the catalogue",
        edits=[
            (
                GIFTS_REPO,
                "        select(Gift).where(Gift.active).order_by(Gift.sort, Gift.id)\n",
                "        select(Gift).order_by(Gift.sort, Gift.id)\n",
            )
        ],
        expect=[
            "test_a_man_sees_the_four_and_his_free_sends_left",
            "test_a_woman_sees_the_gifts_and_no_free_sends",
        ],
    ),
    Case(
        id="t89-28-key-not-unique",
        what="D-653: the key no longer unique per sender (migration and model)",
        edits=[
            (
                GIFTS_KEY,
                '    op.create_unique_constraint(\n        "uq_gift_sends_sender_id_idempotency_key",\n        "gift_sends",\n        ["sender_id", "idempotency_key"],\n    )\n',
                "",
            ),
            (
                GIFTS_KEY,
                '    op.drop_constraint(\n        "uq_gift_sends_sender_id_idempotency_key", "gift_sends", type_="unique"\n    )\n',
                "",
            ),
            (
                GIFTS_MODELS,
                '        UniqueConstraint("sender_id", "idempotency_key"),\n',
                "",
            ),
        ],
        expect=["test_a_gift_send_keeps_its_key_once_per_sender"],
    ),
    Case(
        id="t89-29-no-backfill",
        what="the migration failing on a send from before it",
        edits=[
            (
                GIFTS_KEY,
                '    op.execute("UPDATE gift_sends SET idempotency_key = id::text")\n',
                "",
            )
        ],
        expect=[
            "test_a_send_from_before_gets_its_id_as_its_key_and_going_back_keeps_it"
        ],
    ),
]

# --- P-152: debit() checks who awaits it (D-651) -------------------------------------

P152_SELECTION = [
    "tests/modules/pricing/test_debit_callers.py",
    "tests/modules/gifts/test_send.py",
]
P152: list[Case] = [
    Case(
        id="p152-01-never-checked",
        what="D-651: debit() awaited by anyone, a name built at run time included",
        edits=[
            (
                SERVICE,
                "    if not _may_debit(sys._getframe(1)):\n",
                "    if False and not _may_debit(sys._getframe(1)):\n",
            )
        ],
        expect=[
            "test_a_debit_by_a_name_built_at_run_time_is_refused",
            "test_the_list_names_a_function_in_its_module",
            "test_a_debit_with_no_caller_of_its_own_is_refused",
        ],
    ),
    Case(
        id="p152-02-the-name-alone",
        what="D-651: a listed function's name trusted in any module",
        edits=[
            (
                SERVICE,
                "    return (module, caller.f_code.co_qualname) in DEBIT_CALLERS\n",
                "    return caller.f_code.co_qualname in {name for _, name in DEBIT_CALLERS}\n",
            )
        ],
        expect=[
            "test_the_list_names_a_function_in_its_module[app.modules.never_named_2031.service-charge]"
        ],
    ),
    Case(
        id="p152-03-tests-a-prefix",
        what="D-651: any module whose name starts with tests passed as test code",
        edits=[
            (
                SERVICE,
                '    if module == TESTS_PACKAGE or module.startswith(TESTS_PACKAGE + "."):\n',
                "    if module.startswith(TESTS_PACKAGE):\n",
            )
        ],
        expect=[
            "test_the_list_names_a_function_in_its_module[testsuite_2031.service-buy]"
        ],
    ),
    Case(
        id="p152-04-the-lists-drift",
        what="D-651: debit()'s list grown without the scan's",
        edits=[
            (
                SERVICE,
                '        ("app.modules.admin.panel", "_correct"),\n    }\n',
                '        ("app.modules.admin.panel", "_correct"),\n        ("app.modules.threads.service", "_open_in"),\n    }\n',
            )
        ],
        expect=["test_the_run_time_list_is_the_scans"],
    ),
    Case(
        id="p152-05-gift-sending-unlisted",
        what="D-651: gift sending left off debit()'s list",
        edits=[
            (
                SERVICE,
                '        ("app.modules.gifts.service", "_send_in"),\n        # An admin',
                "        # An admin",
            )
        ],
        expect=[
            "test_the_run_time_list_is_the_scans",
            "test_fifteen_free_sends_write_no_ledger_row_and_the_sixteenth_pays_the_row",
        ],
    ),
]


# --- T-8.6: referrals, and P-63's lock order ----------------------------------------

WALLET_SERVICE = "app/modules/wallet/service.py"
REFERRALS_SERVICE = "app/modules/referrals/service.py"
REFERRALS_RULES = "app/modules/referrals/rules.py"
REFERRALS_REPO = "app/modules/referrals/repository.py"
REFERRALS_ROUTER = "app/modules/referrals/router.py"
REFERRAL_SETTINGS = "alembic/versions/20261008_0e6719809c1b_referral_settings.py"
WEBHOOKS = "app/modules/payments/webhooks.py"
VERIFICATION_SERVICE = "app/modules/verification/service.py"
T86_SELECTION = [
    "tests/modules/referrals",
    "tests/modules/wallet",
    "tests/test_reference_data.py",
]
BELOW_REFUSED = "test_a_wallet_below_one_held_is_refused_and_nothing_is_written"
NO_DEADLOCK = "test_two_transactions_locking_two_men_in_opposite_orders_never_deadlock"
SELFIE_BOTH = "test_a_mans_selfie_matching_pays_both_men_once"
PURCHASE_BOTH = "test_a_first_purchase_pays_both_men_inside_the_capture"
FROZEN_REFEREE = (
    "test_a_referee_who_no_longer_stands_gets_nothing_and_the_referrer_is_paid"
)
REFERRER_GONE = (
    "test_a_referrer_who_no_longer_stands_gets_nothing_and_the_referee_is_paid"
)
NOT_STANDING = "test_a_code_whose_owner_doesnt_stand_is_the_same_not_found"

T86: list[Case] = [
    Case(
        id="t86-01-lock-order-unguarded",
        what="P-63: a wallet below one the transaction holds locked anyway",
        edits=[
            (
                WALLET_SERVICE,
                "    if user_id not in held and held and user_id < max(held):\n",
                "    if False:\n",
            )
        ],
        expect=[
            BELOW_REFUSED,
            "test_lock_wallets_still_refuses_one_below_a_wallet_held",
            NO_DEADLOCK,
        ],
    ),
    Case(
        id="t86-02-held-never-recorded",
        what="P-63: the wallets a transaction locks never recorded, so nothing is refused",
        edits=[
            (
                WALLET_SERVICE,
                "    held.add(user_id)\n    return locked\n",
                "    return locked\n",
            )
        ],
        expect=[BELOW_REFUSED, NO_DEADLOCK],
    ),
    Case(
        id="t86-03-held-never-forgotten",
        what="P-63: what a transaction held outlives it",
        edits=[
            (
                WALLET_SERVICE,
                "    if transaction.parent is None:\n        session.info.pop(_HELD, None)\n",
                "    return\n",
            )
        ],
        expect=["test_what_a_transaction_holds_ends_with_it"],
    ),
    Case(
        id="t86-04-lock-wallets-unsorted",
        what="P-63: lock_wallets() locks in the order it was given",
        edits=[
            (
                WALLET_SERVICE,
                "    for user_id in sorted(set(user_ids) - _held(session)):\n",
                "    for user_id in [u for u in dict.fromkeys(user_ids) if u not in _held(session)]:\n",
            )
        ],
        expect=[
            "test_lock_wallets_sorts_them_so_any_order_of_credits_applies[descending]",
            f"{SELFIE_BOTH}[below]",
            f"{PURCHASE_BOTH}[below]",
        ],
    ),
    Case(
        id="t86-05-reward-after-the-purchase",
        what="P-63: the webhook's reward run after the purchase has locked the buyer",
        edits=[
            (
                WEBHOOKS,
                '    await referrals_service.reward(session, row.user_id, "purchase")\n',
                "",
            ),
            (
                WEBHOOKS,
                '    log.info(\n        "payments.captured",\n',
                (
                    '    await referrals_service.reward(session, row.user_id, "purchase")\n'
                    '    log.info(\n        "payments.captured",\n'
                ),
            ),
        ],
        expect=[f"{PURCHASE_BOTH}[below]", f"{FROZEN_REFEREE}[below]"],
    ),
    Case(
        id="t86-06-only-the-paid-locked",
        what="P-63: the reward locks only whoever is paid, one at a time",
        edits=[
            (
                REFERRALS_SERVICE,
                "    await wallet_service.lock_wallets(session, [referee_id, referrer_id])\n",
                "",
            )
        ],
        expect=[
            f"{SELFIE_BOTH}[below]",
            f"{PURCHASE_BOTH}[below]",
            f"{FROZEN_REFEREE}[below]",
        ],
    ),
    Case(
        id="t86-07-a-woman-credited",
        what="D-076, D-690: the reward's allowlist lets a woman through",
        edits=[
            (
                REFERRALS_RULES,
                "CREDITED_GENDERS: Final = frozenset({Gender.MALE})\n",
                "CREDITED_GENDERS: Final = frozenset({Gender.MALE, Gender.FEMALE})\n",
            )
        ],
        expect=[
            "test_a_womans_selfie_pays_her_referrer_and_never_her",
            "test_two_women_are_rewarded_with_nothing",
            "test_a_man_referred_by_a_woman_is_paid_and_she_never_is",
        ],
    ),
    Case(
        id="t86-08-standing-ignored-at-the-reward",
        what="D-693: a man banned, frozen or deleted since still paid",
        edits=[
            (
                REFERRALS_RULES,
                "    return gender in CREDITED_GENDERS and status in STANDING\n",
                "    return gender in CREDITED_GENDERS\n",
            )
        ],
        expect=[
            f"{REFERRER_GONE}[banned]",
            f"{REFERRER_GONE}[frozen]",
            f"{REFERRER_GONE}[deleted]",
            f"{FROZEN_REFEREE}[below]",
            f"{FROZEN_REFEREE}[above]",
        ],
    ),
    Case(
        id="t86-09-no-cap",
        what="D-692: the referrer paid past referral_rewards_max",
        edits=[
            (
                REFERRALS_SERVICE,
                "    if await wallet_service.referral_rewards_paid(session, referrer_id) < cap:\n",
                "    if True:\n",
            )
        ],
        expect=[
            "test_past_the_cap_the_referrer_gets_nothing_and_the_referee_is_paid",
            "test_two_rewards_at_once_one_short_of_the_cap_pay_him_once",
        ],
    ),
    Case(
        id="t86-10-cap-counted-before-the-lock",
        what="D-692: the cap counted before his wallet is locked",
        edits=[
            (
                WALLET_SERVICE,
                (
                    "    if referrer_id not in _held(session):\n"
                    '        raise WalletMisuse("referral_rewards_paid() reads under the wallet\'s lock")\n'
                ),
                "",
            ),
            (
                REFERRALS_SERVICE,
                "    await wallet_service.lock_wallets(session, [referee_id, referrer_id])\n",
                "",
            ),
            (
                REFERRALS_SERVICE,
                "    ref = Ref(RefType.REFERRAL, referee_id)\n",
                (
                    "    await wallet_service.lock_wallets(session, [referee_id, referrer_id])\n"
                    "    ref = Ref(RefType.REFERRAL, referee_id)\n"
                ),
            ),
        ],
        expect=["test_two_rewards_at_once_one_short_of_the_cap_pay_him_once"],
    ),
    Case(
        id="t86-11-cap-fails-open",
        what="D-692: a missing referral_rewards_max pays every referrer",
        edits=[
            (
                REFERRALS_SERVICE,
                (
                    '        log.warning("referrals.cap_config_missing", key=rules.REWARDS_MAX_KEY, **fields)\n'
                    "        return False\n"
                ),
                (
                    '        log.warning("referrals.cap_config_missing", key=rules.REWARDS_MAX_KEY, **fields)\n'
                    "        return True\n"
                ),
            )
        ],
        expect=["test_a_missing_cap_pays_no_referrer_and_says_so"],
    ),
    Case(
        id="t86-12-own-reward-counted",
        what="D-692: his own reward as a referee counted toward his cap",
        edits=[
            (
                "app/modules/wallet/repository.py",
                "            LedgerEntry.ref_id != user_id,\n",
                "",
            )
        ],
        expect=["test_his_own_reward_as_a_referee_never_counts_toward_his_cap"],
    ),
    Case(
        id="t86-13-never-marked-rewarded",
        what="T-8.6: rewarded_at never set",
        edits=[(REFERRALS_SERVICE, "    referral.rewarded_at = clock.now()\n", "")],
        expect=[
            "test_a_womans_selfie_pays_her_referrer_and_never_her",
            "test_two_women_are_rewarded_with_nothing",
        ],
    ),
    Case(
        id="t86-14-zero-left-unrewarded",
        what="D-692: a reward of 0 leaves the referral for the next trigger",
        edits=[
            (
                REFERRALS_SERVICE,
                "        amount = 0\n\n",
                "        amount = 0\n    if amount == 0:\n        return\n\n",
            )
        ],
        expect=["test_at_zero_or_below_it_is_rewarded_with_nothing[zero]"],
    ),
    Case(
        id="t86-15-missing-setting-fails-the-trigger",
        what="D-692: a missing referral_reward_velas row fails the webhook and the selfie",
        edits=[
            (
                REFERRALS_SERVICE,
                (
                    "    except admin_service.MissingConfig:\n"
                    '        log.warning("referrals.reward_config_missing"'
                ),
                (
                    "    except LookupError:\n"
                    '        log.warning("referrals.reward_config_missing"'
                ),
            )
        ],
        expect=[
            "test_a_missing_setting_skips_with_a_warning_and_a_later_trigger_pays[no row]",
            "test_a_missing_setting_skips_with_a_warning_and_a_later_trigger_pays[not a number]",
        ],
    ),
    Case(
        id="t86-16-no-selfie-trigger",
        what="T-8.6: a matched selfie rewards nothing",
        edits=[
            (
                VERIFICATION_SERVICE,
                '            await referrals_service.reward(session, user.id, "selfie")\n',
                "",
            )
        ],
        expect=[f"{SELFIE_BOTH}[below]", f"{SELFIE_BOTH}[above]"],
    ),
    Case(
        id="t86-17-no-purchase-trigger",
        what="T-8.6: a first purchase rewards nothing",
        edits=[
            (
                WEBHOOKS,
                '    await referrals_service.reward(session, row.user_id, "purchase")\n',
                "",
            )
        ],
        expect=[f"{PURCHASE_BOTH}[below]", f"{PURCHASE_BOTH}[above]"],
    ),
    Case(
        id="t86-18-apply-after-done",
        what="T-8.6: a code applied once onboarding is done",
        edits=[
            (
                REFERRALS_SERVICE,
                "        if user.onboarding_step is OnboardingStep.DONE:\n",
                "        if False:\n",
            )
        ],
        expect=["test_once_onboarding_is_done_it_is_not_allowed"],
    ),
    Case(
        id="t86-19-own-code",
        what="T-8.6: one's own code taken for someone else's",
        edits=[
            (
                REFERRALS_SERVICE,
                "        if owner is not None and owner.id == user.id:\n",
                "        if False:\n",
            )
        ],
        expect=["test_ones_own_code_is_not_allowed"],
    ),
    Case(
        id="t86-20-number-check-gone",
        what="D-691: no check that the number was ever a referee",
        edits=[
            (
                REFERRALS_SERVICE,
                "        if await repository.number_was_referred(session, user.phone_hash):\n",
                "        if False:\n",
            )
        ],
        expect=[
            "test_a_second_code_is_already_exists_and_the_first_stands",
            "test_apply_delete_wait_out_the_erasure_sign_up_again_is_already_exists",
        ],
    ),
    Case(
        id="t86-21-live-accounts-only",
        what="D-691: the number's check reads live accounts only, so an erasure escapes it",
        edits=[
            (
                REFERRALS_REPO,
                "            .where(User.phone_hash == phone_hash)\n",
                (
                    "            .where(User.phone_hash == phone_hash)\n"
                    "            .where(User.anonymised_at.is_(None))\n"
                ),
            )
        ],
        expect=[
            "test_apply_delete_wait_out_the_erasure_sign_up_again_is_already_exists"
        ],
    ),
    Case(
        id="t86-22-any-owner-status",
        what="D-693: a banned, frozen or deleted owner's code works",
        edits=[
            (
                REFERRALS_RULES,
                "    return step is OnboardingStep.DONE and status in STANDING\n",
                "    return step is OnboardingStep.DONE\n",
            )
        ],
        expect=[
            f"{NOT_STANDING}[banned]",
            f"{NOT_STANDING}[frozen]",
            f"{NOT_STANDING}[deleted]",
        ],
    ),
    Case(
        id="t86-23-owner-not-done",
        what="D-693: the code of someone still signing up works",
        edits=[
            (
                REFERRALS_RULES,
                "    return step is OnboardingStep.DONE and status in STANDING\n",
                "    return status in STANDING\n",
            )
        ],
        expect=[f"{NOT_STANDING}[not done]", f"{NOT_STANDING}[at dob]"],
    ),
    Case(
        id="t86-24-apply-unlocked",
        what="T-8.6: apply reads the user without locking the row",
        edits=[
            (
                REFERRALS_SERVICE,
                "        user = await users_service.locked_user(session, user.id)\n",
                "        user = await session.get(User, user.id)  # type: ignore[assignment]\n",
            )
        ],
        expect=["test_two_applies_at_once_take_turns_and_the_second_already_exists"],
    ),
    Case(
        id="t86-25-no-rate-limit",
        what="T-8.6: apply without its own limit",
        edits=[
            (REFERRALS_ROUTER, "APPLIES_PER_HOUR = 10\n", "APPLIES_PER_HOUR = 1000\n")
        ],
        expect=["test_the_eleventh_apply_in_an_hour_is_rate_limited"],
    ),
    Case(
        id="t86-26-setting-not-migrated",
        what="D-692: the migration seeds no referral_reward_velas",
        edits=[
            (
                REFERRAL_SETTINGS,
                'SETTINGS = (("referral_reward_velas", 5), ("referral_rewards_max", 10))\n',
                'SETTINGS = (("referral_rewards_max", 10),)\n',
            )
        ],
        expect=["test_app_config_seeds"],
    ),
]

# --- T-6.9: the Online now filter (D-660) ----------------------------------------------

T69_SELECTION = ["tests/modules/discovery/test_feed.py"]
T69_ONLINE = "test_the_online_filter_keeps_the_last_five_minutes_in_any_feed"

T69: list[Case] = [
    Case(
        id="t69-01-online-filter-ignored",
        what="D-660: the service keeping the last 5 minutes for the Online feed only",
        edits=[
            (
                DISCOVERY_SERVICE,
                "if online or feed is Feed.ONLINE else None",
                "if feed is Feed.ONLINE else None",
            )
        ],
        expect=[T69_ONLINE],
    ),
    Case(
        id="t69-02-online-filter-dropped-by-the-router",
        what="D-660: the router never handing the filter to the service",
        edits=[
            (
                "app/modules/discovery/router.py",
                "        online=online,\n",
                "        online=False,\n",
            )
        ],
        expect=[T69_ONLINE],
    ),
]

# --- T-7.6: the 1-hour Thread, re-open, Extend, the minute's sweeps ----------------

T76_SELECTION = [
    "tests/modules/threads",
    "tests/modules/messages",
    "tests/workers/test_thread_clock.py",
    "tests/workers/test_minutely.py",
    "tests/test_reference_data.py",
]
THREADS_ROUTER = "app/modules/threads/router.py"
THREAD_CLOCK = "app/workers/tasks/thread_clock.py"
MINUTELY = "app/workers/minutely.py"
WORKER_MAIN = "app/workers/main.py"
THE_HOUR = "alembic/versions/20261008_7ee6438868ed_one_hour_threads.py"

T76: list[Case] = [
    Case(
        id="t76-01-buying-time-unlocked",
        what="a re-open or an Extend reading the hour without holding the Thread",
        edits=[
            (
                THREADS_SERVICE,
                "my_thread(session, thread_id, user_id, lock=True)",
                "my_thread(session, thread_id, user_id, lock=False)",
            )
        ],
        expect=["test_two_extends_at_once_each_add_their_day"],
    ),
    Case(
        id="t76-02-a-retried-tap-bought-again",
        what="the same Idempotency-Key not looked for before buying",
        edits=[
            (
                THREADS_SERVICE,
                "        if await wallet_service.entry_for(session, user_id, reason, event) is not None:\n",
                "        if False:\n",
            )
        ],
        expect=["test_the_same_key_again_is_charged_once_and_moves_nothing[extend]"],
    ),
    Case(
        id="t76-03-she-buys-time",
        what="a woman let through to re-open or Extend",
        edits=[
            (
                THREADS_SERVICE,
                "        if not rules.buys_time(gender) or not rules.has_an_hour(thread):\n",
                "        if not rules.has_an_hour(thread):\n",
            )
        ],
        expect=["test_a_woman_buys_nothing_and_is_refused"],
    ),
    Case(
        id="t76-04-time-for-what-has-no-hour",
        what="a Knot or a private message sold an hour",
        edits=[
            (
                THREADS_SERVICE,
                "        if not rules.buys_time(gender) or not rules.has_an_hour(thread):\n",
                "        if not rules.buys_time(gender):\n",
            )
        ],
        expect=["test_what_has_no_hour_cant_be_bought"],
    ),
    Case(
        id="t76-05-a-live-thread-reopened-for-money",
        what="a re-open charging for a Thread that is still live",
        edits=[
            (
                THREADS_SERVICE,
                "            if not rules.has_expired(thread, now):\n                return view_of(thread, user)\n",
                "",
            )
        ],
        expect=["test_reopening_a_live_thread_returns_it_and_charges_nothing"],
    ),
    Case(
        id="t76-06-extend-from-now",
        what="Extend counting from now, losing what was left (answer 4)",
        edits=[
            (
                THREADS_RULES,
                "    start = now if left_until is None or left_until < now else left_until\n",
                "    start = now\n",
            )
        ],
        expect=[
            "test_extend_adds_a_day_to_what_is_left",
            "test_a_second_extend_stacks_on_the_first",
        ],
    ),
    Case(
        id="t76-07-extend-from-a-past-expiry",
        what="Extend from expired counting from the old expiry, not now",
        edits=[
            (
                THREADS_RULES,
                "    start = now if left_until is None or left_until < now else left_until\n",
                "    start = now if left_until is None else left_until\n",
            )
        ],
        expect=["test_extend_from_expired_is_one_debit_and_a_day_from_now"],
    ),
    Case(
        id="t76-08-reopen-from-the-old-hour",
        what="a re-open's hour counted from the old expiry, not now (answer 1)",
        edits=[
            (
                THREADS_SERVICE,
                "            until = rules.reopened_until(now, hours)\n",
                "            until = rules.reopened_until(thread.expires_at or now, hours)\n",
            )
        ],
        expect=["test_reopen_is_two_and_an_hour_from_now"],
    ),
    Case(
        id="t76-09-the-warning-kept-after-buying",
        what="a re-open or an Extend leaving the old warning's mark",
        # Re-anchored on `until` (T-7.7): untying a Knot clears the mark too.
        edits=[
            (
                THREADS_SERVICE,
                "        thread.expires_at = until\n        thread.expiry_warned_at = None\n",
                "        thread.expires_at = until\n",
            )
        ],
        expect=[
            "test_extend_adds_a_day_to_what_is_left",
            "test_reopen_is_two_and_an_hour_from_now",
            "test_each_new_expiry_gets_its_own_warning",
        ],
    ),
    Case(
        id="t76-10-bought-and-still-expired",
        what="a re-open or an Extend leaving the status expired",
        # Re-anchored on `until` (T-7.7): untying a Knot makes it active too.
        edits=[
            (
                THREADS_SERVICE,
                "        thread.status = ThreadStatus.ACTIVE\n        thread.expires_at = until\n",
                "        thread.expires_at = until\n",
            )
        ],
        expect=[
            "test_extend_from_expired_is_one_debit_and_a_day_from_now[status]",
            "test_reopen_is_two_and_an_hour_from_now[status]",
        ],
    ),
    Case(
        id="t76-11-the-key-without-its-thread",
        what="the wallet's event built from the key alone, not the Thread",
        edits=[
            (
                THREADS_RULES,
                '    return f"{kind}:{thread_id}:{key}"\n',
                '    return f"{kind}:{key}"\n',
            )
        ],
        expect=["test_one_key_for_two_threads_buys_twice"],
    ),
    Case(
        id="t76-12-the-price-compared-with-itself",
        what="re-open and Extend comparing the price with itself (P-56)",
        edits=[
            (
                THREADS_SERVICE,
                "            shown=shown_price,\n            ref=Ref(RefType.THREAD, thread.id),\n            event=event,\n",
                (
                    "            shown=await pricing_service.price_for(session, user, reason),\n"
                    "            ref=Ref(RefType.THREAD, thread.id),\n            event=event,\n"
                ),
            )
        ],
        expect=[
            "test_extend_from_expired_compares_its_ten_and_nothing_else",
            "test_a_reopen_he_wasnt_shown_the_price_of_buys_nothing",
        ],
    ),
    Case(
        id="t76-13-the-sweep-waits-on-a-held-thread",
        what="the sweep waiting on a Thread a send holds (no SKIP LOCKED)",
        edits=[
            (
                THREADS_REPOSITORY,
                "        .with_for_update(skip_locked=True)\n",
                "        .with_for_update()\n",
            )
        ],
        expect=["test_the_sweep_skips_a_thread_her_send_holds"],
    ),
    Case(
        id="t76-14-the-sweep-expires-live-threads",
        what="the sweep expiring a Thread before its hour is up",
        edits=[
            (
                THREADS_REPOSITORY,
                "    due = _due(Thread.expires_at <= now, limit=limit)\n",
                "    due = _due(Thread.expires_at.is_not(None), limit=limit)\n",
            )
        ],
        expect=["test_what_isnt_due_is_left_alone"],
    ),
    Case(
        id="t76-15-she-is-told",
        what="the expiry and the warning sent to her too (D-097)",
        edits=[
            (
                THREADS_SERVICE,
                "            if rules.sees_the_expiry(genders.get(user_id)):\n",
                "            if True:\n",
            )
        ],
        expect=[
            "test_a_thread_past_its_hour_is_expired_and_he_is_told",
            "test_ten_minutes_out_he_is_warned_once_and_she_never",
        ],
    ),
    Case(
        id="t76-16-warned-twice",
        what="a Thread warned again for the same expiry",
        edits=[
            (THREADS_REPOSITORY, "        Thread.expiry_warned_at.is_(None),\n", "")
        ],
        expect=["test_ten_minutes_out_he_is_warned_once_and_she_never"],
    ),
    Case(
        id="t76-17-the-warning-a-literal",
        what="the warning's ten minutes written in the code (answer 3)",
        edits=[
            (
                THREADS_SERVICE,
                "now + timedelta(minutes=minutes)",
                "now + timedelta(minutes=10)",
            )
        ],
        expect=["test_the_warning_reads_the_setting_never_a_number"],
    ),
    Case(
        id="t76-18-extend-a-literal",
        what="Extend's day written in the code",
        edits=[
            (
                THREADS_SERVICE,
                "            until = rules.extended_until(thread, now, hours)\n",
                "            until = rules.extended_until(thread, now, 24)\n",
            )
        ],
        expect=["test_extend_reads_the_setting_never_a_number"],
    ),
    Case(
        id="t76-19-reopen-a-literal",
        what="a re-open's hour written in the code",
        edits=[
            (
                THREADS_SERVICE,
                "            until = rules.reopened_until(now, hours)\n",
                "            until = rules.reopened_until(now, 1)\n",
            )
        ],
        expect=["test_reopen_reads_the_setting_never_a_number"],
    ),
    Case(
        id="t76-20-one-batch-a-minute",
        what="the sweep stopping after its first batch",
        edits=[(THREAD_CLOCK, "        if taken < limit:\n", "        if True:\n")],
        expect=["test_it_works_in_batches_until_none_is_left"],
    ),
    Case(
        id="t76-21-warned-before-expired",
        what="the minute warning before it expires",
        edits=[
            (
                THREAD_CLOCK,
                (
                    '    expired = await expire_threads(ctx["sessionmaker"], ctx["redis"])\n'
                    '    warned = await warn_expiring(ctx["sessionmaker"], ctx["redis"])\n'
                ),
                (
                    '    warned = await warn_expiring(ctx["sessionmaker"], ctx["redis"])\n'
                    '    expired = await expire_threads(ctx["sessionmaker"], ctx["redis"])\n'
                ),
            )
        ],
        expect=["test_a_minute_expires_first_and_then_warns"],
    ),
    Case(
        id="t76-22-paid-time-isnt-his-answer",
        what="his first message charged after he paid a re-open or an Extend (D-641)",
        edits=[(MESSAGES_RULES, "        or bought_time\n", "")],
        expect=[
            "test_after_he_paid_from_expired_answering_her_is_free",
            "test_after_an_extend_on_a_live_thread_answering_her_is_free",
            "test_after_a_reopen_where_nobody_wrote_writing_first_is_free",
        ],
    ),
    Case(
        id="t76-23-time-bought-anywhere-answers",
        what="time bought in another Thread counted as his answer here",
        edits=[
            (
                MESSAGES_REPOSITORY,
                "                LedgerEntry.ref_id == thread_id,\n",
                "",
            )
        ],
        expect=["test_time_bought_in_another_thread_answers_nothing_here"],
    ),
    Case(
        id="t76-24-a-failed-minute-stops-the-loop",
        what="one failed minute ending every minute after it",
        edits=[
            (
                MINUTELY,
                (
                    "            except Exception as error:  # noqa: BLE001 — the next minute tries again\n"
                    "                log.warning(\n"
                ),
                (
                    "            except Exception as error:  # noqa: BLE001 — the next minute tries again\n"
                    "                raise\n"
                    "                log.warning(\n"
                ),
            )
        ],
        expect=["test_a_failed_minute_is_logged_and_the_next_one_runs"],
    ),
    Case(
        id="t76-25-runs-drift",
        what="runs a minute apart end to start, drifting by each run's length",
        edits=[
            (
                MINUTELY,
                "            await self._sleep(max(0.0, self._every_s - took))\n",
                "            await self._sleep(self._every_s)\n",
            )
        ],
        expect=["test_runs_start_a_minute_apart_whatever_each_took"],
    ),
    Case(
        id="t76-26-the-worker-never-starts-the-clock",
        what="the worker starting without the Thread's clock",
        edits=[
            (
                WORKER_MAIN,
                '    ctx["minutely"] = asyncio.create_task(each_minute(ctx).run())\n',
                "",
            )
        ],
        expect=["test_the_worker_starts_the_threads_clock_and_stops_it"],
    ),
    Case(
        id="t76-27-the-hour-left-a-day",
        what="the migration leaving thread_hours at 24",
        edits=[
            (
                THE_HOUR,
                'THREAD_HOURS = ("thread_hours", 1)\n',
                'THREAD_HOURS = ("thread_hours", 24)\n',
            )
        ],
        expect=[
            "test_app_config_seeds",
            "test_the_hour_goes_back_to_a_day_and_returns",
            "test_a_man_opens_from_a_match_for_five_and_she_is_told",
        ],
    ),
    Case(
        id="t76-28-any-key-at-all",
        what="an Idempotency-Key of any shape accepted",
        edits=[
            (
                THREADS_ROUTER,
                '    str, Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_KEY_PATTERN)\n',
                '    str, Header(alias="Idempotency-Key")\n',
            )
        ],
        expect=["test_a_missing_or_malformed_key_is_a_validation_error"],
    ),
]

# --- P-740: referrals paused (D-840) --------------------------------------------

PAUSE_REFERRALS = "alembic/versions/20261009_b53383c8e9b6_pause_referrals.py"
P740_SELECTION = T86_SELECTION
PAUSE_CHECK = (
    "        user = await users_service.locked_user(session, user.id)\n"
    "        if not await _running(session):\n"
)
SLOT_KEPT = "test_while_paused_apply_is_refused_and_the_slot_is_kept"
PAUSED_FIRST = "test_paused_is_said_before_anything_else"

P740: list[Case] = [
    Case(
        id="p740-1-apply-while-paused",
        what="D-840: apply takes a code, and the number's slot, while paused",
        edits=[
            (
                REFERRALS_SERVICE,
                PAUSE_CHECK,
                (
                    "        user = await users_service.locked_user(session, user.id)\n"
                    "        if False:\n"
                ),
            )
        ],
        expect=[SLOT_KEPT, PAUSED_FIRST],
    ),
    Case(
        id="p740-2-zero-runs",
        what="D-840: a reward of 0 counts as running",
        edits=[
            (
                REFERRALS_RULES,
                "    return reward_velas > 0\n",
                "    return reward_velas >= 0\n",
            )
        ],
        expect=[f"{SLOT_KEPT}[zero]"],
    ),
    Case(
        id="p740-3-missing-setting-runs",
        what="D-840: a missing referral_reward_velas lets apply through",
        edits=[
            (
                REFERRALS_SERVICE,
                (
                    '        log.warning("referrals.apply_config_missing", key=rules.REWARD_KEY)\n'
                    "        return False\n"
                ),
                (
                    '        log.warning("referrals.apply_config_missing", key=rules.REWARD_KEY)\n'
                    "        return True\n"
                ),
            )
        ],
        expect=[f"{SLOT_KEPT}[no row]"],
    ),
    Case(
        id="p740-4-pause-after-the-code",
        what="D-840: the pause checked last, after the code is looked up",
        edits=[
            (
                REFERRALS_SERVICE,
                PAUSE_CHECK,
                (
                    "        user = await users_service.locked_user(session, user.id)\n"
                    "        if False:\n"
                ),
            ),
            (
                REFERRALS_SERVICE,
                "        await repository.add(session, referee_id=user.id, referrer_id=owner.id)\n",
                (
                    "        if not await _running(session):\n"
                    "            raise AppError(\n"
                    '                "NOT_ALLOWED",\n'
                    '                "Referral codes are paused for now.",\n'
                    "                status=422,\n"
                    '                details={"why": "referrals_paused"},\n'
                    "            )\n"
                    "        await repository.add(session, referee_id=user.id, referrer_id=owner.id)\n"
                ),
            ),
        ],
        expect=[PAUSED_FIRST],
    ),
    Case(
        id="p740-5-migration-leaves-it-running",
        what="D-840: the migration leaves referral_reward_velas at 5",
        edits=[
            (PAUSE_REFERRALS, "PAUSED, RUNNING = 0, 5\n", "PAUSED, RUNNING = 5, 5\n")
        ],
        expect=["test_app_config_seeds"],
    ),
]

# --- T-8.4: the private album ----------------------------------------------------------

ALBUM_SERVICE = "app/modules/album/service.py"
ALBUM_REPO = "app/modules/album/repository.py"
T84_SELECTION = [
    "tests/modules/album",
    "tests/core/test_images_watermark.py",
    "tests/workers/test_watermark_album.py",
    "tests/modules/account/test_erasure.py",
    "tests/modules/users/test_dob_gender.py",
    "tests/modules/discovery/test_public_profile.py",
]
FROM_SCORED = "test_granted_he_sees_his_own_copies_made_from_the_scored_bytes"
NOT_YET = "test_thirty_days_after_she_says_no_he_may_ask_again_not_before"

T84: list[Case] = [
    Case(
        id="t84-01-the-price-compared-with-itself",
        what="P-56: the request's shown price replaced by the row's, so nothing is refused",
        edits=[
            (
                ALBUM_SERVICE,
                "        shown=body.shown_price,\n",
                (
                    "        shown=await pricing_service.price_for(\n"
                    "            session, user, LedgerReason.ALBUM_REQUEST\n"
                    "        ),\n"
                ),
            )
        ],
        expect=[
            "test_a_price_he_wasnt_shown_is_refused_with_nothing_written",
            "test_the_row_is_the_price_and_a_changed_row_is_refused",
            "test_a_woman_shown_a_price_is_refused",
        ],
    ),
    Case(
        id="t84-02-the-requester-unlocked",
        what="two requests at once, each finding none, the second breaking the index",
        edits=[
            (
                ALBUM_SERVICE,
                "    await repository.lock_requester(session, user.id)\n",
                "",
            )
        ],
        expect=["test_two_requests_at_once_are_one_request"],
    ),
    Case(
        id="t84-03-rendered-from-the-upload",
        what="D-700's hole: the copy rendered from the upload a second PUT can replace",
        edits=[
            (
                ALBUM_SERVICE,
                "            photo.scored_key,\n",
                "            photo.raw_key,\n",
            )
        ],
        expect=[FROM_SCORED],
    ),
    Case(
        id="t84-04-a-copy-kept-after-the-revoke",
        what="a copy written as she revokes recorded anyway",
        edits=[
            (
                ALBUM_SERVICE,
                "            and locked.status is AlbumRequestStatus.GRANTED\n",
                "",
            )
        ],
        expect=["test_a_copy_rendered_as_she_revokes_is_deleted_never_kept"],
    ),
    Case(
        id="t84-05-erasure-leaves-album-copies",
        what="D-503's erasure without the album copies in its file list",
        edits=[(ERASURE96, '    (AlbumCopy, "file_key", "private"),\n', "")],
        expect=[
            "test_every_storage_key_on_an_erased_table_is_in_the_file_list",
            "test_an_account_deleted_29_days_ago_is_erased_and_kept_exactly_as_d051_says",
        ],
    ),
    Case(
        id="t84-06-underage-leaves-album-copies",
        what="D-078's deletion without the album copies in its file list",
        edits=[
            (
                "app/modules/users/repository.py",
                '    FileColumn(AlbumCopy, "file_key", "private"),\n',
                "",
            )
        ],
        expect=["test_every_storage_key_on_a_deleted_table_is_in_the_file_list"],
    ),
    Case(
        id="t84-07-another-viewers-copies",
        what="the album's copies read without the viewer's request: everyone's shown",
        edits=[
            (
                ALBUM_REPO,
                "        .where(AlbumCopy.request_id == request_id, *_albumable(owner_id))\n",
                "        .where(*_albumable(owner_id))\n",
            )
        ],
        expect=[FROM_SCORED],
    ),
    Case(
        id="t84-08-a-decline-refunds",
        what="D-230 undone: a decline credits his Vela back",
        edits=[
            (
                ALBUM_SERVICE,
                "            row.decided_at = clock.now()\n            granted_now = grant\n",
                (
                    "            row.decided_at = clock.now()\n            granted_now = grant\n"
                    "            if not grant:\n"
                    "                from app.modules.wallet import service as wallet\n"
                    "\n"
                    "                await wallet.credit(\n"
                    "                    session,\n"
                    "                    row.requester_id,\n"
                    "                    row.credits_charged,\n"
                    "                    LedgerReason.REFUND_ALBUM_DECLINED,\n"
                    "                    ref=Ref(RefType.ALBUM_REQUEST, row.id),\n"
                    "                )\n"
                ),
            )
        ],
        expect=["test_a_decline_returns_nothing"],
    ),
    Case(
        id="t84-09-no-cooldown",
        what="D-731 gone: he asks again the moment she says no",
        edits=[
            (
                ALBUM_SERVICE,
                "    if not rules.may_ask_again(closed_at, now, days):\n",
                "    if False:\n",
            )
        ],
        expect=[
            f"{NOT_YET}[declined]",
            f"{NOT_YET}[revoked]",
            "test_the_days_are_read_fresh_from_app_config",
        ],
    ),
    Case(
        id="t84-10-the-cooldown-a-day-short",
        what="D-731's thirty days counted as twenty-nine",
        edits=[
            (
                "app/modules/album/rules.py",
                "now >= closed_at + timedelta(days=days)\n",
                "now >= closed_at + timedelta(days=days - 1)\n",
            )
        ],
        expect=[f"{NOT_YET}[declined]", f"{NOT_YET}[revoked]"],
    ),
    Case(
        id="t84-11-charged-for-an-empty-album",
        what="D-732: a man charged to see an album with nothing in it",
        edits=[
            (
                ALBUM_SERVICE,
                "    if await repository.albumable_count(session, owner_id) == 0:\n",
                "    if False:\n",
            )
        ],
        expect=["test_an_empty_album_is_refused_before_anything_is_charged"],
    ),
    Case(
        id="t84-12-an-unscored-photo-in-the-album",
        what="a photo approved before D-700, with no scored copy, taken into the album",
        edits=[(ALBUM_REPO, "        Photo.scored_key.is_not(None),\n", "")],
        expect=[
            "test_a_photo_approved_before_scored_copies_is_never_shown",
            "test_an_empty_album_is_refused_before_anything_is_charged",
        ],
    ),
    Case(
        id="t84-13-the-profile-counts-unscored-photos",
        what="D-732: the profile counts a photo the album never shows",
        edits=[
            (
                "app/modules/discovery/repository.py",
                "            Photo.scored_key.is_not(None),\n",
                "",
            )
        ],
        expect=["test_only_approved_public_photos_are_shown_and_nothing_private_named"],
    ),
    Case(
        id="t84-14-the-revoke-shares-the-grants-job-id",
        what="the revoke's deletion queued under the grant's id, which ARQ drops",
        edits=[
            (
                "app/modules/album/rules.py",
                '    return f"{WATERMARK_ALBUM}:{request_id}:revoked"\n',
                '    return f"{WATERMARK_ALBUM}:{request_id}"\n',
            )
        ],
        expect=["test_a_revoke_closes_it_and_queues_its_copies_deletion"],
    ),
    Case(
        id="t84-15-a-removed-photos-copies-stay",
        what="her removed private photo's copies left in every album's storage",
        edits=[
            (
                PHOTOS_SERVICE,
                (
                    "        if photo.kind is PhotoKind.PRIVATE:\n"
                    "            albums = await album_repository.granted_requests(session, user.id)\n"
                ),
                "",
            )
        ],
        expect=["test_a_photo_she_removes_leaves_every_album_file_and_row"],
    ),
    Case(
        id="t84-16-a-block-leaves-the-album-open",
        what="D-493 skipped: a granted man still sees her album after a block",
        edits=[
            (
                ALBUM_SERVICE,
                (
                    "        if owner_id == user.id or not await discovery_service.can_reach(\n"
                    "            session, user, owner_id, mutual=False\n"
                    "        ):\n"
                ),
                "        if owner_id == user.id:\n",
            )
        ],
        expect=["test_after_a_block_either_way_the_album_is_not_found"],
    ),
    Case(
        id="t84-17-the-downgrade-drops-copies",
        what="the table dropped while files hang off it, out of every deletion's sight",
        edits=[
            (
                "alembic/versions/20261009_57ab54709630_album_copies.py",
                "    if held:\n",
                "    if False:\n",
            )
        ],
        expect=["test_the_downgrade_refuses_while_a_copy_is_recorded"],
    ),
    Case(
        id="t84-18-no-watermark-on-the-copy",
        what="the copy written as the scored bytes, with nobody's name on it",
        edits=[
            (
                ALBUM_SERVICE,
                '        marked = images.watermark(data, f"@{username}")\n',
                "        marked = data\n",
            )
        ],
        expect=[FROM_SCORED, "test_the_copy_carries_his_username"],
    ),
    Case(
        id="t84-19-the-watermark-invisible",
        what="the name drawn at no opacity",
        edits=[
            (
                "app/core/images.py",
                "WATERMARK_ALPHA: Final = 51\n",
                "WATERMARK_ALPHA: Final = 0\n",
            )
        ],
        expect=[
            "test_the_name_is_on_every_part_of_the_photo_and_faint",
            "test_each_viewer_gets_a_copy_of_his_own",
            FROM_SCORED,
        ],
    ),
    Case(
        id="t84-20-a-revoke-deletes-nothing",
        what="a revoke's copies never deleted, only forgotten",
        edits=[
            (
                ALBUM_SERVICE,
                "        await storage.delete(bucket, key)\n",
                "        pass\n",
            )
        ],
        expect=["test_a_revoke_leaves_him_nothing"],
    ),
]


# --- T-7.7: the knot, tied and untied ----------------------------------------------

T77_SELECTION = [
    "tests/modules/threads/test_knot.py",
    "tests/modules/threads/test_knot_race.py",
]
T77_TWO_TAPS = "test_two_taps_at_once_make_one_knot"
T77_SECOND_TAP = "test_the_second_tap_makes_a_knot"
T77_UNTIE = "test_untying_a_knot_gives_a_fresh_hour_from_the_setting"

T77: list[Case] = [
    Case(
        id="t77-01-a-tap-unlocked",
        what="a tap or an untie reading the Thread without holding it",
        edits=[
            (
                THREADS_SERVICE,
                "my_thread(session, thread_id, viewer_id, lock=True)",
                "my_thread(session, thread_id, viewer_id, lock=False)",
            )
        ],
        expect=[T77_TWO_TAPS],
    ),
    Case(
        id="t77-02-two-taps-no-knot",
        what="the second tap never making the Knot",
        edits=[
            (
                THREADS_SERVICE,
                "        if rules.tied_by_both(thread):\n",
                "        if False:\n",
            )
        ],
        expect=[
            T77_SECOND_TAP,
            "test_an_expired_thread_ties_straight_into_a_knot",
            T77_TWO_TAPS,
        ],
    ),
    Case(
        id="t77-03-a-knot-keeps-its-expiry",
        what="a Knot left with its expiry (the database's CHECK refuses it)",
        edits=[
            (
                THREADS_SERVICE,
                "            thread.knotted_at = now\n            thread.expires_at = None\n",
                "            thread.knotted_at = now\n",
            )
        ],
        expect=[T77_SECOND_TAP, "test_a_knot_has_no_hour_for_anyone_to_move"],
    ),
    Case(
        id="t77-04-a-knot-keeps-its-warning",
        what="a Knot left marked as warned",
        edits=[
            (
                THREADS_SERVICE,
                "            thread.expires_at = None\n            thread.expiry_warned_at = None\n",
                "            thread.expires_at = None\n",
            )
        ],
        expect=[T77_SECOND_TAP],
    ),
    Case(
        id="t77-05-a-tap-again-asks-again",
        what="a tap already there tapped again, and the other asked again",
        edits=[
            (
                THREADS_SERVICE,
                "        if rules.tapped(thread, user_id):\n",
                "        if False:\n",
            )
        ],
        expect=[
            "test_a_second_tap_of_ones_own_tells_nobody_again",
            "test_tap_untie_tap_asks_her_once",
            "test_tapping_a_knot_returns_it_and_tells_nobody",
        ],
    ),
    Case(
        id="t77-06-tied-to-a-deleted-account",
        what="a tap on a Thread with a deleted account written",
        edits=[
            (
                THREADS_SERVICE,
                "        if await repository.status_of(session, other_id) is UserStatus.DELETED:\n",
                "        if False:\n",
            )
        ],
        expect=["test_tying_to_a_deleted_account_is_refused"],
    ),
    Case(
        id="t77-07-the-tapper-asked",
        what="knot.requested sent to the one who tapped",
        edits=[
            (
                THREADS_SERVICE,
                "events.queue(session, other_id, KNOT_REQUESTED, requested)",
                "events.queue(session, user_id, KNOT_REQUESTED, requested)",
            )
        ],
        expect=["test_one_tap_asks_the_other_and_nothing_else_moves"],
    ),
    Case(
        id="t77-08-accepted-to-one",
        what="knot.accepted sent to the last tapper alone",
        edits=[
            (
                THREADS_SERVICE,
                "            for one in (user_id, other_id):\n",
                "            for one in (user_id,):\n",
            )
        ],
        expect=[T77_SECOND_TAP, T77_TWO_TAPS],
    ),
    Case(
        id="t77-09-accepted-notifies-the-tapper",
        what="the knot_accepted notification written for the last tapper",
        edits=[
            (
                THREADS_SERVICE,
                "                other_id,\n                Kind.KNOT_ACCEPTED,\n",
                "                user_id,\n                Kind.KNOT_ACCEPTED,\n",
            )
        ],
        expect=[T77_SECOND_TAP],
    ),
    Case(
        id="t77-10-untie-what-isnt-a-knot",
        what="untying a Thread that isn't a Knot",
        edits=[
            (
                THREADS_SERVICE,
                "        if thread.status is not ThreadStatus.KNOTTED:\n            return view_of(thread, user)\n",
                "",
            )
        ],
        expect=[
            "test_untying_what_isnt_a_knot_changes_nothing",
            "test_tap_untie_tap_asks_her_once",
        ],
    ),
    Case(
        id="t77-11-untied-for-a-literal-hour",
        what="an untied Knot given 1 hour, not thread_hours",
        edits=[
            (
                THREADS_SERVICE,
                "rules.untied_until(thread.origin, clock.now(), hours)",
                "rules.untied_until(thread.origin, clock.now(), 1)",
            )
        ],
        expect=[T77_UNTIE],
    ),
    Case(
        id="t77-12-an-untied-private-message-expires",
        what="an untied private message given an hour",
        edits=[
            (
                THREADS_RULES,
                '    match (D-560), never for a private message (D-550)."""\n    return expires_at(origin, now, hours)\n',
                '    match (D-560), never for a private message (D-550)."""\n    return now + timedelta(hours=hours)\n',
            )
        ],
        expect=["test_untying_a_private_message_leaves_it_never_expiring"],
    ),
    Case(
        id="t77-13-untied-taps-kept",
        what="an untied Knot keeping a tap",
        edits=[(THREADS_SERVICE, "        thread.low_knot_at = None\n", "")],
        expect=[T77_UNTIE],
    ),
    Case(
        id="t77-14-untied-warning-kept",
        what="an untied Knot keeping an old warning mark",
        edits=[
            (
                THREADS_SERVICE,
                "        thread.high_knot_at = None\n        thread.expiry_warned_at = None\n",
                "        thread.high_knot_at = None\n",
            )
        ],
        expect=[T77_UNTIE],
    ),
    Case(
        id="t77-15-the-untier-told",
        what="knot.untied sent to the one who untied",
        edits=[
            (
                THREADS_SERVICE,
                "            _other_in(thread, user_id),\n            KNOT_UNTIED,\n",
                "            user_id,\n            KNOT_UNTIED,\n",
            )
        ],
        expect=[T77_UNTIE],
    ),
    Case(
        id="t77-16-taps-unlimited",
        what="tapping with no rate limit",
        edits=[
            (
                THREADS_ROUTER,
                '@router.post("/threads/{thread_id}/knot", dependencies=[knot_rate_limit])',
                '@router.post("/threads/{thread_id}/knot")',
            )
        ],
        expect=["test_tying_and_untying_are_rate_limited_together"],
    ),
]

# --- T-8.8: the profile says whether kudos can be given (D-790, P-580) ----------------

T88_SELECTION = [
    "tests/modules/kudos",
    "tests/modules/discovery/test_public_profile.py",
]

T88: list[Case] = [
    Case(
        id="t88-01-given-forgotten",
        what="P-580: the prompt coming back after kudos was given",
        edits=[
            (
                KUDOS_SERVICE,
                "    if await repository.given(session, viewer_id, other_id):\n",
                "    if False:\n",
            )
        ],
        expect=[
            "test_given_once_given_whatever_its_kind_and_only_for_the_giver",
            "test_what_the_profile_says_is_what_post_kudos_does",
        ],
    ),
    Case(
        id="t88-02-given-the-other-way",
        what="kudos she gave him read as his given to her",
        edits=[
            (
                KUDOS_REPOSITORY,
                "        select(exists().where(Kudos.from_id == from_id, Kudos.to_id == to_id))\n",
                "        select(exists().where(Kudos.from_id == to_id, Kudos.to_id == from_id))\n",
            )
        ],
        expect=["test_given_once_given_whatever_its_kind_and_only_for_the_giver"],
    ),
    Case(
        id="t88-03-too-early-never-said",
        what="P-580: the prompt shown before D-680 allows it, each tap NOT_ALLOWED",
        edits=[
            (
                KUDOS_SERVICE,
                (
                    "    if not await _talked(session, thread, viewer_id, other_id, config=config):\n"
                    '        return "too_early"\n'
                ),
                "",
            )
        ],
        expect=[
            "test_state.py::test_five_messages_are_too_early_and_six_enough",
            "test_state.py::test_a_one_sided_thread_is_too_early_for_either",
            "test_what_the_profile_says_is_what_post_kudos_does",
            "test_the_thread_with_me_and_the_match",
        ],
    ),
]

T810_SELECTION = [
    "tests/modules/discovery/test_public_profile.py",
    # D-880: one Thread's screen reads the same rule.
    "tests/modules/threads/test_view.py",
]
DISCOVERY_SERVICE = "app/modules/discovery/service.py"
CAN_GIFT = "test_can_gift_is_the_sends_own_answer"
THREAD_GIFT = "test_can_gift_is_the_profiles_and_the_sends_own_answer"

# T-8.10 (D-780): `can_gift` says where `POST /gifts/send` takes a gift.
T810: list[Case] = [
    Case(
        id="t810-1-can-gift-past-mutual-seeking",
        what="the gift button where a link reaches her but a private message can't",
        edits=[
            (
                DISCOVERY_SERVICE,
                "        and await repository.is_visible(session, viewer, other_id, mutual=True)\n",
                "        and await repository.is_visible(session, viewer, other_id, mutual=False)\n",
            )
        ],
        expect=[
            f"{CAN_GIFT}[male-female-women-False]",
            f"{THREAD_GIFT}[male-female-women-False]",
        ],
    ),
    Case(
        id="t810-2-can-gift-to-a-man",
        what="the gift button on a man's profile",
        edits=[
            (
                DISCOVERY_SERVICE,
                "        and other_gender is Gender.FEMALE\n",
                "",
            )
        ],
        expect=[
            f"{CAN_GIFT}[male-male-men-False]",
            f"{THREAD_GIFT}[male-male-men-False]",
        ],
    ),
    Case(
        id="t810-3-can-gift-from-a-woman",
        what="the gift button for a woman viewing a woman",
        edits=[
            (
                DISCOVERY_SERVICE,
                "        user.gender is Gender.MALE\n        and other_gender",
                "        True\n        and other_gender",
            )
        ],
        expect=[
            f"{CAN_GIFT}[female-female-women-False]",
            f"{THREAD_GIFT}[female-female-women-False]",
        ],
    ),
]


# --- T-7.11: the conversation's Thread, with what the next message costs ----------

T711_SELECTION = [
    "tests/modules/threads/test_view.py",
    "tests/modules/threads/test_list.py",
    "tests/modules/messages/test_send.py",
]
T711_ANSWER = "test_answering_her_is_shown_as_the_re_open_once"
T711_OPEN = "test_writing_first_where_she_opened_is_shown_as_the_open"

T711: list[Case] = [
    Case(
        id="t711-01-the-answer-not-shown",
        what="send_price leaving out what his answer costs",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if answer is not None:\n        price += await pricing_service.price_for(session, user, answer)\n",
                "",
            )
        ],
        expect=[T711_ANSWER, T711_OPEN],
    ),
    Case(
        id="t711-02-a-private-message-not-shown",
        what="send_price leaving out a private message's price",
        edits=[
            (
                MESSAGES_SERVICE,
                "    if rules.private_message_priced(thread):\n        price += await",
                "    if False:\n        price += await",
            )
        ],
        expect=["test_every_private_message_of_his_is_shown_at_two"],
    ),
    Case(
        id="t711-03-the-send-forgets-the-answer",
        what="the send charging no answer while the Thread still shows its price",
        edits=[
            (
                MESSAGES_SERVICE,
                "    answer = await _answer(session, thread, user.id, other_id)\n",
                "    answer = None\n",
            )
        ],
        expect=[
            T711_ANSWER,
            T711_OPEN,
            "test_answering_her_costs_him_the_re_open_once",
        ],
    ),
    Case(
        id="t711-04-my-own-card",
        what="the header's card read for the viewer instead of the other person",
        edits=[
            (
                THREADS_SERVICE,
                "card = await repository.card_of(session, other_id)",
                "card = await repository.card_of(session, user.id)",
            )
        ],
        expect=["test_the_thread_comes_with_the_other_person_and_counts_no_view"],
    ),
    Case(
        id="t711-05-a-deleted-account-named",
        what="a deleted account's name, photo and presence shown",
        edits=[
            (
                THREADS_SERVICE,
                "    deleted = row.other_status is UserStatus.DELETED\n",
                "    deleted = False\n",
            )
        ],
        expect=[
            "test_view.py::test_a_deleted_account_is_named_as_one_and_nothing_more",
            "test_list.py::test_a_deleted_account_is_named_as_one_and_nothing_more",
        ],
    ),
    Case(
        id="t711-06-her-expiry-shown",
        what="her Thread's screen given the expiry",
        edits=[
            (
                THREADS_SERVICE,
                "expires_at=thread.expires_at if rules.sees_the_expiry(viewer.gender) else None,",
                "expires_at=thread.expires_at,",
            )
        ],
        expect=["test_the_thread_comes_with_the_other_person_and_counts_no_view"],
    ),
]

# --- T-9.4: notifications, web push, the outbox ------------------------------------

T94_SELECTION = [
    "tests/modules/notifications",
    "tests/workers/test_send_push.py",
    "tests/modules/account/test_erasure.py",
    "tests/modules/users/test_dob_gender.py",
]
N_RULES = "app/modules/notifications/rules.py"
N_SERVICE = "app/modules/notifications/service.py"
N_REPOSITORY = "app/modules/notifications/repository.py"
N_SENDER = "app/modules/notifications/sender.py"
T94_NOT_ACTIVE = "test_an_account_that_is_not_active_is_told_nothing"
T94_BLOCKED = "test_nothing_about_someone_blocked_either_way_is_listed"

T94: list[Case] = [
    Case(
        id="t94-01-paused-told",
        what="a paused account told, against T-9.6",
        edits=[
            (
                N_RULES,
                "TOLD: Final = frozenset({UserStatus.ACTIVE})",
                "TOLD: Final = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})",
            )
        ],
        expect=[f"{T94_NOT_ACTIVE}[paused]"],
    ),
    Case(
        id="t94-02-her-hour-told",
        what="an hour running out or a balance told to anyone (P-460, D-554)",
        edits=[
            (
                N_RULES,
                "    return kind not in MEN_ONLY or gender is Gender.MALE\n",
                "    return True\n",
            )
        ],
        expect=["test_an_hour_and_a_balance_never_reach_anyone_but_a_man"],
    ),
    Case(
        id="t94-03-a-like-names-who",
        what="a like to a man naming who liked him (D-542)",
        edits=[
            (
                N_SERVICE,
                "    if kind is Kind.LIKE and not likes_rules.sees_everyone(gender):\n",
                "    if False:\n",
            )
        ],
        expect=[
            "test_a_like_to_a_man_never_says_who",
            "test_a_super_like_to_him_never_names_her",
        ],
    ),
    Case(
        id="t94-04-a-push-past-its-setting",
        what="a push written with its setting off",
        edits=[(N_SERVICE, "    if wanted and subscribed:\n", "    if subscribed:\n")],
        expect=[
            "test_a_setting_turned_off_keeps_the_push_and_not_the_row",
            "test_a_gifts_push_follows_the_gift_setting",
        ],
    ),
    Case(
        id="t94-05-push-only-kinds-listed",
        what="a message or a like given a row in the list (D-852)",
        edits=[(N_SERVICE, "    if kind not in rules.PUSH_ONLY:\n", "    if True:\n")],
        expect=[
            "test_messages_and_likes_are_pushes_only",
            "test_a_like_is_a_push_to_her_naming_him",
        ],
    ),
    Case(
        id="t94-06-no-wake",
        what="a push written and the worker never woken (D-850)",
        edits=[(N_SERVICE, "        events.wake_push(session, user_id)\n", "")],
        expect=[
            "test_an_active_account_with_a_subscription_gets_both",
            "test_a_match_wakes_the_worker_once_after_the_commit",
        ],
    ),
    Case(
        id="t94-07-a-wake-per-push",
        what="every queued wake published, a PUBLISH each against D-091",
        edits=[
            (
                "app/core/events.py",
                "    events = [each for each in events if each.type != PUSH_WAKE or each is first_wake]\n",
                "",
            )
        ],
        expect=["test_one_wake_is_published_however_many_were_queued"],
    ),
    Case(
        id="t94-08-any-host",
        what="a subscription naming any host, so the worker posts anywhere (D-855)",
        edits=[
            (
                N_RULES,
                "    return host in PUSH_HOSTS or host.endswith(PUSH_HOST_SUFFIXES)\n",
                "    return True\n",
            )
        ],
        expect=["test_an_endpoint_off_the_push_services_is_refused"],
    ),
    Case(
        id="t94-09-a-suffix-without-its-dot",
        what="a push host's suffix matched without the dot before it",
        edits=[
            (
                N_RULES,
                'PUSH_HOST_SUFFIXES: Final = (".push.apple.com", ".notify.windows.com")',
                'PUSH_HOST_SUFFIXES: Final = ("push.apple.com", "notify.windows.com")',
            )
        ],
        expect=["test_an_endpoint_off_the_push_services_is_refused[https://evilpush"],
    ),
    Case(
        id="t94-10-keys-unchecked",
        what="a subscription's keys taken unread",
        edits=[
            (
                "app/modules/notifications/schemas.py",
                "        if p256dh is None or len(p256dh) != P256DH_BYTES or p256dh[0] != 0x04:\n",
                "        if False:\n",
            )
        ],
        expect=["test_keys_that_are_not_keys_are_refused"],
    ),
    Case(
        id="t94-11-unsubscribe-anyones",
        what="an unsubscribe deleting another account's subscription",
        edits=[
            (
                N_REPOSITORY,
                (
                    "        delete(PushSubscription).where(\n"
                    "            PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint\n"
                ),
                (
                    "        delete(PushSubscription).where(\n"
                    "            PushSubscription.endpoint == endpoint\n"
                ),
            )
        ],
        expect=["test_unsubscribing_removes_only_your_own"],
    ),
    Case(
        id="t94-12-everyones-list",
        what="the list showing everyone's notifications",
        edits=[(N_REPOSITORY, "            Notification.user_id == user_id,\n", "")],
        expect=["test_the_list_is_your_own_newest_first_in_pages"],
    ),
    Case(
        id="t94-13-blocks-listed",
        what="the list showing rows about someone blocked (P-760)",
        edits=[
            (
                N_REPOSITORY,
                "            ~blocked_either_way(Notification.user_id, about),\n",
                "",
            )
        ],
        expect=[T94_BLOCKED],
    ),
    Case(
        id="t94-14-a-threads-block-listed",
        what="a row about a Thread's blocked other person listed (P-760)",
        edits=[(N_REPOSITORY, "        other_in_thread,\n", "        None,\n")],
        expect=[T94_BLOCKED],
    ),
    Case(
        id="t94-15-everyones-read",
        what="reading marks other people's notifications read",
        edits=[
            (
                N_REPOSITORY,
                "        .where(Notification.user_id == user_id, Notification.read_at.is_(None))\n",
                "        .where(Notification.read_at.is_(None))\n",
            )
        ],
        expect=["test_reading_marks_every_unread_one_of_yours"],
    ),
    Case(
        id="t94-16-sent-past-its-setting",
        what="a push sent after its setting was turned off",
        edits=[
            (N_SENDER, " or not wanted or not subscriptions", " or not subscriptions")
        ],
        expect=["test_a_setting_turned_off_since_sends_nothing"],
    ),
    Case(
        id="t94-17-sent-while-paused",
        what="a push sent to an account paused since (T-9.6)",
        edits=[
            (
                N_SENDER,
                "    if not rules.told(status) or not wanted",
                "    if not wanted",
            )
        ],
        expect=["test_an_account_paused_since_is_sent_nothing"],
    ),
    Case(
        id="t94-18-sent-across-a-block",
        what="a push sent about someone blocked since (P-760)",
        edits=[
            (N_SENDER, " or not subscriptions or blocked:", " or not subscriptions:")
        ],
        expect=["test_a_block_since_sends_nothing"],
    ),
    Case(
        id="t94-19-a-name-despite-generic-text",
        what="a name sent with generic_text on",
        edits=[(N_SENDER, "None if generic_text else name", "name")],
        expect=["test_generic_text_sends_no_name"],
    ),
    Case(
        id="t94-20-pushed-while-connected",
        what="a message pushed while a socket of hers is open (D-854)",
        edits=[
            (
                N_SENDER,
                "    if kind in rules.ONLY_IF_NOT_CONNECTED and await connected(redis, user_id):\n",
                "    if False:\n",
            )
        ],
        expect=["test_a_message_waits_on_presence_by_numsub"],
    ),
    Case(
        id="t94-21-sent-an-hour-late",
        what="a push sent an hour or more after it was written",
        edits=[(N_SENDER, "    if age_s >= rules.PUSH_TTL_S:\n", "    if False:\n")],
        expect=["test_a_push_an_hour_old_is_dropped_not_sent"],
    ),
    Case(
        id="t94-22-a-gone-subscription-kept",
        what="a subscription the push service called gone, kept",
        edits=[
            (
                N_SENDER,
                "                await repository.drop_gone(session, user_id, endpoint)\n",
                "                pass\n",
            )
        ],
        expect=["test_a_gone_subscription_is_deleted_and_the_others_still_sent"],
    ),
    Case(
        id="t94-23-retried-for-ever",
        what="a failing push tried again with no end",
        edits=[
            (
                N_SENDER,
                "        if retry and attempts < rules.PUSH_ATTEMPTS:\n",
                "        if retry:\n",
            )
        ],
        expect=["test_a_failure_is_tried_three_times_then_dropped"],
    ),
    Case(
        id="t94-24-a-claim-ignored",
        what="a push another sender holds, claimed again before it goes stale",
        edits=[
            (
                N_REPOSITORY,
                "                PushOutbox.claimed_at < stale_before,\n",
                "                True,\n",
            )
        ],
        expect=[
            "test_a_push_mid_send_is_never_taken_by_another_sender",
            "test_a_claim_gone_stale_is_taken_again",
        ],
    ),
    Case(
        id="t94-25-a-lock-waited-on",
        what="a sender waiting on a row another is claiming",
        edits=[
            (
                N_REPOSITORY,
                "        .with_for_update(skip_locked=True)\n",
                "        .with_for_update()\n",
            )
        ],
        expect=["test_a_row_being_claimed_is_skipped_not_waited_on"],
    ),
    Case(
        id="t94-26-an-expiry-pushed",
        what="an hour's expiry carried in a push (P-460)",
        edits=[
            (
                N_RULES,
                '    Kind.THREAD_EXPIRING: ("thread_id",),\n',
                '    Kind.THREAD_EXPIRING: ("thread_id", "expires_at"),\n',
            )
        ],
        expect=[
            "test_nothing_about_an_hour_ever_leaves_in_a_push",
            "test_no_kind_may_carry_an_expiry_a_price_or_a_text[thread_expiring]",
        ],
    ),
    Case(
        id="t94-27-album-request-untold",
        what="a new album request telling her nothing (P-631)",
        edits=[
            (
                "app/modules/album/service.py",
                "    await notifications_service.notify(session, owner_id, Kind.ALBUM_REQUEST, told)\n",
                "",
            )
        ],
        expect=["test_a_new_album_request_tells_her"],
    ),
    Case(
        id="t94-28-an-opening-pushed-twice",
        what="a Thread opened with a message pushing twice",
        edits=[
            (
                "app/modules/threads/service.py",
                "await messages_service.announce(session, row, other_id, notify=False)",
                "await messages_service.announce(session, row, other_id, notify=True)",
            )
        ],
        expect=["test_an_opening_with_a_first_message_is_one_push"],
    ),
    Case(
        id="t94-29-low-balance-every-debit",
        what="low_balance told at every debit under the line, not once (D-853)",
        edits=[(N_SERVICE, "    if before >= low > after:\n", "    if low > after:\n")],
        expect=["test_a_balance_falling_under_ten_tells_him_once"],
    ),
    Case(
        id="t94-30-a-pair-unmatched",
        what="a VAPID public key that isn't the private key's, taken (D-856)",
        edits=[
            (
                "app/core/config.py",
                "        if vapid_public_key(private) != self.VAPID_PUBLIC_KEY:\n",
                "        if False:\n",
            )
        ],
        expect=["test_a_wrong_key_or_subject_is_refused_without_its_value"],
    ),
    Case(
        id="t94-31-rfc-8291-info",
        what="the key info off RFC 8291's by its zero byte",
        edits=[
            (
                "app/core/providers/push.py",
                '_KEY_INFO: Final = b"WebPush: info\\x00"',
                '_KEY_INFO: Final = b"WebPush: info"',
            )
        ],
        expect=["test_the_body_is_rfc_8291s_example_byte_for_byte"],
    ),
    Case(
        id="t94-32-gone-read-as-failure",
        what="404 and 410 read as a failure to try again",
        edits=[
            (
                "app/core/providers/push.py",
                "_GONE: Final = frozenset({404, 410})",
                "_GONE: Final = frozenset()",
            )
        ],
        expect=["test_the_push_services_answer_decides"],
    ),
    Case(
        id="t94-33-the-wrong-ear",
        what="the worker's push listener on another channel",
        edits=[
            (
                "app/workers/main.py",
                "        channel=wake_channel(SEND_PUSH),\n",
                "        channel=wake_channel(VERIFY_SELFIE),\n",
            )
        ],
        expect=["test_a_wake_sends_the_waiting_push_at_once"],
    ),
    Case(
        id="t94-34-the-minute-sends-nothing",
        what="the worker's minute leaving what a lost wake left",
        edits=[
            (
                "app/workers/main.py",
                "        pushed = await send_push.run(ctx)\n",
                "        pushed: dict[str, int] = {}\n",
            )
        ],
        expect=["test_the_minute_sends_what_a_lost_wake_left"],
    ),
    Case(
        id="t94-35-erasure-keeps-the-outbox",
        what="an erased account's waiting pushes kept (D-503)",
        edits=[
            (
                "app/modules/account/erasure.py",
                '    Erased(PushOutbox, ("user_id",)),\n',
                "",
            )
        ],
        expect=[
            "test_an_account_deleted_29_days_ago_is_erased_and_kept_exactly_as_d051_says"
        ],
    ),
    Case(
        id="t94-36-under-18-keeps-the-outbox",
        what="an under-18 refusal leaving the outbox's rows (D-078)",
        edits=[
            (
                "app/modules/users/repository.py",
                '    Attached(PushOutbox, ("user_id",)),\n',
                "",
            )
        ],
        expect=["test_under_eighteen_deletes_every_row_in_every_table_the_app_may"],
    ),
    Case(
        id="t94-37-a-key-while-push-is-off",
        what="the VAPID key served with push off, so browsers subscribe to nothing",
        edits=[
            (
                N_SERVICE,
                'if settings.PUSH_PROVIDER != "webpush" or not settings.VAPID_PUBLIC_KEY:',
                "if not settings.VAPID_PUBLIC_KEY:",
            )
        ],
        expect=["test_push_off_serves_no_key_even_with_one_set"],
    ),
]


# --- T-9.1: reports and blocks -------------------------------------------------------

DISCOVERY_REPO91 = "app/modules/discovery/repository.py"
SAFETY_SERVICE = "app/modules/safety/service.py"
SAFETY_REPO = "app/modules/safety/repository.py"
SAFETY_ROUTER = "app/modules/safety/router.py"
THREADS_REPO91 = "app/modules/threads/repository.py"
THREADS_SERVICE91 = "app/modules/threads/service.py"
BLOCKS_HISTORY = "alembic/versions/20261009_4889c586aa2c_blocks_keep_history.py"
ACCOUNT_REPO91 = "app/modules/account/repository.py"
T91_SELECTION = [
    "tests/modules/safety",
    "tests/workers/test_thread_clock.py",
    "tests/modules/account/test_export.py",
    "tests/modules/album",
]

T91: list[Case] = [
    Case(
        id="t91-01-a-lifted-block-still-blocks",
        what="D-860: a lifted block read as standing, so unblocking lifts nothing",
        edits=[
            (
                DISCOVERY_REPO91,
                "        .where(Block.unblocked_at.is_(None), or_(by(a, b), by(b, a)))\n",
                "        .where(or_(by(a, b), by(b, a)))\n",
            )
        ],
        expect=[
            "test_unblocking_lifts_every_one_of_them",
            "test_a_lifted_block_warns_and_tells_as_before",
            "test_nobody_is_told_and_lifting_her_one_block_lets_him_through",
        ],
    ),
    Case(
        id="t91-02-by-account-not-number",
        what="P-400's hole: a block matched by account alone, so a new one on the number walks in",
        edits=[
            (
                DISCOVERY_REPO91,
                "            Block.blocker_id == blocker, blocked.phone_hash == _number_of(other)\n",
                "            Block.blocker_id == blocker, Block.blocked_id == other\n",
            )
        ],
        expect=[
            "test_a_new_account_on_a_blocked_number_is_blocked_both_ways_everywhere"
        ],
    ),
    Case(
        id="t91-03-a-block-revokes-nothing",
        what="a block leaving her album granted to him",
        edits=[
            (
                SAFETY_SERVICE,
                "    return await album_service.revoke_between(session, user.id, other_id)\n",
                "    return []\n",
            )
        ],
        expect=[
            "test_a_block_revokes_the_grant_and_its_copies_go",
            "test_grants_both_ways_are_revoked_by_one_block",
            "test_a_report_with_also_block_revokes_too",
        ],
    ),
    Case(
        id="t91-04-only-grants-locked",
        what="the block locking granted requests only, so a grant being decided is missed",
        edits=[
            (
                ALBUM_REPO,
                "        .order_by(AlbumRequest.id)\n        .with_for_update()\n",
                (
                    "        .where(AlbumRequest.status == AlbumRequestStatus.GRANTED)\n"
                    "        .order_by(AlbumRequest.id)\n        .with_for_update()\n"
                ),
            )
        ],
        expect=["test_a_block_waiting_on_a_grant_revokes_it"],
    ),
    Case(
        id="t91-05-a-grant-across-a-block",
        what="decide never asking for a block, so she grants across one",
        edits=[
            (
                ALBUM_SERVICE,
                (
                    "        if await repository.blocked_between(session, row.owner_id, row.requester_id):\n"
                    "            raise rules.not_found()\n"
                ),
                "",
            )
        ],
        expect=[
            "test_she_cant_grant_across_a_block_and_a_pending_one_waits_it_out",
            "test_a_grant_waiting_on_a_block_sees_it",
        ],
    ),
    Case(
        id="t91-06-warned-across-a-block",
        what="the clock warning him of a Thread across a block",
        edits=[
            (
                THREADS_REPO91,
                "        ~blocked_either_way(Thread.user_low, Thread.user_high),\n",
                "",
            )
        ],
        expect=["test_across_a_block_nobody_is_warned"],
    ),
    Case(
        id="t91-07-expiry-told-across-a-block",
        what="the clock telling him a Thread across a block expired",
        edits=[
            (
                THREADS_SERVICE91,
                "        told = [row for row in rows if not row.blocked]\n",
                "        told = list(rows)\n",
            )
        ],
        expect=["test_across_a_block_it_expires_and_nobody_is_told"],
    ),
    Case(
        id="t91-08-evidence-through-the-clearing",
        what="D-006's hole: the report's evidence read through the reporter's clearing",
        edits=[
            (
                SAFETY_REPO,
                "        .where(Message.thread_id == thread_id)\n",
                (
                    "        .where(\n"
                    "            Message.thread_id == thread_id,\n"
                    "            ~exists().where(\n"
                    "                ThreadClear.thread_id == thread_id,\n"
                    "                ThreadClear.cleared_at >= Message.created_at,\n"
                    "            ),\n"
                    "        )\n"
                ),
            ),
            (
                SAFETY_REPO,
                "from app.modules.threads.models import Thread\n",
                "from app.modules.threads.models import Thread, ThreadClear\n",
            ),
        ],
        expect=["test_the_evidence_is_every_message_whatever_the_reporter_cleared"],
    ),
    Case(
        id="t91-09-also-block-ignored",
        what="a report's also_block dropped",
        edits=[
            (SAFETY_SERVICE, "        if body.also_block:\n", "        if False:\n")
        ],
        expect=[
            "test_also_block_blocks_in_the_same_request",
            "test_a_report_with_also_block_revokes_too",
        ],
    ),
    Case(
        id="t91-10-any-thread-attached",
        what="a report naming a Thread that isn't the pair's",
        edits=[
            (
                SAFETY_SERVICE,
                "            if pair != body.thread_id:\n                raise _not_found()\n",
                "",
            )
        ],
        expect=["test_a_thread_that_isnt_theirs_is_not_found_and_blocks_nothing"],
    ),
    Case(
        id="t91-11-reports-unlimited",
        what="reports with no daily limit",
        edits=[
            (
                SAFETY_ROUTER,
                '        Depends(user_rate_limit("reports", limit=REPORTS_PER_DAY, window_s=86_400))\n',
                "",
            )
        ],
        expect=["test_ten_a_day_then_rate_limited"],
    ),
    Case(
        id="t91-12-blocks-unlimited",
        what="blocks and unblocks with no limit",
        edits=[
            (
                SAFETY_ROUTER,
                '@router.post("/blocks", status_code=201, dependencies=[Depends(_blocks_limit)])\n',
                '@router.post("/blocks", status_code=201)\n',
            )
        ],
        expect=["test_blocks_and_unblocks_share_a_limit_a_minute"],
    ),
    Case(
        id="t91-13-unblock-deletes",
        what="P-16's loss: unblocking deleting the block's history",
        edits=[
            (SAFETY_REPO, "        update(Block)\n", "        delete(Block)\n"),
            (SAFETY_REPO, "        .values(unblocked_at=now)\n", ""),
            (
                SAFETY_REPO,
                "from sqlalchemy import Row, Uuid, and_, cast, exists, func, or_, select, tuple_, update\n",
                "from sqlalchemy import Row, Uuid, and_, cast, delete, exists, func, or_, select, tuple_, update\n",
            ),
        ],
        expect=["test_unblocking_keeps_the_row_and_blocking_again_is_a_new_one"],
    ),
    Case(
        id="t91-14-twice-is-an-error",
        what="a second block of the same person breaking the index",
        edits=[
            (
                SAFETY_REPO,
                (
                    "        .on_conflict_do_nothing(\n"
                    "            index_elements=[Block.blocker_id, Block.blocked_id],\n"
                    "            index_where=Block.unblocked_at.is_(None),\n"
                    "        )\n"
                ),
                "",
            )
        ],
        expect=["test_twice_is_once"],
    ),
    Case(
        id="t91-15-downgrade-deletes-history",
        what="the downgrade going back over lifted blocks",
        edits=[
            (
                BLOCKS_HISTORY,
                "    if lifted:\n",
                "    if False:\n",
            )
        ],
        expect=["test_the_downgrade_refuses_while_a_lifted_block_is_recorded"],
    ),
    Case(
        id="t91-16-the-reported-told",
        what="a report telling its subject",
        edits=[
            (
                SAFETY_SERVICE,
                "        result = schemas.ReportFiled(id=filed.id, created_at=filed.created_at)\n",
                (
                    '        events.queue(session, body.reported_id, "report.filed", {})\n'
                    "        result = schemas.ReportFiled(id=filed.id, created_at=filed.created_at)\n"
                ),
            ),
            (
                SAFETY_SERVICE,
                "from app.core import clock\n",
                "from app.core import clock, events\n",
            ),
        ],
        expect=["test_the_reported_person_is_never_told"],
    ),
    Case(
        id="t91-17-the-blocked-told",
        what="D-862's hole: a block telling the blocked person",
        edits=[
            (
                SAFETY_SERVICE,
                "        revoked = await _block_in(session, user, other_id)\n",
                (
                    "        revoked = await _block_in(session, user, other_id)\n"
                    '        events.queue(session, other_id, "block.made", {})\n'
                ),
            ),
            (
                SAFETY_SERVICE,
                "from app.core import clock\n",
                "from app.core import clock, events\n",
            ),
        ],
        expect=["test_nothing_is_queued_or_published_for_the_blocked_person"],
    ),
    Case(
        id="t91-18-yourself-allowed",
        what="blocking or reporting yourself reaching the database",
        edits=[
            (
                SAFETY_SERVICE,
                "    if other_id == user.id:\n        raise _not_yourself(what)\n",
                "",
            )
        ],
        expect=[
            "test_nobody_is_not_found_and_yourself_is_not_allowed",
        ],
    ),
    Case(
        id="t91-19-export-forgets-the-unblock",
        what="D-502's export of your blocks without when you lifted them",
        edits=[
            (
                ACCOUNT_REPO91,
                "            select(Block.created_at, Block.unblocked_at)\n",
                "            select(Block.created_at)\n",
            )
        ],
        expect=["test_the_export_is_all_mine_and_nothing_of_theirs"],
    ),
]

# --- P-592: a worker's queued events published -------------------------------------

WORKER_MAIN = "app/workers/main.py"
CORE_DB = "app/core/db.py"
P592_SELECTION = [
    "tests/workers/test_worker_events.py",
    "tests/modules/realtime",
]

P592: list[Case] = [
    Case(
        id="p592-01-the-worker-publishes-nothing",
        what="P-592's hole: the worker's jobs open plain sessions, so a credit never reaches a screen",
        edits=[
            (
                WORKER_MAIN,
                '        sessionmaker=publishing(build_sessionmaker(engine), ctx["redis"]),\n',
                "        sessionmaker=build_sessionmaker(engine),\n",
            )
        ],
        expect=["test_a_jobs_committed_event_reaches_the_persons_sockets"],
    ),
    Case(
        id="p592-02-publishing-forgets-to-publish",
        what="the shared opener takes the committed events and publishes none",
        edits=[
            (
                CORE_DB,
                "        finally:\n            await events.publish(committed, redis)\n",
                "        finally:\n            await events.publish([], redis)\n",
            )
        ],
        expect=[
            "test_a_jobs_committed_event_reaches_the_persons_sockets",
            "test_a_reward_credited_in_verify_selfie_moves_both_balances",
        ],
    ),
]

# --- T-7.12: one Thread's gift and kudos answers (D-880) -------------------------

T712_SELECTION = ["tests/modules/threads/test_view.py"]
THREADS_SERVICE712 = "app/modules/threads/service.py"
THREAD_KUDOS = "test_kudos_is_the_profiles_and_post_kudos_own_answer"

T712: list[Case] = [
    Case(
        id="t712-01-gift-by-a-guessed-gender",
        what="the Thread's gift answer assumes she is a woman instead of reading it",
        edits=[
            (
                THREADS_SERVICE712,
                "            session, user, other_id, await repository.gender_of(session, other_id)\n",
                "            session, user, other_id, type(user.gender).FEMALE\n",
            )
        ],
        expect=[f"{THREAD_GIFT}[male-male-men-False]"],
    ),
    Case(
        id="t712-02-kudos-a-second-rule",
        what="the Thread's kudos answer its own guess, not kudos.service.state",
        edits=[
            (
                THREADS_SERVICE712,
                "        kudos = await kudos_service.state(session, user.id, other_id, thread)\n",
                '        kudos = "can_give"\n',
            )
        ],
        expect=[f"{THREAD_KUDOS}[3-False-too_early]", f"{THREAD_KUDOS}[5-True-given]"],
    ),
]

# --- T-9.8: the cleared chats, the filed reports, D-910's badge -----------------------

THREADS_REPO98 = "app/modules/threads/repository.py"
SAFETY_REPO98 = "app/modules/safety/repository.py"
SAFETY_SERVICE98 = "app/modules/safety/service.py"
SAFETY_SCHEMAS98 = "app/modules/safety/schemas.py"
BADGE98 = "app/modules/verification/repository.py"
PHOTOS_SERVICE98 = "app/modules/photos/service.py"
T98_SELECTION = [
    "tests/modules/threads",
    "tests/modules/safety",
    "tests/modules/verification",
    "tests/modules/photos/test_face_photo.py",
]

T98: list[Case] = [
    Case(
        id="t98-01-anyones-clearing-listed",
        what="the cleared list reading anyone's clearing of my Thread as mine",
        edits=[
            (
                THREADS_REPO98,
                "        .join(mine, and_(mine.thread_id == Thread.id, mine.user_id == viewer_id))\n",
                "        .join(mine, mine.thread_id == Thread.id)\n",
            )
        ],
        expect=["test_only_my_own_clearing_is_listed"],
    ),
    Case(
        id="t98-02-cleared-list-keeps-what-came-back",
        what="a chat a message brought back still listed as cleared",
        edits=[
            (
                THREADS_REPO98,
                "                Thread.last_message_at <= mine.cleared_at,\n",
                "                true(),\n",
            )
        ],
        expect=[
            "test_a_cleared_chat_is_listed_until_a_message_or_a_restore_brings_it_back"
        ],
    ),
    Case(
        id="t98-03-cleared-across-a-block",
        what="the lists, the cleared one too, showing a Thread across a block",
        edits=[
            (
                THREADS_REPO98,
                "            ~blocked_either_way(viewer_id, other.id),\n",
                "",
            )
        ],
        expect=[
            "test_one_across_a_block_isnt_listed_and_an_unblock_brings_it_back[me]",
            "test_one_across_a_block_isnt_listed_and_an_unblock_brings_it_back[them]",
        ],
    ),
    Case(
        id="t98-04-unread-takes-every-clearing",
        what="the unread count's clearing uncorrelated, every clearing the viewer has",
        edits=[(THREADS_REPO98, "        .correlate(Thread)\n", "")],
        expect=[
            "test_each_thread_counts_its_unread_after_its_own_clearing",
            "test_a_cleared_chat_is_listed_until_a_message_or_a_restore_brings_it_back",
        ],
    ),
    Case(
        id="t98-05-reports-about-me-listed",
        what="the filed list not asking who filed",
        edits=[
            (
                SAFETY_REPO98,
                "        .where(Report.reporter_id == reporter_id)\n",
                "        .where(Report.reporter_id.is_not(None))\n",
            )
        ],
        expect=["test_my_reports_are_listed_newest_first_and_never_one_about_me"],
    ),
    Case(
        id="t98-06-the-status-told",
        what="D-911: what moderation did, said in the reporter's list",
        edits=[
            (
                SAFETY_REPO98,
                "            Report.reason,\n            Report.created_at,\n",
                "            Report.reason,\n            Report.status,\n            Report.created_at,\n",
            ),
            (
                SAFETY_SCHEMAS98,
                "    reason: ReportReason\n    created_at: datetime\n    reported: CardLite\n",
                "    reason: ReportReason\n    status: str\n    created_at: datetime\n    reported: CardLite\n",
            ),
            (
                SAFETY_SERVICE98,
                "        reason=row.reason,\n        created_at=row.created_at,\n        reported=CardLite(\n",
                "        reason=row.reason,\n        status=row.status,\n        created_at=row.created_at,\n        reported=CardLite(\n",
            ),
        ],
        expect=[
            "test_what_moderation_did_is_never_said",
            "test_my_reports_are_listed_newest_first_and_never_one_about_me",
        ],
    ),
    Case(
        id="t98-07-a-photo-across-a-block",
        what="D-862: the reported person's photo and presence shown across a block",
        edits=[
            (
                SAFETY_SERVICE98,
                "    shown = not deleted and not row.blocked\n",
                "    shown = not deleted\n",
            )
        ],
        expect=[
            "test_across_a_block_the_card_is_the_name_alone_whoever_blocked[me]",
            "test_across_a_block_the_card_is_the_name_alone_whoever_blocked[them]",
        ],
    ),
    Case(
        id="t98-08-reports-oldest-first",
        what="the filed list oldest first",
        edits=[
            (
                SAFETY_REPO98,
                "        .order_by(Report.created_at.desc(), Report.id.desc())\n",
                "        .order_by(Report.created_at, Report.id)\n",
            )
        ],
        expect=["test_my_reports_are_listed_newest_first_and_never_one_about_me"],
    ),
    Case(
        id="t98-09-the-badge-from-any-photo",
        what="D-910 undone: a match anywhere on the profile lends the main photo the badge",
        edits=[
            (
                BADGE98,
                "    return and_(is_verified.is_(True), main_matched.is_(True))\n",
                (
                    "    return and_(\n"
                    "        is_verified.is_(True),\n"
                    "        select(Photo.id)\n"
                    "        .where(\n"
                    "            Photo.user_id == user_id,\n"
                    "            Photo.kind == PhotoKind.PUBLIC,\n"
                    "            Photo.status == ReviewStatus.APPROVED,\n"
                    "            Photo.public_key.is_not(None),\n"
                    '            Photo.moderation["selfie_match"]["matched"].as_boolean().is_(True),\n'
                    "        )\n"
                    "        .exists(),\n"
                    "    )\n"
                ),
            )
        ],
        expect=[
            "test_the_query_needs_is_verified_and_a_main_photo_that_matched",
            "test_a_reorder_that_puts_an_unmatched_photo_first_turns_it_off",
        ],
    ),
    Case(
        id="t98-10-the-main-photo-is-the-last",
        what="the badge reading a photo other than the card's main one",
        edits=[
            (
                BADGE98,
                "        .order_by(Photo.position, Photo.id)\n",
                "        .order_by(Photo.position.desc(), Photo.id)\n",
            )
        ],
        expect=[
            "test_the_query_needs_is_verified_and_a_main_photo_that_matched",
            "test_a_reorder_that_puts_an_unmatched_photo_first_turns_it_off",
        ],
    ),
    Case(
        id="t98-11-the-face-photo-swapped-once-matched",
        what="the founder's condition: a matched face photo swapped from under the badge",
        edits=[
            (
                PHOTOS_SERVICE98,
                (
                    "    if user.is_verified:\n"
                    "        raise AppError(\n"
                    '            "NOT_ALLOWED", "Your face photo can\'t change once your selfie matched."\n'
                    "        )\n"
                ),
                "",
            )
        ],
        expect=[
            "test_swapping_the_face_photo_once_matched_is_refused_and_the_badge_stands",
            "test_the_face_photo_cant_change_once_the_selfie_matched",
        ],
    ),
]

# --- P-680: each E2E browser context a client of its own (D-890) ----------------

P680_SELECTION = ["tests/test_config.py", "tests/test_e2e_server.py"]
CONFIG = "app/core/config.py"
E2E_SERVER = "tests/e2e_server.py"
CADDY_ONLY = "test_outside_local_only_caddys_header_is_read"

P680: list[Case] = [
    Case(
        id="p680-1-deployed-reads-any-header",
        what="a deployed build reading the client's IP from any header it is given",
        edits=[
            (
                CONFIG,
                "            and self.CLIENT_IP_HEADER.lower() not in PROXY_CLIENT_IP_HEADERS\n",
                "            and False\n",
            )
        ],
        expect=[
            f"{CADDY_ONLY}[X-Forwarded-For-staging]",
            f"{CADDY_ONLY}[X-Forwarded-For-production]",
            f"{CADDY_ONLY}[X-E2E-Client-IP-staging]",
            f"{CADDY_ONLY}[X-E2E-Client-IP-production]",
        ],
    ),
    Case(
        id="p680-2-header-name-case-sensitive",
        what="Caddy's header refused in another case, which HTTP treats as the same",
        edits=[
            (
                CONFIG,
                "            and self.CLIENT_IP_HEADER.lower() not in PROXY_CLIENT_IP_HEADERS\n",
                "            and self.CLIENT_IP_HEADER not in PROXY_CLIENT_IP_HEADERS\n",
            )
        ],
        expect=["test_outside_local_caddys_header_is_read_in_any_case"],
    ),
    Case(
        id="p680-3-e2e-reads-the-socket",
        what="the E2E server keying every context on 127.0.0.1, one budget for all",
        edits=[(E2E_SERVER, "        CLIENT_IP_HEADER=E2E_CLIENT_IP_HEADER,\n", "")],
        expect=[
            "test_the_e2e_server_reads_each_contexts_header_and_is_local",
            "test_each_context_has_d066s_twenty_sends_of_its_own",
        ],
    ),
]

# --- P-49: each deployment reads only the header its CLIENT_IP_HEADER names --------

P49_SELECTION = ["tests/core/test_deps.py"]
DEPS49 = "app/core/deps.py"
NAMED_LINE = "        return request.headers.get(settings.CLIENT_IP_HEADER)\n"
ONLY_NAMED = "test_a_deployment_reads_only_the_header_it_names"
OTHER_ALONE = "test_the_other_proxys_header_alone_escapes_nothing"

P49: list[Case] = [
    Case(
        id="p49-1-either-proxys-header-is-read",
        what="a deployment reading the other proxy's header when its own is absent",
        edits=[
            (
                DEPS49,
                NAMED_LINE,
                (
                    "        return request.headers.get(settings.CLIENT_IP_HEADER) or "
                    'request.headers.get("fly-client-ip") or request.headers.get("caddy-client-ip")\n'
                ),
            )
        ],
        expect=[
            f"{OTHER_ALONE}[Caddy-Client-IP-Fly-Client-IP]",
            f"{OTHER_ALONE}[Fly-Client-IP-Caddy-Client-IP]",
        ],
    ),
    Case(
        id="p49-2-the-other-proxys-header-wins",
        what="a deployment preferring the other proxy's header over its own",
        edits=[
            (
                DEPS49,
                NAMED_LINE,
                (
                    '        return request.headers.get("fly-client-ip") or '
                    'request.headers.get("caddy-client-ip")\n'
                ),
            )
        ],
        # Behind Caddy only: with Fly's header configured, preferring it is right.
        expect=[f"{ONLY_NAMED}[Caddy-Client-IP-Fly-Client-IP]"],
    ),
]

# --- T-9.2: fraud scoring and auto-freeze -----------------------------------------

FRAUD = "app/modules/safety/fraud.py"
SCORING = "app/modules/safety/scoring.py"
SIGNALS = "app/modules/safety/signals.py"
SAFETY_SERVICE92 = "app/modules/safety/service.py"
SAFETY_REPO92 = "app/modules/safety/repository.py"
MESSAGES_SERVICE92 = "app/modules/messages/service.py"
MESSAGES_REPO92 = "app/modules/messages/repository.py"
THREADS_REPO92 = "app/modules/threads/repository.py"
AUTH_REPO92 = "app/modules/auth/repository.py"
FRAUD_WORKER = "app/workers/tasks/recompute_fraud.py"
WORKER_MAIN92 = "app/workers/main.py"
SYSTEM_USER_MIGRATION = "alembic/versions/20261009_4800f0e8d5a9_system_user.py"
T92_SELECTION = [
    "tests/modules/safety",
    "tests/tools/test_unfreeze.py",
    "tests/workers/test_recompute_fraud.py",
]
FROZE = "test_a_score_above_80_freezes_signs_out_closes_sockets_and_audits"
THIRD_REPORT = "test_three_reporters_sharing_a_thread_freeze_in_the_third_report"

T92: list[Case] = [
    Case(
        id="t92-01-a-report-is-no-signal",
        what="a report filed and no signal written for the person reported",
        edits=[
            (
                SAFETY_SERVICE92,
                "        signals.record_report_received(\n",
                "        if False:\n          signals.record_report_received(\n",
            )
        ],
        expect=["test_a_report_is_a_signal_on_the_person_reported_naming_the_report"],
    ),
    Case(
        id="t92-02-a-report-scores-nobody",
        what="D-031's three reports left to the next sweep, not the third report",
        edits=[
            (
                SAFETY_SERVICE92,
                "        await scoring.recompute(session, body.reported_id)\n",
                "",
            )
        ],
        expect=[THIRD_REPORT],
    ),
    Case(
        id="t92-03-scored-without-the-lock",
        what="two reports at once each counting two, so neither freezes",
        edits=[
            (
                SAFETY_REPO92,
                "    query = query.with_for_update(key_share=True, skip_locked=skip_locked)\n",
                "",
            )
        ],
        expect=["test_two_reports_at_once_are_counted_one_after_the_other"],
    ),
    Case(
        id="t92-04-strangers-reports-freeze",
        what="D-901: reporters who never shared a Thread counted toward the freeze",
        edits=[(SAFETY_REPO92, "            shares_a_thread,\n", "")],
        expect=["test_reporters_who_never_shared_a_thread_shadow_and_never_freeze"],
    ),
    Case(
        id="t92-05-by-account-not-number",
        what="D-901: reporters counted by account, so one number counts twice",
        edits=[
            (
                SAFETY_REPO92,
                "        select(func.count(reporter.phone_hash.distinct()))\n",
                "        select(func.count(reporter.id.distinct()))\n",
            )
        ],
        expect=["test_one_numbers_two_accounts_report_as_one"],
    ),
    Case(
        id="t92-06-a-deleted-account-frozen",
        what="D-902: a deleted account frozen, which stops its erasure",
        edits=[
            (
                FRAUD,
                "FREEZABLE: Final = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})\n",
                "FREEZABLE: Final = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED, UserStatus.DELETED})\n",
            )
        ],
        expect=["test_a_deleted_or_banned_account_is_left_as_it_is[deleted]"],
    ),
    Case(
        id="t92-07-frozen-but-signed-in",
        what="D-557: a freeze that leaves the sessions and sockets open",
        edits=[
            (
                SCORING,
                "    await auth_service.sign_out_everywhere(session, user.id)\n",
                "",
            )
        ],
        expect=[FROZE],
    ),
    Case(
        id="t92-08-a-freeze-nobody-audits",
        what="P-20: an automatic freeze written nowhere",
        edits=[
            (
                SCORING,
                "    await admin_service.audit(\n        session,\n        admin_service.SYSTEM_USER_ID,\n        FREEZE,\n",
                "    if False:\n      await admin_service.audit(\n        session,\n        admin_service.SYSTEM_USER_ID,\n        FREEZE,\n",
            )
        ],
        expect=[FROZE],
    ),
    Case(
        id="t92-09-frozen-at-every-score",
        what="D-902: a freeze whatever the status, so written again at every recompute",
        edits=[
            (
                SCORING,
                "    if user.status not in fraud.FREEZABLE:\n        return False\n",
                "",
            )
        ],
        expect=[
            "test_a_freeze_is_written_once_however_often_it_is_scored",
            "test_a_deleted_or_banned_account_is_left_as_it_is[banned]",
        ],
    ),
    Case(
        id="t92-10-nothing-decays",
        what="D-900's decay lost: a week-old signal counts in full",
        edits=[
            (
                FRAUD,
                "    return weight * left if left > 0 else 0.0\n",
                "    return float(weight)\n",
            )
        ],
        expect=[
            "test_older_signals_count_less_and_a_week_old_ones_not_at_all",
            "test_an_event_decays_in_a_straight_line_to_nothing_at_seven_days",
        ],
    ),
    Case(
        id="t92-11-a-minor-score-uncapped",
        what="D-093: possible-minor scores able to shadow or freeze on their own",
        edits=[
            (
                FRAUD,
                "    POSSIBLE_MINOR_SCORE: 20,\n",
                "    POSSIBLE_MINOR_SCORE: 100,\n",
            )
        ],
        expect=[
            "test_possible_minor_scores_never_act_on_anyone_alone",
            "test_a_possible_minor_never_leaves_the_normal_band_on_its_own",
        ],
    ),
    Case(
        id="t92-12-every-report-counts",
        what="one reporter's repeated reports each counted",
        edits=[
            (
                FRAUD,
                "            key = event.reporter if event.reporter is not None else id(event)\n",
                "            key = id(event)\n",
            )
        ],
        expect=[
            "test_one_reporter_three_times_is_one",
            "test_a_report_counts_once_per_reporter_and_has_no_cap",
        ],
    ),
    Case(
        id="t92-13-masking-is-no-signal",
        what="a masked contact detail never written as a signal",
        edits=[
            (
                MESSAGES_SERVICE92,
                "        safety_signals.record_contact_masked(session, sender_id)\n",
                "        pass\n",
            )
        ],
        expect=["test_a_masked_contact_is_a_signal_and_never_the_message"],
    ),
    Case(
        id="t92-14-a-crossing-every-time",
        what="a threshold signal written at every crossing, not once a day",
        edits=[
            (
                SIGNALS,
                "    if await repository.has_signal_since(session, user_id, signal, since):\n",
                "    if False:\n",
            )
        ],
        expect=["test_a_threshold_signal_is_written_once_a_day"],
    ),
    Case(
        id="t92-15-any-message-is-a-first",
        what="a message after someone else's first counted as a first message",
        edits=[
            (
                MESSAGES_REPO92,
                "            ~exists().where(\n                earlier.thread_id == Message.thread_id,\n                earlier.created_at < Message.created_at,\n            ),\n",
                "",
            )
        ],
        expect=["test_the_same_first_message_to_more_than_10_people_is_a_signal"],
    ),
    Case(
        id="t92-16-a-rotation-is-a-sign-in",
        what="D-903: each rotated session counted as a sign-in",
        edits=[
            (
                AUTH_REPO92,
                "        select(func.count(Session.family_id.distinct())).where(\n",
                "        select(func.count(Session.id)).where(\n",
            ),
            (
                AUTH_REPO92,
                "            Session.revoked_at.is_(None),\n            Session.auth_time >= since,\n",
                "            Session.auth_time >= since,\n",
            ),
        ],
        expect=["test_refreshing_a_session_is_no_sign_in"],
    ),
    Case(
        id="t92-26-sign-ins-from-any-time",
        what="D-903: sign-ins counted however long ago they were",
        edits=[(AUTH_REPO92, "            Session.auth_time >= since,\n", "")],
        expect=["test_sign_ins_older_than_seven_days_dont_count"],
    ),
    Case(
        id="t92-27-in-the-band-but-never-frozen",
        what="an account the freeze band reached while deleted, never frozen once restored",
        edits=[
            (
                SCORING,
                "    if band is FraudBand.FREEZE:\n",
                "    if band is FraudBand.FREEZE and before is not FraudBand.FREEZE:\n",
            )
        ],
        expect=["test_an_account_restored_while_in_the_freeze_band_is_frozen_then"],
    ),
    Case(
        id="t92-17-a-jump-at-any-time",
        what="a long move counted as a jump however long after the last",
        edits=[
            (
                FRAUD,
                "    return km > JUMP_KM and since_last <= JUMP_WITHIN\n",
                "    return km > JUMP_KM\n",
            )
        ],
        expect=["test_a_far_move_after_an_hour_or_a_near_one_is_no_signal"],
    ),
    Case(
        id="t92-18-unfreeze-forgets-the-reset",
        what="D-906: a lifted freeze scored again on what was set aside",
        edits=[
            (
                SCORING,
                "        counted_from=clock.now(),\n",
                "        counted_from=None,\n",
            )
        ],
        expect=[
            "test_what_was_set_aside_never_freezes_her_again_and_new_signals_count"
        ],
    ),
    Case(
        id="t92-19-anyone-may-unfreeze",
        what="D-906: a freeze lifted in the name of someone who isn't an admin",
        edits=[
            (
                SCORING,
                "        or admin.role is not Role.ADMIN\n",
                "        or False\n",
            )
        ],
        expect=["test_only_an_active_admin_may_lift_one[user]"],
    ),
    Case(
        id="t92-20-an-unfreeze-nobody-audits",
        what="D-906: a lifted freeze written nowhere",
        edits=[
            (
                SCORING,
                "    await admin_service.audit(\n        session,\n        by,\n",
                "    if False:\n      await admin_service.audit(\n        session,\n        by,\n",
            )
        ],
        expect=[
            "test_it_lifts_an_automatic_freeze_on_a_woman_and_starts_her_score_again"
        ],
    ),
    Case(
        id="t92-21-the-system-user-scored",
        what="D-905: the system user scored like a person",
        edits=[
            (
                SCORING,
                "    if user is None or user.id == admin_service.SYSTEM_USER_ID:\n        return None\n",
                "    if user is None:\n        return None\n",
            )
        ],
        expect=["test_the_system_user_is_never_scored"],
    ),
    Case(
        id="t92-22-old-scores-never-decay",
        what="the sweep reading only new signals, so a score never comes down",
        edits=[
            (
                SAFETY_REPO92,
                "    ids = signalled.union(scored).subquery()\n",
                "    ids = signalled.subquery()\n",
            )
        ],
        expect=["test_a_score_decays_to_nothing_once_its_signals_are_a_week_old"],
    ),
    Case(
        id="t92-23-the-system-user-dropped-from-under-the-log",
        what="the system user's downgrade deleting the row the audit log names",
        edits=[(SYSTEM_USER_MIGRATION, "    if named:\n", "    if False:\n")],
        expect=["test_the_downgrade_refuses_while_the_audit_log_names_it"],
    ),
    Case(
        id="t92-24-the-loop-never-starts",
        what="the worker never starting recompute_fraud's loop",
        edits=[
            (
                WORKER_MAIN92,
                '    ctx["fraud"] = asyncio.create_task(every_ten_minutes(ctx).run())\n',
                "",
            )
        ],
        expect=["test_the_worker_starts_the_fraud_loop_and_stops_it"],
    ),
    Case(
        id="t92-25-her-threads-are-his",
        what="Threads opened to him counted as his openings",
        edits=[(THREADS_REPO92, "            Thread.opened_by == user_id,\n", "")],
        expect=["test_more_than_30_threads_opened_in_a_day_is_a_signal[29-False]"],
    ),
]

# --- P-61: a 500 carries its CORS headers, for an allowed origin only ----------

P61_SELECTION = ["tests/core/test_headers.py"]
HEADERS61 = "app/core/headers.py"
ERRORS61 = "app/core/errors.py"
CORS_CALL61 = (
    "            **cors_headers(\n"
    '                request.headers.get("origin"),\n'
    "                request.app.state.settings.CORS_ORIGINS,\n"
    "            ),\n"
)

P61: list[Case] = [
    Case(
        id="p61-01-a-500-without-cors",
        what="P-61: the 500 left without its CORS headers, unreadable to the web",
        edits=[
            (
                ERRORS61,
                CORS_CALL61,
                "",
            )
        ],
        expect=["test_a_500_carries_the_cors_headers_a_200_does"],
    ),
    Case(
        id="p61-02-any-origin-reads-a-500",
        what="P-61: a 500's CORS headers given to an origin CORS_ORIGINS doesn't name",
        edits=[
            (
                HEADERS61,
                "    if origin is None or origin not in allowed:\n",
                "    if origin is None:\n",
            )
        ],
        expect=[
            "test_a_500_for_any_other_origin_carries_no_cors_header[another origin]",
            "test_a_500_for_any_other_origin_carries_no_cors_header[a near miss]",
        ],
    ),
]

# --- P-80: no query value in the API's database errors (D-990) --------------------

DB80 = "app/core/db.py"
P80_SELECTION = ["tests/core/test_db.py", "tests/workers/test_worker.py"]
NO_VALUES = "test_the_apis_database_errors_carry_no_values"
DETAIL_LEAKS = [
    f"{NO_VALUES}[a duplicate key, in DETAIL]",
    f"{NO_VALUES}[a check's failing row, in DETAIL]",
]
MESSAGE_LEAKS = [
    f"{NO_VALUES}[a cast Postgres refused, in its message]",
    f"{NO_VALUES}[an argument asyncpg can't encode, in its message]",
]

P80: list[Case] = [
    Case(
        id="p80-1-the-api-s-engine-shows-values",
        what="the API's engine built without hide_parameters, as before P-80",
        edits=[("app/main.py", "        hide_parameters=True,\n", "")],
        expect=[
            *DETAIL_LEAKS,
            *MESSAGE_LEAKS,
            "test_a_withheld_error_keeps_its_code_and_constraint",
            "test_postgres_s_words_are_kept_only_where_they_quote_nothing",
        ],
    ),
    Case(
        id="p80-2-sqlalchemy-s-option-alone",
        what="hide_parameters trusted to hide values, the hook never installed",
        edits=[
            (
                DB80,
                '        event.listen(engine.sync_engine, "handle_error", _withhold_values)\n',
                "        pass\n",
            )
        ],
        expect=[
            *DETAIL_LEAKS,
            *MESSAGE_LEAKS,
            "test_the_workers_database_errors_carry_no_values",
        ],
    ),
    Case(
        id="p80-3-the-driver-keeps-detail",
        what="the text rewritten but the driver's DETAIL left for a reporter to read",
        edits=[
            (
                DB80,
                '            setattr(driver, field, safe if field == "message" else None)\n',
                "            pass\n",
            )
        ],
        expect=[
            *DETAIL_LEAKS,
            "test_a_withheld_error_keeps_its_code_and_constraint",
        ],
    ),
    Case(
        id="p80-4-every-message-kept",
        what="Postgres's message kept for every error, a cast's quoted text too",
        edits=[
            (DB80, '_MESSAGE_KEPT_FOR = ("23", "P0")\n', '_MESSAGE_KEPT_FOR = ("",)\n')
        ],
        # asyncpg's own refusals have no message field, so stay withheld.
        expect=[
            MESSAGE_LEAKS[0],
            "test_postgres_s_words_are_kept_only_where_they_quote_nothing",
        ],
    ),
    Case(
        id="p80-5-sqlalchemy-s-own-text-kept",
        what="the driver's layers rewritten, SQLAlchemy's error left as it was built",
        edits=[
            (
                DB80,
                '    error.args = (f"({type(adapted).__module__}.{type(adapted).__name__}) {adapted}",)\n',
                "",
            )
        ],
        expect=[*DETAIL_LEAKS, *MESSAGE_LEAKS],
    ),
]

# --- T-9.5: the moderation panel ------------------------------------------------------

ADMIN_ROUTER95 = "app/modules/admin/router.py"
ADMIN_PANEL95 = "app/modules/admin/panel.py"
ADMIN_RULES95 = "app/modules/admin/rules.py"
ADMIN_REPO95 = "app/modules/admin/repository.py"
AUTH_REPO95 = "app/modules/auth/repository.py"
LIFT_MIGRATION95 = "alembic/versions/20261016_7c8a628fd3d7_bans_are_lifted_in_place.py"
REF_MIGRATION95 = (
    "alembic/versions/20261016_7a758777affd_admin_grant_names_its_audit_row.py"
)
SHAPE_MIGRATION95 = (
    "alembic/versions/20261016_688032b1dc7a_ledger_shape_names_admin_correction.py"
)
WALLET_RULES95 = "app/modules/wallet/rules.py"
WALLET_SERVICE95 = "app/modules/wallet/service.py"
PHOTOS_SERVICE95 = "app/modules/photos/service.py"
SEED_RUN95 = "seed/run.py"
T95_SELECTION = [
    "tests/modules/admin",
    "tests/modules/wallet",
    "tests/modules/auth/test_ban_lift_migration.py",
    "tests/modules/pricing/test_debit_callers.py",
]
T95_SEED_SELECTION = ["tests/seed/test_seed.py"]

T95: list[Case] = [
    Case(
        id="t95-01-a-user-reaches-the-panel",
        what="a user's token let into every panel route",
        edits=[
            (
                ADMIN_ROUTER95,
                "Staff = Annotated[User, Depends(require_role(*STAFF))]\n",
                "Staff = Annotated[User, Depends(require_role(Role.USER, *STAFF))]\n",
            ),
        ],
        expect=["test_a_user_is_forbidden_and_nothing_is_written"],
    ),
    Case(
        id="t95-02-a-moderator-moves-velas",
        what="a moderator granting Velas, at the route and in the panel",
        edits=[
            (
                ADMIN_ROUTER95,
                "Admin = Annotated[User, Depends(require_role(Role.ADMIN))]\n",
                "Admin = Annotated[User, Depends(require_role(*STAFF))]\n",
            ),
            (
                ADMIN_PANEL95,
                '    changes nothing and writes nothing; for another, `ALREADY_EXISTS`."""\n    if staff.role is not Role.ADMIN:\n        raise _forbidden()\n',
                '    changes nothing and writes nothing; for another, `ALREADY_EXISTS`."""\n',
            ),
        ],
        expect=["test_a_moderator_is_forbidden_what_only_an_admin_may_call"],
    ),
    Case(
        id="t95-03-a-moderator-lifts-a-ban",
        what="D-922: a moderator allowed every status change",
        edits=[
            (
                ADMIN_RULES95,
                "    return role is Role.ADMIN or target not in ADMIN_ONLY\n",
                "    return True\n",
            ),
        ],
        expect=["test_a_moderator_never_bans_unbans_or_unfreezes"],
    ),
    Case(
        id="t95-04-a-ban-leaves-sessions",
        what="a ban with the person still signed in",
        edits=[
            (
                ADMIN_PANEL95,
                "        user.status = UserStatus.BANNED\n        await auth_service.sign_out_everywhere(session, user.id)\n",
                "        user.status = UserStatus.BANNED\n",
            ),
        ],
        expect=["test_an_admins_ban_bars_the_number_signs_out_and_audits"],
    ),
    Case(
        id="t95-05-a-freeze-leaves-sessions",
        what="a staff freeze with the person still signed in",
        edits=[
            (
                ADMIN_PANEL95,
                "    user.status = UserStatus.FROZEN\n    await auth_service.sign_out_everywhere(session, user.id)\n",
                "    user.status = UserStatus.FROZEN\n",
            ),
        ],
        expect=["test_staff_freeze_signs_out_closes_sockets_and_audits"],
    ),
    Case(
        id="t95-06-a-lifted-ban-still-bars",
        what="sign-in reading a lifted ban as standing",
        edits=[
            (AUTH_REPO95, "            BannedIdentity.lifted_at.is_(None),\n", ""),
        ],
        expect=["test_an_unban_lifts_the_row_in_place_and_returns_the_account"],
    ),
    Case(
        id="t95-07-an-underage-ban-lifted",
        what="D-922: the trigger letting any reason be lifted",
        edits=[
            (
                LIFT_MIGRATION95,
                "                if old.reason is distinct from 'ban' then\n",
                "                if false then\n",
            ),
        ],
        expect=["test_an_underage_ban_can_never_be_lifted_nor_any_ban_deleted"],
    ),
    Case(
        id="t95-08-an-unban-forgets-the-deletion",
        what="an unban making active someone who had asked to go",
        edits=[
            (
                ADMIN_PANEL95,
                "            UserStatus.DELETED\n            if user.deleted_requested_at is not None\n            else UserStatus.ACTIVE\n",
                "            UserStatus.ACTIVE\n",
            ),
        ],
        expect=["test_an_unban_of_someone_who_asked_to_go_returns_them_to_deleted"],
    ),
    Case(
        id="t95-09-a-correction-past-the-balance",
        what="a correction beyond the balance, reaching the wallet's 402",
        edits=[
            (
                ADMIN_PANEL95,
                "        if delta < 0 and balance < -delta:\n",
                "        if False:\n",
            ),
        ],
        expect=[
            "test_a_correction_beyond_the_balance_is_not_allowed_and_writes_nothing"
        ],
    ),
    Case(
        id="t95-10-a-retry-applies-twice",
        what="the same key again, not answered from the ledger",
        edits=[
            (
                ADMIN_PANEL95,
                "            if earlier_reason is ledger_reason and earlier.delta == delta:\n                return\n",
                "            if earlier_reason is ledger_reason and earlier.delta == delta:\n                continue\n",
            ),
        ],
        expect=["test_the_same_key_again_changes_nothing_and_writes_nothing"],
    ),
    Case(
        id="t95-11-admin-grant-ref-optional",
        what="D-923: the rule letting admin_grant name no audit row",
        edits=[
            (
                WALLET_RULES95,
                "    LedgerReason.ADMIN_GRANT: Rule(CREDIT, RefType.AUDIT_LOG, caller_names_event=True),\n",
                "    LedgerReason.ADMIN_GRANT: Rule(\n        CREDIT, RefType.AUDIT_LOG, ref_required=False, caller_names_event=True\n    ),\n",
            ),
        ],
        expect=["test_each_reason_has_exactly_one_ref_type_in_the_database"],
    ),
    Case(
        id="t95-12-the-database-takes-a-grant-with-no-ref",
        what="D-923: the migration leaving admin_grant's ref optional",
        edits=[
            (
                REF_MIGRATION95,
                '        "CHECK (ref_id IS NOT NULL) NOT VALID"\n',
                "        \"CHECK (reason = 'admin_grant' OR ref_id IS NOT NULL) NOT VALID\"\n",
            ),
        ],
        expect=["test_an_admin_grant_with_no_ref_is_refused_by_the_database"],
    ),
    Case(
        id="t95-13-a-correction-one-per-event",
        what="admin_correction left inside the per-event index",
        edits=[
            (
                SHAPE_MIGRATION95,
                'REPEATS = (*REPEATS_BEFORE, "admin_correction")\n',
                "REPEATS = REPEATS_BEFORE\n",
            ),
        ],
        expect=["test_one_entry_per_event_except_the_reasons_that_repeat"],
    ),
    Case(
        id="t95-14-the-masked-text-shown",
        what="a Thread read as masked, not as written",
        edits=[
            (
                ADMIN_PANEL95,
                "            body=message.body_raw if message.body_raw is not None else message.body,\n",
                "            body=message.body,\n",
            ),
        ],
        expect=["test_a_masked_message_is_read_as_written_and_a_voice_note_is_linked"],
    ),
    Case(
        id="t95-15-a-blank-reason-reads",
        what="D-924: a reason of spaces taken",
        edits=[
            (
                ADMIN_PANEL95,
                "    if len(reason) < rules.REASON_MIN:\n",
                "    if False:\n",
            ),
        ],
        expect=["test_a_read_without_a_reason_is_refused_and_unwritten"],
    ),
    Case(
        id="t95-16-a-read-unaudited",
        what="D-924: a Thread read with no audit row",
        edits=[
            (
                ADMIN_PANEL95,
                '            "thread.read",\n            {"reason": reason},\n',
                '            "thread.other",\n            {"reason": reason},\n',
            ),
        ],
        expect=["test_every_message_shows_whatever_either_person_cleared"],
    ),
    Case(
        id="t95-17-a-moderator-sees-the-number",
        what="D-927: the whole number shown to a moderator",
        edits=[
            (
                ADMIN_PANEL95,
                "            phone = whole if staff.role is Role.ADMIN else rules.masked(whole)\n",
                "            phone = whole\n",
            ),
        ],
        expect=["test_a_moderator_sees_it_masked"],
    ),
    Case(
        id="t95-18-the-system-user-listed",
        what="D-905: the system user in search",
        edits=[
            (
                ADMIN_REPO95,
                "        .where(User.id != SYSTEM_USER_ID)\n        .order_by(User.created_at.desc(), User.id.desc())\n",
                "        .order_by(User.created_at.desc(), User.id.desc())\n",
            ),
        ],
        expect=["test_the_system_user_is_never_listed_nor_read"],
    ),
    Case(
        id="t95-19-a-moderator-sees-revenue",
        what="D-926: money in shown to a moderator",
        edits=[
            (
                ADMIN_PANEL95,
                "        if staff.role is Role.ADMIN:\n            year = payments_rules.financial_year_of(now)\n",
                "        if True:\n            year = payments_rules.financial_year_of(now)\n",
            ),
        ],
        expect=["test_staff_see_counts_and_only_an_admin_sees_revenue"],
    ),
    Case(
        id="t95-20-selfies-in-the-queue",
        what="D-925: selfies and face photos in the panel",
        edits=[
            (
                ADMIN_RULES95,
                "PANEL_PHOTO_KINDS: Final = frozenset({PhotoKind.PUBLIC, PhotoKind.PRIVATE})\n",
                "PANEL_PHOTO_KINDS: Final = frozenset(PhotoKind)\n",
            ),
        ],
        expect=["test_the_queue_is_pending_public_and_private_photos_oldest_first"],
    ),
    Case(
        id="t95-21-completeness-stale",
        what="P-210: a staff decision leaving completeness as it was",
        edits=[
            (
                PHOTOS_SERVICE95,
                "        )\n    if photo.kind is PhotoKind.PUBLIC:\n        await onboarding_service.refresh_completeness(session, user)\n    return decided\n",
                "        )\n    return decided\n",
            ),
        ],
        expect=[
            "test_approving_a_public_photo_publishes_it_and_lifts_completeness",
            "test_taking_down_an_approved_photo_removes_its_public_copies_and_keeps_the_record",
        ],
    ),
    Case(
        id="t95-22-a-takedown-stays-public",
        what="a taken-down photo left in the public bucket",
        edits=[
            (
                PHOTOS_SERVICE95,
                "    for key in decided.public_keys:\n        await storage.delete(settings.R2_BUCKET_PUBLIC, key)\n",
                "",
            ),
        ],
        expect=[
            "test_taking_down_an_approved_photo_removes_its_public_copies_and_keeps_the_record"
        ],
    ),
    Case(
        id="t95-23-a-report-resolved-twice",
        what="a resolved report resolved again",
        edits=[
            (
                ADMIN_PANEL95,
                "        if report.status is not ReportStatus.OPEN:\n",
                "        if False:\n",
            ),
        ],
        expect=["test_a_report_is_resolved_once"],
    ),
    Case(
        id="t95-24-a-moderator-bans-from-a-report",
        what="D-921: a moderator's ban from a report, both checks",
        edits=[
            (
                ADMIN_PANEL95,
                "    if action is ReportAction.BAN and staff.role is not Role.ADMIN:\n        raise _forbidden()\n",
                "",
            ),
            (
                ADMIN_PANEL95,
                "    if staff.role is not Role.ADMIN:\n        raise _forbidden()\n    erased = user.anonymised_at is not None\n",
                "    erased = user.anonymised_at is not None\n",
            ),
        ],
        expect=["test_a_moderator_never_bans_from_a_report"],
    ),
    Case(
        id="t95-25-a-deleted-account-frozen",
        what="D-902: a staff freeze reaching a deleted account",
        edits=[
            (
                ADMIN_RULES95,
                "FREEZABLE: Final = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})\n",
                "FREEZABLE: Final = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED, UserStatus.DELETED})\n",
            ),
        ],
        expect=["test_only_who_can_sign_in_is_frozen_and_nothing_else_is_written"],
    ),
    Case(
        id="t95-26-the-correction-unlisted",
        what="P-152: the correction left off debit()'s list",
        edits=[
            (
                WALLET_SERVICE95,
                '        ("app.modules.admin.panel", "_correct"),\n',
                "",
            ),
        ],
        expect=[
            "test_the_run_time_list_is_the_scans",
            "test_a_correction_is_exactly_one_admin_correction_and_the_ledger_reconciles",
        ],
    ),
    Case(
        id="t95-27-every-freeze-manual",
        what="P-800: automatic freezes not marked",
        edits=[
            (
                ADMIN_PANEL95,
                "        automatic = row.frozen_by == SYSTEM_USER_ID\n",
                "        automatic = False\n",
            ),
        ],
        expect=["test_the_accounts_frozen_now_automatic_ones_marked_newest_first"],
    ),
]
T95_SEED: list[Case] = [
    Case(
        id="t95-28-the-seed-rewrites-an-old-grant",
        what="an earlier seed's grant with no ref met with a new audit row",
        edits=[
            (SEED_RUN95, "    if earlier is not None:\n", "    if False:\n"),
        ],
        expect=["test_an_earlier_seeds_grant_with_no_ref_is_left_as_it_is"],
    ),
]

# --- T-7.13: the E2E's local-only expiry (D-930) ------------------------------

T713_SELECTION = ["tests/modules/e2e/test_expire_thread.py"]
E2E_SERVICE = "app/modules/e2e/service.py"
NOT_RUN_OUT = "test_a_thread_with_no_hour_to_run_out_is_not_found_and_unchanged"
NOT_SERVED = "test_isnt_served_anywhere_else"

T713: list[Case] = [
    Case(
        id="t713-1-served-everywhere",
        what="the test routes mounted whatever ENV and the SMS provider are",
        edits=[
            (
                "app/main.py",
                "    if settings.ENV in E2E_SERVED_IN and settings.SMS_PROVIDER in E2E_SERVED_FOR:\n",
                "    if True:\n",
            )
        ],
        expect=[
            f"{NOT_SERVED}[ENV=staging]",
            f"{NOT_SERVED}[ENV=production]",
            f"{NOT_SERVED}[ENV=preview]",
            f"{NOT_SERVED}[ENV=env-nobody-has-named-2031]",
            f"{NOT_SERVED}[SMS_PROVIDER=msg91]",
        ],
    ),
    Case(
        id="t713-2-runs-out-an-expired-one",
        what="any status given a past hour, an expired Thread's moved again",
        edits=[
            (
                E2E_SERVICE,
                "            or thread.status is not ThreadStatus.ACTIVE\n",
                "",
            )
        ],
        expect=[f"{NOT_RUN_OUT}[already-expired]"],
    ),
    Case(
        id="t713-3-runs-out-a-private-message",
        what="a Thread with no expires_at given one, a private message's",
        edits=[(E2E_SERVICE, "            or thread.expires_at is None\n", "")],
        expect=[f"{NOT_RUN_OUT}[private-message]"],
    ),
    Case(
        id="t713-4-hour-left-as-it-was",
        what="the hour left where it was, the call answering as if it had ended",
        edits=[
            (
                E2E_SERVICE,
                "        thread.expires_at = clock.now()\n",
                "        thread.expires_at = thread.expires_at\n",
            )
        ],
        expect=[
            "test_its_hour_ends_at_the_call_and_nothing_else_moves",
            "test_it_is_the_clocks_expiry_his_send_refused_and_hers_delivered",
            "test_his_reopen_after_it_charges_exactly_two",
        ],
    ),
    Case(
        id="t713-5-in-the-schema",
        what="the test routes in OpenAPI, so in `make types` and the web's reach",
        edits=[
            (
                "app/modules/e2e/router.py",
                '\nrouter = APIRouter(prefix="/test", tags=["test"], include_in_schema=False)\n',
                '\nrouter = APIRouter(prefix="/test", tags=["test"])\n',
            )
        ],
        expect=["test_is_never_in_the_schema"],
    ),
]

# --- T-9.9: the ledger audit and the daily reconciliation ----------------------------

PRICING99 = "app/modules/pricing/service.py"
LIKES_SERVICE99 = "app/modules/likes/service.py"
SWIPES_SERVICE99 = "app/modules/swipes/service.py"
WALLET_REPO99 = "app/modules/wallet/repository.py"
WALLET_SERVICE99 = "app/modules/wallet/service.py"
WORKER99 = "app/workers/main.py"
AUDIT99 = "tests/modules/wallet/test_paid_actions.py"
T99_SELECTION = [
    "tests/modules/wallet/test_paid_actions.py",
    "tests/modules/wallet/test_reconcile.py",
    "tests/workers/test_reconcile_ledger.py",
    "tests/workers/test_log_turnover.py",
]
WOMAN99 = "test_a_woman_pays_nothing"
MAN99 = "test_a_man_pays_once_at_the_price"
SHORT99 = "test_too_few_velas_buys_nothing"
FOUND99 = [
    "test_a_balance_written_outside_the_wallet_is_found_and_logged_as_an_error",
    "test_a_ledger_row_the_balance_never_took_is_found_the_other_way",
    "test_balances_that_agree_are_never_reported",
    "test_a_balance_with_no_ledger_rows_at_all_is_found",
    "test_ledger_rows_with_no_wallet_are_found",
    "test_the_job_logs_a_mismatch_at_error_level",
]

T99: list[Case] = [
    Case(
        id="t99-01-a-woman-priced-like-a-man",
        what="D-098 gone: a woman priced at the row's value for every action",
        edits=[
            (
                PRICING99,
                "    return credits if user.gender is Gender.MALE else 0\n",
                "    return credits\n",
            )
        ],
        expect=[
            f"{WOMAN99}[{action}]"
            for action in (
                "thread_open",
                "thread_open-answering",
                "dm_open",
                "thread_reopen-answering",
                "dm_message",
                "album_request",
                "super_like",
                "liked_you_reveal",
            )
        ],
    ),
    Case(
        id="t99-02-a-one-vela-charge-goes-free",
        what="a careless floor: prices of 1 Vela debited as if 0",
        edits=[(PRICING99, "    if price == 0:\n", "    if price <= 1:\n")],
        expect=[
            f"{MAN99}[album_request]",
            f"{MAN99}[liked_you_reveal]",
            f"{SHORT99}[album_request]",
            f"{SHORT99}[liked_you_reveal]",
        ],
    ),
    Case(
        id="t99-03-a-reveal-charged-as-a-super-like",
        what="the wrong reason, and so the wrong price, for a reveal",
        edits=[
            (
                LIKES_SERVICE99,
                "                LedgerReason.LIKED_YOU_REVEAL,\n",
                "                LedgerReason.SUPER_LIKE,\n",
            )
        ],
        expect=[f"{MAN99}[liked_you_reveal]"],
    ),
    Case(
        id="t99-04-a-refused-super-like-kept",
        what="the 402 swallowed: the super like written, nothing paid",
        edits=[
            (
                SWIPES_SERVICE99,
                (
                    "    if direction is SwipeDirection.SUPER:\n"
                    "        await pricing_service.charge(\n"
                ),
                (
                    "    if direction is SwipeDirection.SUPER:\n"
                    '        with __import__("contextlib").suppress(AppError):\n'
                    "          await pricing_service.charge(\n"
                ),
            )
        ],
        expect=[f"{SHORT99}[super_like]"],
    ),
    Case(
        id="t99-05-a-debit-with-no-row",
        what="the gift's row dropped from the audit table: a debit with no tests",
        edits=[
            (
                AUDIT99,
                '    Spend("gift", LedgerReason.GIFT, 5, _gift, REFUSED),\n',
                "",
            )
        ],
        expect=["test_every_debit_of_velas_has_its_three_tests"],
    ),
    Case(
        id="t99-06-the-check-compares-nothing",
        what="the balance compared with itself: no mismatch ever found",
        edits=[
            (
                WALLET_REPO99,
                "        .where(Wallet.balance.is_distinct_from(ledger_sum))\n",
                "        .where(Wallet.balance.is_distinct_from(Wallet.balance))\n",
            )
        ],
        expect=FOUND99,
    ),
    Case(
        id="t99-07-an-inner-join",
        what="a plain join: a wallet with no ledger rows, or rows with no wallet, hidden",
        edits=[
            (
                WALLET_REPO99,
                "        .join(sums, sums.c.user_id == Wallet.user_id, full=True)\n",
                "        .join(sums, sums.c.user_id == Wallet.user_id)\n",
            )
        ],
        expect=[
            "test_a_balance_with_no_ledger_rows_at_all_is_found",
            "test_ledger_rows_with_no_wallet_are_found",
        ],
    ),
    Case(
        id="t99-08-a-mismatch-as-a-warning",
        what="the mismatch logged below error, where T-9.12 forwards nothing",
        edits=[
            (
                WALLET_SERVICE99,
                '        log.error(\n            "wallet.ledger_mismatch",\n',
                '        log.warning(\n            "wallet.ledger_mismatch",\n',
            )
        ],
        expect=[
            "test_a_balance_written_outside_the_wallet_is_found_and_logged_as_an_error",
            "test_the_job_logs_a_mismatch_at_error_level",
        ],
    ),
    Case(
        id="t99-09-the-cron-dropped",
        what="the daily check never scheduled",
        edits=[
            (
                WORKER99,
                (
                    "    cron(\n"
                    "        reconcile_ledger_job.reconcile_ledger,\n"
                    "        name=RECONCILE_LEDGER,\n"
                    "        hour=reconcile_ledger_job.RUN_AT_UTC[0],\n"
                    "        minute=reconcile_ledger_job.RUN_AT_UTC[1],\n"
                    "    ),\n"
                ),
                "",
            )
        ],
        expect=[
            "test_it_runs_once_a_day_at_0830_ist",
            "test_it_runs_once_a_day_at_0900_ist",
        ],
    ),
]


# --- T-9.11: the E2E's local-only staff role (D-963) ---------------------------

T911_SELECTION = ["tests/modules/e2e/test_make_staff.py"]
STAFF_TEST = "test_makes_a_person_staff_and_audits_it"
STAFF_ONLY = "test_gives_only_a_staff_role_and_changes_nothing_else"
STAFF_NOT_SERVED = "test_isnt_served_anywhere_else"

T911: list[Case] = [
    Case(
        id="t911-1-role-served-everywhere",
        what="the test routes mounted whatever ENV and the SMS provider are",
        edits=[
            (
                "app/main.py",
                "    if settings.ENV in E2E_SERVED_IN and settings.SMS_PROVIDER in E2E_SERVED_FOR:\n",
                "    if True:\n",
            )
        ],
        expect=[
            f"{STAFF_NOT_SERVED}[ENV=ci]",
            f"{STAFF_NOT_SERVED}[ENV=staging]",
            f"{STAFF_NOT_SERVED}[ENV=production]",
            f"{STAFF_NOT_SERVED}[ENV=preview]",
            f"{STAFF_NOT_SERVED}[ENV=env-nobody-has-named-2031]",
            f"{STAFF_NOT_SERVED}[SMS_PROVIDER=msg91]",
            f"{STAFF_NOT_SERVED}[ENV=production,SMS_PROVIDER=fake]",
        ],
    ),
    Case(
        id="t911-2-role-gives-user",
        what="any role taken, `user` among them, so it could strip a moderator",
        edits=[
            (
                "app/modules/e2e/schemas.py",
                "    role: Literal[Role.MODERATOR, Role.ADMIN]\n",
                "    role: Role\n",
            )
        ],
        expect=[f"{STAFF_ONLY}[user]"],
    ),
    Case(
        id="t911-3-role-unaudited",
        what="the role changed with no audit_log row beside it",
        edits=[
            (
                E2E_SERVICE,
                (
                    "        await admin_service.audit(\n"
                    "            session,\n"
                    "            admin_service.SYSTEM_USER_ID,\n"
                    '            "user.role",\n'
                    '            {"from": str(was), "to": str(role), "by": "e2e"},\n'
                    '            target=("user", user_id),\n'
                    "        )\n"
                ),
                "",
            )
        ],
        expect=[f"{STAFF_TEST}[moderator]", f"{STAFF_TEST}[admin]"],
    ),
    Case(
        id="t911-4-role-for-the-erased",
        what="an erased account made staff",
        edits=[
            (
                E2E_SERVICE,
                "        if user is None or user.anonymised_at is not None:\n",
                "        if user is None:\n",
            )
        ],
        expect=["test_an_erased_account_is_not_found_and_unchanged"],
    ),
    Case(
        id="t911-5-role-takes-extra-fields",
        what="fields beside the role accepted and ignored",
        edits=[
            (
                "app/modules/e2e/schemas.py",
                (
                    '    """The staff role to give (D-963): moderator or admin, never user."""\n'
                    "\n"
                    '    model_config = ConfigDict(extra="forbid")\n'
                ),
                '    """The staff role to give (D-963): moderator or admin, never user."""\n',
            )
        ],
        expect=["test_refuses_anything_beside_the_role"],
    ),
]


# --- T-9.10: the feed asked for before /me has answered (D-1033) ---------------

T910_SELECTION = [
    "tests/modules/discovery/test_feed.py",
    "tests/modules/users/test_me.py",
]

T910: list[Case] = [
    Case(
        id="t910-1-a-frozen-account-signs-in",
        what="a frozen account let through the request's status check",
        edits=[
            (
                "app/modules/users/service.py",
                "MAY_SIGN_IN = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})\n",
                "MAY_SIGN_IN = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED, UserStatus.FROZEN})\n",
            )
        ],
        expect=["test_a_frozen_account_is_refused_the_feed"],
    ),
]


CASES: list[tuple[Case, list[str]]] = (
    [(c, T51_SELECTION) for c in T51]
    + [(c, T54_SELECTION) for c in T54]
    + T44
    + T46
    + LAND
    + [(c, T52_SELECTION) for c in T52]
    + P142
    + P143
    + [(c, P38_SELECTION) for c in P38]
    + T45
    + T48
    + [(c, T411_SELECTION) for c in T411]
    + T412
    + [(c, T81_SELECTION) for c in T81]
    + P120
    + P210
    + T62
    + T63
    + [(c, T96_SELECTION) for c in T96]
    + P47
    + T64
    + [(c, T82_SELECTION) for c in T82]
    + [(c, T71_SELECTION) for c in T71]
    + [(c, T811_SELECTION) for c in T811]
    + [(c, T72_SELECTION) for c in T72]
    + [(c, T73_SELECTION) for c in T73]
    + [(c, T83_SELECTION) for c in T83]
    + T66
    + [(c, P64_SELECTION) for c in P64]
    + [(c, T74_SELECTION) for c in T74]
    + [(c, P56_SELECTION) for c in P56]
    + [(c, T65_SELECTION) for c in T65]
    + [(c, P79_SELECTION) for c in P79]
    + T67
    + [(c, T78_SELECTION) for c in T78]
    + T68
    + [(c, T75_SELECTION) for c in T75]
    + [(c, T85_SELECTION) for c in T85]
    + [(c, T88_SELECTION) for c in T88]
    + [(c, T79_SELECTION) for c in T79]
    + [(c, T89_SELECTION) for c in T89]
    + [(c, P152_SELECTION) for c in P152]
    + [(c, T86_SELECTION) for c in T86]
    + [(c, T69_SELECTION) for c in T69]
    + [(c, T76_SELECTION) for c in T76]
    + [(c, P740_SELECTION) for c in P740]
    + [(c, T84_SELECTION) for c in T84]
    + [(c, T77_SELECTION) for c in T77]
    + [(c, T810_SELECTION) for c in T810]
    + [(c, T711_SELECTION) for c in T711]
    + [(c, T94_SELECTION) for c in T94]
    + [(c, T91_SELECTION) for c in T91]
    + [(c, P592_SELECTION) for c in P592]
    + [(c, T712_SELECTION) for c in T712]
    + [(c, T98_SELECTION) for c in T98]
    + [(c, P680_SELECTION) for c in P680]
    + [(c, P49_SELECTION) for c in P49]
    + [(c, T92_SELECTION) for c in T92]
    + [(c, P61_SELECTION) for c in P61]
    + [(c, P80_SELECTION) for c in P80]
    + [(c, T95_SELECTION) for c in T95]
    + [(c, T95_SEED_SELECTION) for c in T95_SEED]
    + [(c, T713_SELECTION) for c in T713]
    + [(c, T99_SELECTION) for c in T99]
    + [(c, T911_SELECTION) for c in T911]
    + [(c, T910_SELECTION) for c in T910]
)

# The fifty-connection fixture's own message when Postgres refuses a connection.
REFUSED_CONNECTIONS = "connections ("


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked() -> dict[str, str]:
    """Every file under api/ but caches and the virtualenv, infra/gce/ (T-4.4's
    case breaks its compose.yml, P-49), the landing guard's scripts and `migrate-with-url`
    (T-4.8 breaks it), by SHA-256, keyed by
    their path from api/."""
    skip = {".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    files = {
        str(path.relative_to(API)): sha(path)
        for path in API.rglob("*")
        if path.is_file() and not skip & set(path.relative_to(API).parts)
    }
    for path in (API.parent / "infra" / "gce").iterdir():
        if path.is_file():
            files[f"../infra/gce/{path.name}"] = sha(path)
    for name in (
        "push-gate",
        "mark-checked",
        "require-main-checkout",
        "migrate-with-url",
    ):
        files[f"../scripts/{name}"] = sha(API.parent / "scripts" / name)
    files["../Makefile"] = sha(API.parent / "Makefile")
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
