"""Shared test setup."""

import pytest
from stepdag import version


@pytest.fixture(autouse=True)
def fixed_code_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs never read the real git state: the code version is "test-version" unless a test injects its own."""
    monkeypatch.setattr(version, "code_version", lambda: "test-version")
