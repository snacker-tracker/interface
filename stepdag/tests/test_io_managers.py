"""The IO manager contract, run against every binding of every JSON IO manager."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from stepdag import RunContext
from stepdag.json_io import DirectoryStore, MemoryStore, RunJson, S3Store, Store
from tests.fakes import s3_bucket


def context(run_id: str, asset: str = "a") -> RunContext:
    return RunContext(run_id=run_id, started_at="2026-10-30T00:00:00+00:00", asset=asset, config={}, asset_config={}, force=False)


@pytest.fixture(params=["memory", "directory", "s3"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Store]:
    if request.param == "s3":
        with s3_bucket("values") as client:
            yield S3Store(client, "values", "graph/")
        return
    stores: dict[str, Callable[[], Store]] = {
        "memory": MemoryStore,
        "directory": lambda: DirectoryStore(tmp_path),
    }
    yield stores[request.param]()


def test_a_stored_value_loads_back_from_its_pointer(store: Store) -> None:
    io = RunJson(store)
    value: Any = {"text": "Hello, world!", "words": [1, 2]}

    pointer = io.store(value, "a", context("r1"))

    assert pointer.asset == "a"
    assert pointer.io_manager == "run_json"
    assert io.load(pointer) == value


def test_latest_is_none_before_anything_is_stored(store: Store) -> None:
    assert RunJson(store).latest("a") is None


def test_run_json_keeps_every_run_and_latest_is_the_last_stored(store: Store) -> None:
    io = RunJson(store)
    first = io.store(1, "a", context("r1"))
    second = io.store(2, "a", context("r0"))  # Run IDs aren't ordered; storage order is.
    io.store(3, "b", context("r2", asset="b"))

    assert io.latest("a") == second
    assert io.load(first) == 1
    assert io.load(second) == 2


def test_a_pointer_survives_a_json_round_trip(store: Store) -> None:
    from stepdag import Pointer

    io = RunJson(store)
    pointer = io.store("x", "a", context("r1"))

    assert io.load(Pointer.from_json(pointer.to_json())) == "x"


def test_fixed_json_keeps_one_materialization_per_asset(store: Store) -> None:
    from stepdag.json_io import FixedJson

    io = FixedJson(store)
    first = io.store(1, "a", context("r1"))
    second = io.store(2, "a", context("r2"))

    assert first.uri == second.uri
    assert io.latest("a") == second
    assert io.load(second) == 2
    assert io.latest("b") is None
