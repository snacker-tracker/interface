"""Fixtures shared by the build and contract tests."""

from pathlib import Path

import pytest


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    path = tmp_path / "raw"
    (path / "scans").mkdir(parents=True)
    return path


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "out"
