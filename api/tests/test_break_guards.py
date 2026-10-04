"""The breaking-run script (`tests/break_guards.py`) stays runnable: every
case's anchor is still in its file exactly once, every test it expects still
exists, and its parser reads node ids the way pytest prints them.

Without this, an edit to a guarded file would leave a case that can't apply,
and the claim it backed (T-5.1's thirty-five, T-5.4's six) unrecheckable.
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
    assert {i.split("-")[0] for i in ids} == {"t51", "t54"}
    assert len([i for i in ids if i.startswith("t51-")]) == 35
    assert len([i for i in ids if i.startswith("t54-")]) == 6


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
