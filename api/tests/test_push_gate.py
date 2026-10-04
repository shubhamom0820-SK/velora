"""The landing guard (scripts/push-gate, scripts/mark-checked; 4 October 2026):
its own tests, scripts/push-gate-test, run with the suite, so `make test` and
CI fail when the guard breaks, and tests/break_guards.py can break it."""

from __future__ import annotations

import subprocess

from tests.infra import API_DIR

TESTS = API_DIR.parent / "scripts" / "push-gate-test"


def test_the_landing_guard_refuses_what_it_should() -> None:
    proc = subprocess.run(  # its exit code is read below
        [str(TESTS)], capture_output=True, text=True, timeout=120, check=False
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "push-gate-test: 16 passed, 0 failed" in proc.stdout
