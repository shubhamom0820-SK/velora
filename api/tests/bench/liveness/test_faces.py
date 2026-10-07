"""The liveness probe's faces guard (T-4.11): the NASA fixtures by default, and
any other set only from outside the repository and every worktree of it, so a
consenting volunteer's photo (P-280) never sits where a commit could take it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bench.liveness import run
from bench.liveness.run import FIXTURES, REPO, FacesRefused, faces_dir, worktrees

INSIDE = REPO / "api" / "app"  # a real directory of the repository


def porcelain(*roots: Path) -> str:
    return "".join(f"worktree {root}\nHEAD 0123abcd\ndetached\n\n" for root in roots)


def git_answers(monkeypatch: pytest.MonkeyPatch, code: int, out: str) -> None:
    monkeypatch.setattr(run, "list_worktrees", lambda: (code, out))


def test_the_fixtures_by_default() -> None:
    assert faces_dir(None, roots=[REPO]) == FIXTURES.resolve()


def test_the_fixtures_by_name() -> None:
    assert faces_dir(FIXTURES, roots=[REPO]) == FIXTURES.resolve()


def test_a_directory_outside_the_repository_is_read(tmp_path: Path) -> None:
    assert faces_dir(tmp_path, roots=[REPO]) == tmp_path.resolve()


def test_a_directory_inside_the_repository_is_refused() -> None:
    with pytest.raises(FacesRefused) as refused:
        faces_dir(INSIDE, roots=[REPO])

    assert str(refused.value).startswith(f"{INSIDE} is inside the repository ({REPO}).")


def test_a_link_into_the_repository_is_refused(tmp_path: Path) -> None:
    link = tmp_path / "faces"
    link.symlink_to(INSIDE, target_is_directory=True)

    with pytest.raises(FacesRefused, match="is inside the repository"):
        faces_dir(link, roots=[REPO])


def test_a_missing_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FacesRefused, match="is not a directory"):
        faces_dir(tmp_path / "nowhere", roots=[REPO])


def test_another_worktree_of_the_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other-worktree"
    (other / "photos").mkdir(parents=True)
    git_answers(monkeypatch, 0, porcelain(REPO, other))

    with pytest.raises(FacesRefused) as refused:
        faces_dir(other / "photos")

    assert f"is inside the repository ({other})" in str(refused.value)


def test_if_git_cant_list_the_worktrees_only_the_fixtures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git_answers(monkeypatch, 128, "")

    with pytest.raises(FacesRefused, match="git couldn't list"):
        faces_dir(tmp_path)
    assert faces_dir(None) == FIXTURES.resolve()


def test_the_real_repository_is_asked() -> None:
    with pytest.raises(FacesRefused, match="is inside the repository"):
        faces_dir(INSIDE)


def test_worktrees_reads_gits_porcelain() -> None:
    assert worktrees(porcelain(Path("/a"), Path("/b c"))) == [Path("/a"), Path("/b c")]


def test_the_command_refuses_before_starting_anything(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def never(*args: Any, **kwargs: Any) -> int:
        raise AssertionError("a container was started")

    monkeypatch.setattr(run, "execute", never)

    assert run.main(["baseline", "--faces", str(INSIDE)]) == 2
    assert capsys.readouterr().err.startswith(f"run: refused: {INSIDE} is inside")
