"""Every test gets an OpenFoodFacts file and somewhere to copy it, so graphs with the copy asset run,
and a Snacker archive for `products` to read."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from graph.food_parquet import food, write_archive, write_food


@pytest.fixture(autouse=True)
def openfoodfacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    source = write_food(tmp_path / "openfoodfacts" / "food.parquet", [food("1", names=[("main", "One")])])
    monkeypatch.setenv("SCANS_OPENFOODFACTS", str(source))
    monkeypatch.setenv("SCANS_FILES", str(tmp_path / "files"))
    monkeypatch.setenv("SCANS_SITE", str(tmp_path / "site"))
    yield source


@pytest.fixture(autouse=True)
def archive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    path = write_archive(tmp_path / "archive" / "snacker-archive.csv", [("2", "Two")])
    monkeypatch.setenv("SCANS_ARCHIVE", str(path))
    yield path
