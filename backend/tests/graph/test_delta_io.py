"""The Delta IO manager's contract, against a local directory."""

from pathlib import Path

import polars as pl

from snacker.graph.delta_io import DeltaIO, Merge
from stepdag import RunContext


def context(run_id: str, force: bool = False) -> RunContext:
    return RunContext(run_id=run_id, started_at="2026-10-30T00:00:00+00:00", asset="t", config={}, asset_config={}, force=force)


def test_a_stored_frame_loads_back_from_its_pointer(tmp_path: Path) -> None:
    io = DeltaIO(str(tmp_path))
    frame = pl.DataFrame({"code": ["a", "b"], "n": [1, 2]})

    pointer = io.store(frame, "t", context("r1"))

    assert pointer.io_manager == "delta"
    assert pointer.metadata["version"] == 0
    assert pointer.metadata["run_id"] == "r1"
    assert io.load(pointer).collect().equals(frame)


def test_latest_is_none_until_the_table_exists(tmp_path: Path) -> None:
    assert DeltaIO(str(tmp_path)).latest("t") is None


def test_latest_is_the_newest_version(tmp_path: Path) -> None:
    io = DeltaIO(str(tmp_path))
    io.store(pl.DataFrame({"n": [1]}), "t", context("r1"))
    second = io.store(pl.DataFrame({"n": [2]}), "t", context("r2"))

    latest = io.latest("t")

    assert latest is not None
    assert latest.metadata["version"] == second.metadata["version"] == 1
    assert io.load(latest).collect()["n"].to_list() == [2]


def test_a_pointer_still_loads_its_own_version_after_a_later_write(tmp_path: Path) -> None:
    io = DeltaIO(str(tmp_path))
    first = io.store(pl.DataFrame({"n": [1]}), "t", context("r1"))
    io.store(pl.DataFrame({"n": [2]}), "t", context("r2"))

    assert io.load(first).collect()["n"].to_list() == [1]


def test_merge_mode_inserts_new_keys_and_updates_matched_ones_in_a_new_pinned_version(tmp_path: Path) -> None:
    io = DeltaIO(str(tmp_path), merges={"t": Merge(keys=["id"])})
    first = io.store(pl.DataFrame({"id": ["a", "b"], "n": [1, 2]}), "t", context("r1"))

    second = io.store(pl.DataFrame({"id": ["b", "c"], "n": [20, 3]}), "t", context("r2"))

    assert second.metadata["version"] == 1
    assert second.metadata["run_id"] == "r2"
    assert io.load(second).collect().sort("id").to_dicts() == [{"id": "a", "n": 1}, {"id": "b", "n": 20}, {"id": "c", "n": 3}]
    assert io.load(first).collect().sort("id").to_dicts() == [{"id": "a", "n": 1}, {"id": "b", "n": 2}]
    latest = io.latest("t")
    assert latest is not None and latest.metadata == second.metadata


def test_merge_mode_replaces_the_table_in_a_forced_run(tmp_path: Path) -> None:
    """A forced run gives the asset no `previous`, so what it returns is the whole table, not new rows."""
    io = DeltaIO(str(tmp_path), merges={"t": Merge(keys=["id"])})
    io.store(pl.DataFrame({"id": ["a", "b"], "n": [1, 2]}), "t", context("r1"))

    forced = io.store(pl.DataFrame({"id": ["b"], "n": [20]}), "t", context("r2", force=True))

    assert io.load(forced).collect().to_dicts() == [{"id": "b", "n": 20}]


def test_an_overwrite_replaces_the_tables_schema(tmp_path: Path) -> None:
    io = DeltaIO(str(tmp_path))
    io.store(pl.DataFrame({"code": ["a"], "count": [1]}), "t", context("r1"))

    pointer = io.store(pl.DataFrame({"code": ["a"], "count": [1], "name": ["Apple"]}), "t", context("r2"))

    assert io.load(pointer).collect().to_dicts() == [{"code": "a", "count": 1, "name": "Apple"}]


def test_an_enum_column_is_stored_as_text(tmp_path: Path) -> None:
    # deltalake can't write polars Enums (dictionary-encoded); Snacker's products schema has three.
    io = DeltaIO(str(tmp_path))
    frame = pl.DataFrame({"grade": ["A", None, "E"]}, schema={"grade": pl.Enum(["A", "B", "C", "D", "E"])})

    pointer = io.store(frame, "t", context("r1"))

    assert io.load(pointer).collect().equals(frame.cast({"grade": pl.String()}))


def test_a_conditional_merge_updates_a_matched_row_only_when_the_condition_holds(tmp_path: Path) -> None:
    io = DeltaIO(str(tmp_path), merges={"t": Merge(keys=["id"], update_when="s.n > t.n")})
    io.store(pl.DataFrame({"id": ["a", "b"], "n": [5, 5]}), "t", context("r1"))

    merged = io.store(pl.DataFrame({"id": ["a", "b", "c"], "n": [9, 1, 3]}), "t", context("r2"))

    assert io.load(merged).collect().sort("id").to_dicts() == [{"id": "a", "n": 9}, {"id": "b", "n": 5}, {"id": "c", "n": 3}]
