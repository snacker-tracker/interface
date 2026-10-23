"""Tests at the CLI's code-version seam: the git commit stamped on a cache it writes."""

import subprocess
from pathlib import Path

from snacker.cli import code_version


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


def committed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "scans.py").write_text("v1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "v1")
    return repo


def test_a_clean_tree_is_its_commit(tmp_path: Path) -> None:
    repo = committed_repo(tmp_path)

    assert code_version(repo) == git(repo, "rev-parse", "HEAD")


def test_a_dirty_tree_has_no_version(tmp_path: Path) -> None:
    repo = committed_repo(tmp_path)
    (repo / "scans.py").write_text("v2, uncommitted\n")

    assert code_version(repo) is None


def test_outside_a_git_repository_there_is_no_version(tmp_path: Path) -> None:
    assert code_version(tmp_path) is None
