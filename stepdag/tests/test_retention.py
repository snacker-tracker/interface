"""Retention: how many of an asset's materializations are kept after each run, run through `run`."""

from pathlib import Path

from stepdag import Definitions, RunContext, asset, run
from stepdag.json_io import DirectoryStore, RunJson


def kept(root: Path, asset_name: str) -> list[str]:
    return sorted(path.stem for path in (root / "runs" / asset_name).glob("*.json"))


def test_an_asset_that_declares_no_retention_keeps_only_its_latest_materialization(
    tmp_path: Path,
) -> None:
    @asset(io_manager="run_json")
    def scan(*, context: RunContext) -> str:
        return context.run_id

    io = {"run_json": RunJson(DirectoryStore(tmp_path))}
    defs = Definitions([scan])

    run_ids = [run(defs, io).pointers["scan"].metadata["run_id"] for _ in range(3)]

    assert kept(tmp_path, "scan") == [run_ids[-1]]


def test_keep_n_retains_the_newest_n_materializations_and_removes_older_ones(
    tmp_path: Path,
) -> None:
    @asset(io_manager="run_json", retention=2)
    def scan(*, context: RunContext) -> str:
        return context.run_id

    io = {"run_json": RunJson(DirectoryStore(tmp_path))}
    defs = Definitions([scan])

    run_ids = [run(defs, io).pointers["scan"].metadata["run_id"] for _ in range(4)]

    assert kept(tmp_path, "scan") == sorted(run_ids[-2:])


def test_lineage_survives_retention(tmp_path: Path) -> None:
    @asset(io_manager="run_json", retention=2)
    def scan(*, context: RunContext) -> str:
        return context.run_id

    io = {"run_json": RunJson(DirectoryStore(tmp_path))}
    defs = Definitions([scan])

    run_ids = [run(defs, io).pointers["scan"].metadata["run_id"] for _ in range(4)]

    assert [p.metadata["run_id"] for p in io["run_json"].lineage("scan")] == run_ids
