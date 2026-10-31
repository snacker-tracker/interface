"""`openfoodfacts_copy`, run by the local executor against a local stand-in for Hugging Face."""

from pathlib import Path
from typing import Any

import pytest

from snacker.graph.definitions import defs
from stepdag import run
from stepdag.assets import Bindings
from graph.food_parquet import food, write_food


@pytest.fixture
def io(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Bindings:
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))
    return defs.bindings("local")


def copy_of(io: Bindings, result: Any) -> dict[str, Any]:
    pointer = result.pointers["openfoodfacts_copy"]
    description: dict[str, Any] = io[pointer.io_manager].load(pointer)
    return description


def copied_file(description: dict[str, Any]) -> Path:
    return Path(description["uri"].removeprefix("file://"))


def test_a_first_run_copies_the_file_to_a_key_named_after_its_revision(io: Bindings, openfoodfacts: Path) -> None:
    description = copy_of(io, run(defs, io))

    assert description["revision"]
    assert f"/openfoodfacts/{description['revision']}/food.parquet" in description["uri"]
    assert copied_file(description).read_bytes() == openfoodfacts.read_bytes()
    assert description["bytes"] == openfoodfacts.stat().st_size
    assert description["copied_at"]


def test_a_run_without_download_skips_the_copy(io: Bindings, openfoodfacts: Path) -> None:
    first = run(defs, io)
    write_food(openfoodfacts, [food("2")])  # A newer revision exists, but nobody asked for it.

    second = run(defs, io)

    assert "openfoodfacts_copy" in second.skipped
    assert copy_of(io, second) == copy_of(io, first)


def test_download_with_the_same_revision_skips(io: Bindings) -> None:
    run(defs, io)

    result = run(defs, io, config={"download": True})

    assert "openfoodfacts_copy" in result.skipped


def test_download_with_a_new_revision_copies_to_a_new_key(io: Bindings, openfoodfacts: Path) -> None:
    first = copy_of(io, run(defs, io))
    write_food(openfoodfacts, [food("2", names=[("main", "Two")])])

    second = copy_of(io, run(defs, io, config={"download": True}))

    assert second["revision"] != first["revision"]
    assert second["uri"] != first["uri"]
    assert copied_file(second).read_bytes() == openfoodfacts.read_bytes()
    assert copied_file(first).exists()  # Earlier copies stay until the lifecycle rule expires them.


def test_a_forced_run_copies_again(io: Bindings) -> None:
    first = copy_of(io, run(defs, io))

    result = run(defs, io, select=["openfoodfacts_copy"], force=True)

    assert "openfoodfacts_copy" in result.computed
    assert copy_of(io, result)["copied_at"] >= first["copied_at"]


def test_a_copy_that_fails_partway_leaves_no_file(io: Bindings, openfoodfacts: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from snacker import openfoodfacts as source_module

    class Broken:
        def __init__(self, path: Path) -> None:
            self.handle = path.open("rb")
            self.reads = 0

        def read(self, size: int = -1) -> bytes:
            self.reads += 1
            if self.reads > 1:
                raise ConnectionResetError("the CDN went away")
            return self.handle.read(4)

        def close(self) -> None:
            self.handle.close()

    monkeypatch.setattr(source_module.LocalFile, "open", lambda self: Broken(self.path))

    with pytest.raises(ConnectionResetError):
        run(defs, io)

    assert not list((openfoodfacts.parent.parent / "files").rglob("food.parquet"))


def test_a_copy_that_has_expired_is_copied_again(io: Bindings) -> None:
    first = copy_of(io, run(defs, io))
    copied_file(first).unlink()  # As the bucket's lifecycle rule does to copies older than 14 days.

    result = run(defs, io)

    assert "openfoodfacts_copy" in result.computed
    assert copied_file(copy_of(io, result)).exists()
