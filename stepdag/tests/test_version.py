"""code_version(): the version a materialization is stamped with, for the skip rule (ADR 0006)."""

import subprocess
from pathlib import Path

import pytest
from stepdag.version import code_version


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git checkout with one commit, as the working directory."""
    monkeypatch.delenv("STEPDAG_CODE_VERSION", raising=False)
    git(tmp_path, "init", "-q")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "init")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_the_environment_variable_is_the_version(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STEPDAG_CODE_VERSION", "sha256:abc")

    assert code_version() == "sha256:abc"


def test_the_environment_variable_wins_over_a_dirty_tree(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "scratch.txt").write_text("x")
    monkeypatch.setenv("STEPDAG_CODE_VERSION", "sha256:abc")

    assert code_version() == "sha256:abc"


def test_an_empty_environment_variable_is_no_version(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STEPDAG_CODE_VERSION", "")

    assert code_version() == git(repo, "rev-parse", "HEAD")


def test_a_clean_checkout_is_its_head_commit(repo: Path) -> None:
    assert code_version() == git(repo, "rev-parse", "HEAD")


def test_a_dirty_tree_with_an_untracked_file_has_no_version(repo: Path) -> None:
    (repo / "scratch.txt").write_text("x")

    assert code_version() is None


def test_a_dirty_tree_with_a_modified_file_has_no_version(repo: Path) -> None:
    (repo / "tracked.txt").write_text("one")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-q", "-m", "add")
    (repo / "tracked.txt").write_text("two")

    assert code_version() is None


def test_outside_a_checkout_there_is_no_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STEPDAG_CODE_VERSION", raising=False)
    monkeypatch.chdir(tmp_path)

    assert code_version() is None


def test_without_git_there_is_no_version(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(repo))

    assert code_version() is None
