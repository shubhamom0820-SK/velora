"""The breaking-run script (`tests/break_guards.py`) stays runnable: every
case's anchor is still in its file exactly once, every test it expects still
exists, and its parser reads node ids the way pytest prints them.

Without this, an edit to a guarded file would leave a case that can't apply,
and the claim it backed (T-5.1's thirty-five, T-5.4's six, T-4.4's thirty-seven, T-4.6's three,
the landing guard's five, T-5.2's twenty-two, P-38's eleven, T-4.8's twenty-six
(twenty-seven until T-4.12 took the photo requirement away, D-392),
T-4.11's eight, T-4.12's twenty-two, T-8.1's twenty-eight, T-8.2's eighteen, T-7.1's twenty, T-7.2's fourteen, T-7.3's twenty-six (twenty-five since T-7.9 let her voice notes through), P-64's three, T-7.4's eighteen, P-79's eight, T-8.5's ten, T-7.9's thirty-five, T-8.9's twenty-nine, P-152's five, P-740's five)
unrecheckable.
"""

from __future__ import annotations

import re

import pytest

from tests import break_guards
from tests.break_guards import CASES, failed_tests
from tests.infra import API_DIR

TEST_SOURCES = "\n".join(p.read_text() for p in (API_DIR / "tests").rglob("test_*.py"))


@pytest.mark.parametrize(
    ("case", "selection"), CASES, ids=[case["id"] for case, _ in CASES]
)
def test_each_case_can_still_apply(
    case: break_guards.Case, selection: list[str]
) -> None:
    for rel, old, new in case["edits"]:
        assert (API_DIR / rel).read_text().count(old) == 1, rel
        assert old != new
    for expected in case["expect"]:
        name = expected.split("::")[-1].split("[")[0]
        assert re.search(rf"def {name}\(", TEST_SOURCES), expected


def test_case_ids_are_unique_and_name_their_task() -> None:
    ids = [case["id"] for case, _ in CASES]
    assert len(ids) == len(set(ids))
    assert {i.split("-")[0] for i in ids} == {
        "t51",
        "t54",
        "t44",
        "t46",
        "land",
        "t52",
        "p142",
        "p143",
        "p38",
        "t45",
        "t48",
        "t411",
        "t412",
        "t81",
        "p120",
        "p210",
        "t62",
        "t63",
        "t96",
        "p47",
        "t64",
        "t82",
        "t71",
        "t811",
        "t72",
        "t73",
        "t83",
        "t66",
        "p64",
        "t74",
        "p56",
        "t65",
        "p79",
        "t67",
        "t78",
        "t68",
        "t75",
        "t85",
        "t79",
        "t89",
        "p152",
        "t86",
        "t69",
        "t76",
        "p740",
    }
    assert len([i for i in ids if i.startswith("t51-")]) == 35
    assert len([i for i in ids if i.startswith("t54-")]) == 6
    assert len([i for i in ids if i.startswith("t44-")]) == 37
    assert len([i for i in ids if i.startswith("land-")]) == 5
    assert len([i for i in ids if i.startswith("t52-")]) == 22
    assert len([i for i in ids if i.startswith("p142-")]) == 1
    assert len([i for i in ids if i.startswith("p143-")]) == 2
    assert len([i for i in ids if i.startswith("p38-")]) == 10
    assert len([i for i in ids if i.startswith("t48-")]) == 26
    assert len([i for i in ids if i.startswith("t45-")]) == 31
    assert len([i for i in ids if i.startswith("t411-")]) == 8
    assert len([i for i in ids if i.startswith("t412-")]) == 22
    assert len([i for i in ids if i.startswith("t81-")]) == 28
    assert len([i for i in ids if i.startswith("p120-")]) == 7
    assert len([i for i in ids if i.startswith("p210-")]) == 3
    assert len([i for i in ids if i.startswith("t62-")]) == 22
    assert len([i for i in ids if i.startswith("t63-")]) == 8
    assert len([i for i in ids if i.startswith("t96-")]) == 32
    assert len([i for i in ids if i.startswith("p47-")]) == 4
    assert len([i for i in ids if i.startswith("t64-")]) == 14
    assert len([i for i in ids if i.startswith("t82-")]) == 18
    assert len([i for i in ids if i.startswith("t71-")]) == 20
    assert len([i for i in ids if i.startswith("t72-")]) == 14
    assert len([i for i in ids if i.startswith("t73-")]) == 25
    assert len([i for i in ids if i.startswith("t83-")]) == 22
    assert len([i for i in ids if i.startswith("t66-")]) == 11
    assert len([i for i in ids if i.startswith("p64-")]) == 3
    assert len([i for i in ids if i.startswith("t74-")]) == 18
    assert len([i for i in ids if i.startswith("p79-")]) == 8
    assert len([i for i in ids if i.startswith("t67-")]) == 13
    assert len([i for i in ids if i.startswith("t68-")]) == 6
    assert len([i for i in ids if i.startswith("t75-")]) == 20
    assert len([i for i in ids if i.startswith("t85-")]) == 10
    assert len([i for i in ids if i.startswith("t79-")]) == 35
    assert len([i for i in ids if i.startswith("t89-")]) == 29
    assert len([i for i in ids if i.startswith("p152-")]) == 5
    assert len([i for i in ids if i.startswith("t86-")]) == 26
    assert len([i for i in ids if i.startswith("t76-")]) == 28


def test_failed_tests_reads_ids_whole() -> None:
    output = """\
FAILED tests/a.py::test_x[a ledger row] - AssertionError: no
ERROR tests/b.py::test_y[one key - two] - RuntimeError
FAILED tests/c.py::test_z
tests/d.py::test_not_a_summary_line FAILED
"""

    assert failed_tests(output) == [
        "tests/a.py::test_x[a ledger row]",
        "tests/b.py::test_y[one key - two]",
        "tests/c.py::test_z",
    ]
