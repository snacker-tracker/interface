"""Retention: how many of an asset's materializations are kept after each run, run through `run`."""

from datetime import UTC, datetime
from pathlib import Path

from stepdag import Definitions, RunContext, asset, run
from stepdag.json_io import DirectoryStore, MemoryStore, RunJson


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


class CountingStore(MemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def get(self, key: str) -> bytes | None:
        self.reads += 1
        return super().get(key)


def test_pruning_reads_none_of_the_materializations_it_considers() -> None:
    """A materialization can be megabytes and there can be hundreds: pruning must not load them to pick the oldest."""

    @asset(io_manager="run_json", retention=5)
    def scan(*, context: RunContext) -> str:
        return context.run_id

    store = CountingStore()
    io = {"run_json": RunJson(store)}
    defs = Definitions([scan])
    run_ids = [run(defs, io).pointers["scan"].metadata["run_id"] for _ in range(4)]
    store.reads = 0

    io["run_json"].prune("scan", 1)

    assert store.reads == 0
    assert [key.rsplit("/", 1)[-1].removesuffix(".json") for key in store.modified("runs/scan/")] == [run_ids[-1]]


class TiedStore(MemoryStore):
    """S3 times writes to the second, so writes close together tie."""

    def modified(self, prefix: str) -> dict[str, datetime]:
        return {key: datetime(2026, 11, 18, tzinfo=UTC) for key in super().modified(prefix)}


def test_pruning_never_removes_what_was_just_stored_when_the_store_s_times_tie() -> None:
    @asset(io_manager="run_json")
    def scan(*, context: RunContext) -> str:
        return context.run_id

    store = TiedStore()
    io = {"run_json": RunJson(store)}
    defs = Definitions([scan])

    for _ in range(8):
        run_id = run(defs, io).pointers["scan"].metadata["run_id"]
        assert [key.rsplit("/", 1)[-1].removesuffix(".json") for key in store.modified("runs/scan/")] == [run_id]
