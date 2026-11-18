"""The Site IO manager's contract, against a local directory."""

from pathlib import Path
from typing import Any

from stepdag import RunContext
from stepdag.json_io import MemoryStore

from snacker.graph.site_io import SiteIO


def context(run_id: str, stamp: dict[str, Any] | None = None) -> RunContext:
    return RunContext(run_id=run_id, started_at="2026-10-19T12:00:00+00:00", asset="site_tree", config={}, asset_config={}, force=False, stamp=stamp or {})


def tree(generated_at: str) -> dict[str, Any]:
    return {"meta.json": {"generated_at": generated_at, "contract_version": 4}}


STAMP: dict[str, Any] = {"parents": {"upstream": {"version": 3, "run_id": "r1"}}}


def test_a_stamp_is_stored_with_the_pointer_and_latest_returns_it(tmp_path: Path) -> None:
    io = SiteIO(str(tmp_path / "site"), state=MemoryStore())

    pointer = io.store(tree("2026-10-19T12:00:00Z"), "site_tree", context("r1", STAMP))

    assert pointer.metadata["stamp"] == STAMP
    latest = io.latest("site_tree")
    assert latest is not None
    assert latest.metadata == {"generated_at": "2026-10-19T12:00:00Z", "stamp": STAMP}


def test_a_pointer_without_a_stamp_has_no_stamp_key(tmp_path: Path) -> None:
    io = SiteIO(str(tmp_path / "site"), state=MemoryStore())

    pointer = io.store(tree("2026-10-19T12:00:00Z"), "site_tree", context("r1"))

    assert "stamp" not in pointer.metadata
    latest = io.latest("site_tree")
    assert latest is not None and "stamp" not in latest.metadata


def test_a_later_store_without_a_stamp_drops_the_older_stamp(tmp_path: Path) -> None:
    """Publishing has no commit log to walk back through, so the stamp follows the newest publish."""
    io = SiteIO(str(tmp_path / "site"), state=MemoryStore())
    io.store(tree("2026-10-19T12:00:00Z"), "site_tree", context("r1", STAMP))

    io.store(tree("2026-10-19T13:00:00Z"), "site_tree", context("r2"))

    latest = io.latest("site_tree")
    assert latest is not None
    assert latest.metadata["generated_at"] == "2026-10-19T13:00:00Z"
    assert "stamp" not in latest.metadata


def test_without_a_state_store_no_stamp_is_kept_and_nothing_is_written_beside_the_site(tmp_path: Path) -> None:
    io = SiteIO(str(tmp_path / "site"))

    pointer = io.store(tree("2026-10-19T12:00:00Z"), "site_tree", context("r1", STAMP))

    assert "stamp" not in pointer.metadata
    latest = io.latest("site_tree")
    assert latest is not None and "stamp" not in latest.metadata
    assert sorted(p.relative_to(tmp_path / "site").as_posix() for p in (tmp_path / "site").rglob("*") if p.is_file()) == [
        "data/meta.json",
    ]


def test_the_stamp_is_kept_in_the_state_store_not_in_the_site(tmp_path: Path) -> None:
    state = MemoryStore()
    io = SiteIO(str(tmp_path / "site"), state=state)

    io.store(tree("2026-10-19T12:00:00Z"), "site_tree", context("r1", STAMP))

    assert "site_stamps/site_tree.json" in state.objects
    assert not (tmp_path / "site" / "stamp.json").exists()
