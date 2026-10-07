"""Run T-4.11's probe as Fly runs the worker: one CPU, 1 GB, no swap.

    uv run python -m bench.liveness.run all                      # from api/
    uv run python -m bench.liveness.run minifas_cv --runs 3
    uv run python -m bench.liveness.run baseline --at-once 4 --allow-swap
    uv run python -m bench.liveness.run same_weights

Each run is a fresh container (`docker run --rm`), its whole output kept in
`out/t-4.11-probe/logs/`, git-ignored. `all` is every run the record cites, as
5 October 2026 made them; it prints each one's peak and exit, and exits 1 if
any run ended in a way it wasn't expected to. Needs the two images and the
weights the package docstring says how to make.

**The faces guard.** `--faces` is the NASA fixtures by default. Any other set
must come from outside the repository: a directory inside it, or inside any
worktree of it, is refused, a link judged by where it leads. A consenting
volunteer's photo (P-280) then has no reason ever to sit in the tree, where
one `git add` would commit it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from bench.liveness.weights import WEIGHTS_DIR, problems

REPO: Final = Path(__file__).resolve().parents[3]
BENCH: Final = REPO / "api" / "bench"
FIXTURES: Final = REPO / "api" / "tests" / "fixtures" / "faces"
LOGS: Final = REPO / "out" / "t-4.11-probe" / "logs"
IMAGE: Final = "velora-api:bench"
TOOLS_IMAGE: Final = "velora-api:bench-tools"
NEEDS_TOOLS: Final = {"minifas_ort", "minifas_torch", "same_weights"}
KILLED: Final = 137  # SIGKILL: the kernel's out-of-memory killer, in a container


class FacesRefused(Exception):
    """A faces directory the probe won't read."""


def worktrees(porcelain: str) -> list[Path]:
    """The roots `git worktree list --porcelain` names."""
    return [
        Path(line.removeprefix("worktree "))
        for line in porcelain.splitlines()
        if line.startswith("worktree ")
    ]


def list_worktrees() -> tuple[int, str]:
    """git's exit code and its porcelain list of this repository's worktrees."""
    listed = subprocess.run(  # its exit code is returned, and read by the caller
        ["git", "-C", str(REPO), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return listed.returncode, listed.stdout


def repository_roots() -> list[Path]:
    """This checkout and every worktree of its repository. Fails closed: if
    git can't say, the caller refuses every set but the fixtures."""
    code, porcelain = list_worktrees()
    if code != 0:
        raise FacesRefused(
            "git couldn't list this repository's worktrees, so a faces directory "
            "can't be shown to be outside them. Only the fixtures can be read."
        )
    return [REPO, *worktrees(porcelain)]


def faces_dir(chosen: Path | None, roots: Iterable[Path] | None = None) -> Path:
    """The faces directory to read: the fixtures unless another is chosen, and
    another only from outside the repository and its worktrees."""
    if chosen is None or chosen.resolve() == FIXTURES.resolve():
        return FIXTURES.resolve()
    target = chosen.resolve()
    for root in repository_roots() if roots is None else roots:
        if target.is_relative_to(root.resolve()):
            raise FacesRefused(
                f"{chosen} is inside the repository ({root}). Faces other than the "
                "NASA fixtures are read only from outside it, so no one's photo "
                "sits where a commit could take it (P-280)."
            )
    if not target.is_dir():
        raise FacesRefused(f"{chosen} is not a directory.")
    return target


@dataclass(frozen=True)
class Run:
    name: str
    module: str  # probe or same_weights
    args: tuple[str, ...]
    image: str
    allow_swap: bool = False
    expect_killed: bool = False


def every_run(runs: int) -> list[Run]:
    """The runs T-4.11's record cites, as 5 October 2026 made them."""
    planned = []
    for route in ("baseline", "minifas_cv"):
        for n in range(1, runs + 1):
            planned.append(Run(f"{route}-{n}", "probe", (route,), IMAGE))
    for route in ("baseline", "minifas_ort", "minifas_torch"):
        for n in range(1, runs + 1):
            name = f"{route}-tools-{n}" if route == "baseline" else f"{route}-{n}"
            planned.append(Run(name, "probe", (route,), TOOLS_IMAGE))
    for route in ("baseline", "minifas_cv"):
        planned.append(
            Run(
                f"{route}-at-once-4-swap",
                "probe",
                (route, "--at-once", "4"),
                IMAGE,
                allow_swap=True,
            )
        )
    planned.append(
        Run(
            "baseline-at-once-4",
            "probe",
            ("baseline", "--at-once", "4"),
            IMAGE,
            expect_killed=True,
        )
    )
    planned.append(Run("same_weights", "same_weights", (), TOOLS_IMAGE))
    return planned


def command(run: Run, faces: Path, weights: Path) -> list[str]:
    swap = [] if run.allow_swap else ["--memory-swap=1g"]
    return [
        "docker",
        "run",
        "--rm",
        "--cpuset-cpus=0",
        "--memory=1g",
        *swap,
        "-e",
        "PYTHONPATH=/app",
        "-v",
        f"{BENCH}:/app/bench:ro",
        "-v",
        f"{faces}:/faces:ro",
        "-v",
        f"{weights}:/weights:ro",
        "--entrypoint",
        "python",
        run.image,
        "-m",
        f"bench.liveness.{run.module}",
        *run.args,
    ]


def summary(output: str) -> str:
    for line in reversed(output.splitlines()):
        if line.startswith("RESULT {"):
            found = json.loads(line.removeprefix("RESULT "))
            return f"peak {found['peak_mb']} MB"
        if line.startswith("RESULT "):
            return f"largest difference {line.removeprefix('RESULT ')}"
    return "no result"


def execute(planned: Sequence[Run], faces: Path, weights: Path) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    unexpected = 0
    for run in planned:
        done = subprocess.run(  # its exit code is read below
            command(run, faces, weights), capture_output=True, text=True, check=False
        )
        output = done.stdout + done.stderr
        (LOGS / f"{run.name}.log").write_text(output)
        expected = KILLED if run.expect_killed else 0
        verdict = "as expected" if done.returncode == expected else "UNEXPECTED"
        unexpected += done.returncode != expected
        sys.stdout.write(
            f"{run.name:28} exit {done.returncode:3} ({verdict}) {summary(output)}\n"
        )
        sys.stdout.flush()
    return 1 if unexpected else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "what",
        choices=(
            "all",
            "same_weights",
            "baseline",
            *sorted(NEEDS_TOOLS - {"same_weights"}),
            "minifas_cv",
        ),
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--at-once", type=int, default=1)
    parser.add_argument("--allow-swap", action="store_true")
    parser.add_argument("--faces", type=Path)
    parser.add_argument("--weights", type=Path, default=WEIGHTS_DIR)
    args = parser.parse_args(argv)

    try:
        faces = faces_dir(args.faces)
    except FacesRefused as refused:
        sys.stderr.write(f"run: refused: {refused}\n")
        return 2
    wrong = problems(args.weights)
    if wrong:
        sys.stderr.write(
            "run: the weights aren't ready: "
            + "; ".join(wrong)
            + ". Fetch them with `uv run python -m bench.liveness.weights`.\n"
        )
        return 2

    if args.what == "all":
        planned = every_run(args.runs)
    elif args.what == "same_weights":
        planned = [Run("same_weights", "same_weights", (), TOOLS_IMAGE)]
    else:
        image = TOOLS_IMAGE if args.what in NEEDS_TOOLS else IMAGE
        extra = ("--at-once", str(args.at_once)) if args.at_once > 1 else ()
        planned = [
            Run(
                f"{args.what}-{n}",
                "probe",
                (args.what, *extra),
                image,
                allow_swap=args.allow_swap,
            )
            for n in range(1, args.runs + 1)
        ]
    return execute(planned, faces, args.weights.resolve())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
