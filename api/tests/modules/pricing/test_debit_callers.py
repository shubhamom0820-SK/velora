"""Only `pricing.service.charge` calls `wallet.service.debit()` (T-5.2), so no
literal price can reach a debit: every paid action is priced from its row.
Gift sending (T-8.9, priced from `gifts`) joins the list when it is built, and
not before: an entry naming code that doesn't exist fails here too.

An allowlist of (file, function), never a list of who may not: anything that
reaches `debit` from `app/` or `seed/` and isn't named fails. It is proved as
D-084's gate is, against a caller in a module nobody has named, written each
way a caller could reach it. A blacklist can't be tested with the names you
already know.

The scan reads source, so code that builds the name at run time
(`getattr(m, "de" + "bit")`) gets past it; review catches that, not this. It
finds `debit` however it is imported or renamed, any attribute called `debit`
on anything, `getattr(..., "debit")`, and a star import of the wallet service.
Tests aren't scanned: they prove the wallet by calling it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.infra import API_DIR

ALLOWED = {("app/modules/pricing/service.py", "charge")}

WALLET_SERVICE = "app.modules.wallet.service"


def _debit_names(tree: ast.Module, rel: str) -> set[str]:
    """Names in this module bound to the wallet's `debit` function."""
    names = {"debit"} if rel == "app/modules/wallet/service.py" else set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        local = rel.startswith("app/modules/wallet/") and node.level == 1
        if module == WALLET_SERVICE or (local and module == "service"):
            for alias in node.names:
                if alias.name == "*":
                    names.add("debit")
                elif alias.name == "debit":
                    names.add(alias.asname or alias.name)
    return names


def _reaches_debit(node: ast.AST, names: set[str]) -> bool:
    if isinstance(node, ast.Attribute) and node.attr == "debit":
        return True
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return node.id in names
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "debit"
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


def debit_callers(base: Path, *roots: str) -> set[tuple[str, str]]:
    """(file, function) for everything under `roots` that reaches `debit`."""
    callers: set[tuple[str, str]] = set()
    for root in roots:
        for path in sorted((base / root).rglob("*.py")):
            rel = path.relative_to(base).as_posix()
            tree = ast.parse(path.read_text(), filename=rel)
            names = _debit_names(tree, rel)
            callers |= {
                (rel, scope)
                for node, scope in _walk(tree, "<module>")
                if _reaches_debit(node, names)
            }
    return callers


def test_only_charge_reaches_the_debit() -> None:
    assert debit_callers(API_DIR, "app", "seed") == ALLOWED


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
