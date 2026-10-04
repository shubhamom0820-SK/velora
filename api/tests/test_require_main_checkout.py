"""`make hooks` only from the clone's main checkout (P-143): its own tests,
scripts/require-main-checkout-test, run with the suite, so `make test` and CI
fail when the refusal breaks; and make itself confirms the check is the first
thing the target runs."""

from __future__ import annotations

import os
import subprocess

from tests.infra import API_DIR

REPO = API_DIR.parent
TESTS = REPO / "scripts" / "require-main-checkout-test"


def test_make_hooks_is_refused_outside_the_main_checkout() -> None:
    proc = subprocess.run(  # its exit code is read below
        [str(TESTS)], capture_output=True, text=True, timeout=60, check=False
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "require-main-checkout-test: 5 passed, 0 failed" in proc.stdout


def test_the_check_is_the_first_thing_make_hooks_runs() -> None:
    """Read from make's own dry run, never the Makefile's text: comment lines
    aside, the first command is the check. Run as a make of its own, not a
    sub-make of `make test-api`: GNU make 4 (CI's) prints "Entering directory"
    in a sub-make, before any command."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"MAKEFLAGS", "MAKELEVEL", "MFLAGS"}
    }
    proc = subprocess.run(  # its exit code is read below
        ["make", "--no-print-directory", "-n", "hooks"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    commands = [
        line for line in proc.stdout.splitlines() if line and not line.startswith("#")
    ]

    assert proc.returncode == 0, proc.stderr
    assert commands[0] == "scripts/require-main-checkout"
