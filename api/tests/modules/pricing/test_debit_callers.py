"""Only `pricing.service.charge` and gift sending (T-8.9, priced from `gifts`)
call `wallet.service.debit()` (T-5.2), so no literal price can reach a debit:
every paid action is priced from its row. An entry naming code that doesn't
exist fails here too.

An allowlist of (file, function), never a list of who may not: anything that
reaches `debit` from `app/` or `seed/` and isn't named fails. It is proved as
D-084's gate is, against a caller in a module nobody has named, written each
way a caller could reach it. A blacklist can't be tested with the names you
already know.

The scan reads source, so code that builds the name at run time
(`getattr(m, "de" + "bit")`) gets past it. Since P-152 (D-651) `debit` itself
refuses any caller but these two when it runs, and the last cases here prove it
against exactly that caller, which the scan is shown not to see. The scan stays
as the second layer: it finds `debit` however it is imported or renamed, any
attribute called `debit` on anything, `getattr(..., "debit")`, and a star
import of the wallet service. Tests aren't scanned: they prove the wallet by
calling it, which `debit` allows them (they never ship, `.dockerignore`).

**`reverse()` the same way (T-8.2, D-520):** it takes what the balance holds
and never refuses, so a priced action reaching it would take Velas for free.
Only payments' webhook, taking back a payment whose money went back, calls it.
"""

from __future__ import annotations

import ast
import asyncio
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LedgerReason
from app.modules.wallet import service as wallet_service
from app.modules.wallet.models import LedgerEntry, Wallet
from app.modules.wallet.rules import Ref, RefType
from app.modules.wallet.service import WalletMisuse
from tests.conftest import MakeUser
from tests.infra import API_DIR

ALLOWED = {
    ("app/modules/pricing/service.py", "charge"),
    ("app/modules/gifts/service.py", "_send_in"),
}
REVERSE_ALLOWED = {("app/modules/payments/webhooks.py", "_reverse_once")}

WALLET_SERVICE = "app.modules.wallet.service"


def _debit_names(tree: ast.Module, rel: str, target: str = "debit") -> set[str]:
    """Names in this module bound to the wallet's `target` function."""
    names = {target} if rel == "app/modules/wallet/service.py" else set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        local = rel.startswith("app/modules/wallet/") and node.level == 1
        if module == WALLET_SERVICE or (local and module == "service"):
            for alias in node.names:
                if alias.name == "*":
                    names.add(target)
                elif alias.name == target:
                    names.add(alias.asname or alias.name)
    return names


def _reaches_debit(node: ast.AST, names: set[str], target: str = "debit") -> bool:
    if isinstance(node, ast.Attribute) and node.attr == target:
        return True
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return node.id in names
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == target
    )


def _walk(node: ast.AST, scope: str) -> list[tuple[ast.AST, str]]:
    """Every node, with the function (or class) it is inside."""
    found = [(node, scope)]
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            inner = child.name if scope == "<module>" else f"{scope}.{child.name}"
        else:
            inner = scope
        found += _walk(child, inner)
    return found


def debit_callers(
    base: Path, *roots: str, target: str = "debit"
) -> set[tuple[str, str]]:
    """(file, function) for everything under `roots` that reaches `target`."""
    callers: set[tuple[str, str]] = set()
    for root in roots:
        for path in sorted((base / root).rglob("*.py")):
            rel = path.relative_to(base).as_posix()
            tree = ast.parse(path.read_text(), filename=rel)
            names = _debit_names(tree, rel, target)
            callers |= {
                (rel, scope)
                for node, scope in _walk(tree, "<module>")
                if _reaches_debit(node, names, target)
            }
    return callers


def test_only_charge_reaches_the_debit() -> None:
    assert debit_callers(API_DIR, "app", "seed") == ALLOWED


def test_only_the_webhooks_reversal_reaches_reverse() -> None:
    assert debit_callers(API_DIR, "app", "seed", target="reverse") == REVERSE_ALLOWED


SOMEWHERE = "app/modules/never_named_2031/service.py"
# Each way a caller could reach the debit, in a module nobody has listed.
WAYS = {
    "the module, renamed": """
from app.modules.wallet import service as wallet_service

async def buy(session, user):
    await wallet_service.debit(session, user.id, 5, "thread_open")
""",
    "the function": """
from app.modules.wallet.service import debit

async def buy(session, user):
    await debit(session, user.id, 5, "thread_open")
""",
    "the function, renamed": """
from app.modules.wallet.service import debit as take

async def buy(session, user):
    await take(session, user.id, 5, "thread_open")
""",
    "the full path": """
import app.modules.wallet.service

async def buy(session, user):
    await app.modules.wallet.service.debit(session, user.id, 5, "thread_open")
""",
    "getattr": """
from app.modules.wallet import service

async def buy(session, user):
    await getattr(service, "debit")(session, user.id, 5, "thread_open")
""",
    "a star import": """
from app.modules.wallet.service import *

async def buy(session, user):
    await debit(session, user.id, 5, "thread_open")
""",
    "a method": """
from app.modules.wallet import service

class Shop:
    async def buy(self, session, user):
        await service.debit(session, user.id, 5, "thread_open")
""",
}
SCOPES = {"a method": "Shop.buy"}


@pytest.mark.parametrize("way", WAYS)
def test_a_caller_nobody_has_named_is_found(tmp_path: Path, way: str) -> None:
    (tmp_path / SOMEWHERE).parent.mkdir(parents=True)
    (tmp_path / SOMEWHERE).write_text(WAYS[way])

    found = debit_callers(tmp_path, "app")

    assert found == {(SOMEWHERE, SCOPES.get(way, "buy"))}
    assert not found <= ALLOWED


def test_the_allowlist_names_a_function_not_a_file(tmp_path: Path) -> None:
    """A second function beside `charge` in pricing's own service is as
    unnamed as anything else."""
    path = tmp_path / "app/modules/pricing/service.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        """
from app.modules.wallet import service as wallet_service

async def charge(session, user):
    await wallet_service.debit(session, user.id, 5, "thread_open")

async def charge_twice(session, user):
    await wallet_service.debit(session, user.id, 10, "thread_open")
"""
    )

    found = debit_callers(tmp_path, "app")

    assert found - ALLOWED == {("app/modules/pricing/service.py", "charge_twice")}


def test_a_value_passed_around_counts_as_a_caller(tmp_path: Path) -> None:
    """Handing `debit` to something else is reaching it, at module level too."""
    path = tmp_path / SOMEWHERE
    path.parent.mkdir(parents=True)
    path.write_text(
        """
from app.modules.wallet.service import debit

PAY = {"thread_open": debit}
"""
    )

    assert debit_callers(tmp_path, "app") == {(SOMEWHERE, "<module>")}


@pytest.mark.parametrize("way", WAYS)
def test_a_reverse_caller_nobody_has_named_is_found(tmp_path: Path, way: str) -> None:
    """Every way a caller could reach `debit`, aimed at `reverse` instead."""
    (tmp_path / SOMEWHERE).parent.mkdir(parents=True)
    (tmp_path / SOMEWHERE).write_text(WAYS[way].replace("debit", "reverse"))

    found = debit_callers(tmp_path, "app", target="reverse")

    assert found == {(SOMEWHERE, SCOPES.get(way, "buy"))}
    assert not found <= REVERSE_ALLOWED


# --- At run time (P-152, D-651) ------------------------------------------------------


def _module_of(path: str) -> str:
    return path.removesuffix(".py").replace("/", ".")


def test_the_run_time_list_is_the_scans() -> None:
    """One list in two places: the scan's files and `debit`'s modules name the
    same functions, so neither can grow alone."""
    assert {
        (_module_of(path), scope) for path, scope in ALLOWED
    } == wallet_service.DEBIT_CALLERS


# Reaches the debit by a name built at run time, from a module nobody named.
BUILT_AT_RUN_TIME = """
from app.core.enums import LedgerReason
from app.modules.wallet import service

async def buy(session, user_id, ref):
    pay = getattr(service, "de" + "bit")
    return await pay(session, user_id, 5, LedgerReason.THREAD_OPEN, ref=ref)
"""


def _loaded(name: str, source: str) -> ModuleType:
    """`source` run as the module `name`, as if it lived in `app/`."""
    module = ModuleType(name)
    # The test's own source, never input: the point is a module the scan never read.
    exec(compile(source, f"<{name}>", "exec"), module.__dict__)  # noqa: S102
    return module


async def _moved(db: AsyncSession, user_id: uuid.UUID) -> tuple[int, int]:
    entries = await db.scalar(
        select(func.count())
        .select_from(LedgerEntry)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant")
    )
    balance = await db.scalar(select(Wallet.balance).where(Wallet.user_id == user_id))
    return int(entries or 0), int(balance or 0)


async def test_a_debit_by_a_name_built_at_run_time_is_refused(
    db: AsyncSession, make_user: MakeUser, tmp_path: Path
) -> None:
    """The case P-152 names: the scan can't see this caller, and `debit`
    refuses it anyway, having written nothing."""
    (tmp_path / SOMEWHERE).parent.mkdir(parents=True)
    (tmp_path / SOMEWHERE).write_text(BUILT_AT_RUN_TIME)
    assert debit_callers(tmp_path, "app") == set()  # the scan's blind spot

    man, _ = await make_user(credits=10)
    module = _loaded(_module_of(SOMEWHERE), BUILT_AT_RUN_TIME)
    with pytest.raises(WalletMisuse, match=r"P-152"):
        await module.buy(db, man.id, Ref(RefType.THREAD, uuid.uuid4()))

    assert await _moved(db, man.id) == (0, 10)


@pytest.mark.parametrize(
    ("module", "function"),
    [
        # A listed function's name, in a module nobody listed.
        ("app.modules.never_named_2031.service", "charge"),
        # A listed module, with a function nobody listed.
        ("app.modules.pricing.service", "charge_twice"),
        ("app.modules.gifts.service", "send_gift"),
        # Only the package `tests` is test code, not a name starting with it.
        ("testsuite_2031.service", "buy"),
    ],
)
async def test_the_list_names_a_function_in_its_module(
    db: AsyncSession, make_user: MakeUser, module: str, function: str
) -> None:
    man, _ = await make_user(credits=10)
    source = f"""
from app.core.enums import LedgerReason
from app.modules.wallet import service

async def {function}(session, user_id, ref):
    return await service.debit(session, user_id, 5, LedgerReason.THREAD_OPEN, ref=ref)
"""
    loaded = _loaded(module, source)
    with pytest.raises(WalletMisuse, match=r"P-152"):
        await getattr(loaded, function)(db, man.id, Ref(RefType.THREAD, uuid.uuid4()))

    assert await _moved(db, man.id) == (0, 10)


async def test_a_debit_with_no_caller_of_its_own_is_refused(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Started as a task, `debit` is awaited by the event loop: a caller
    nobody named, so refused, even from a test."""
    man, _ = await make_user(credits=10)
    ref = Ref(RefType.THREAD, uuid.uuid4())
    task: asyncio.Task[Any] = asyncio.create_task(
        wallet_service.debit(db, man.id, 5, LedgerReason.THREAD_OPEN, ref=ref)
    )
    with pytest.raises(WalletMisuse, match=r"P-152"):
        await task

    assert await _moved(db, man.id) == (0, 10)


async def test_a_listed_caller_passes(db: AsyncSession, make_user: MakeUser) -> None:
    """The check refuses by who calls, nothing else: the same source, loaded
    as pricing's `charge`, debits."""
    man, _ = await make_user(credits=10)
    source = """
from app.core.enums import LedgerReason
from app.modules.wallet import service

async def charge(session, user_id, ref):
    return await service.debit(session, user_id, 5, LedgerReason.THREAD_OPEN, ref=ref)
"""
    loaded = _loaded("app.modules.pricing.service", source)
    await loaded.charge(db, man.id, Ref(RefType.THREAD, uuid.uuid4()))

    assert await _moved(db, man.id) == (1, 5)
