"""The whole site tree: byte-identical to Snacker's build, checked against the contract, and diffed by `parity`."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from scans_example import site as site_module
from scans_example.graph import defs
from stepdag import CheckFailed, run
from stepdag.assets import Bindings
from tests.food_parquet import food, write_archive, write_food
from tests.raw_events import backfill_scan, heartbeat_flat, heartbeat_v2, live_scan, with_api_key, write_heartbeats, write_raw
from tests.snacker_oracle import files_under, snacker_tree

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
ZONES = {"thailand": "Asia/Bangkok", "japan": "Asia/Tokyo"}


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))
    monkeypatch.setenv("SCANS_SITE", str(tmp_path / "site"))
    monkeypatch.setenv("SCANS_OFFICE_TIME_ZONES", json.dumps(ZONES))
    return tmp_path / "site" / "data"


@pytest.fixture
def raw(tmp_path: Path, openfoodfacts: Path, archive: Path) -> Path:
    root = tmp_path / "raw"
    write_raw(root, "2019/03/01", "old", [backfill_scan("111", scanned_at="2019-03-01T02:00:00+00:00")], "2026-10-01T00:00:00+00:00")
    write_raw(root, "2026/10/18", "a", [
        with_api_key(live_scan("222", time="2026-10-18T16:30:00Z"), "key-bkk"),
        with_api_key(live_scan("111", time="2026-10-18T03:00:00Z", location="thailand:bangkok:rooftop"), "key-bkk"),
        with_api_key(live_scan("333", time="2026-10-18T05:00:00Z", location="japan:tokyo:lobby"), "key-tyo"),
        live_scan("https://qrco.de/bbAote", time="2026-10-19T01:00:00Z"),
    ], "2026-10-19T01:05:00+00:00")
    write_heartbeats(root, "2026/10/19", "h", [
        heartbeat_flat(time="2026-10-19T11:00:00Z", api_key="key-bkk"),
        heartbeat_v2(time="2026-10-19T10:00:00Z", device_name="tokyo-1", location="japan:tokyo:lobby", api_key="key-tyo"),
    ], "2026-10-19T11:05:00+00:00")
    write_food(openfoodfacts, [food("111", names=[("main", "One one one")], brands="Acme", nutriscore="b"), food("333", names=[("en", "Three")], nutriscore="e")])
    write_archive(archive, [("222", "Two from the archive")])
    return root


def theirs(raw: Path, openfoodfacts: Path, archive: Path) -> dict[str, bytes]:
    return snacker_tree(raw, openfoodfacts, archive, now=NOW, office_time_zones=ZONES)


def report(io: Bindings, result: Any) -> dict[str, Any]:
    pointer = result.pointers["parity"]
    value: dict[str, Any] = io[pointer.io_manager].load(pointer)
    return value


def test_the_whole_tree_is_byte_identical_to_snackers_build(site: Path, raw: Path, openfoodfacts: Path, archive: Path) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    ours = files_under(site)
    expected = theirs(raw, openfoodfacts, archive)

    assert sorted(ours) == sorted(expected)
    assert [path for path in ours if ours[path] != expected[path]] == []


def test_a_tree_that_breaks_the_contract_fails_at_site_tree_and_publishes_nothing(
    site: Path, raw: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    merged = site_module.merged

    def without_a_scanners_file(bundles: list[site_module.Bundle]) -> dict[str, Any]:
        tree = merged(bundles)
        del tree["scanners/by-location/all.json"]  # The contract wants one per selectable location.
        return tree

    monkeypatch.setattr(site_module, "merged", without_a_scanners_file)

    with pytest.raises(CheckFailed, match="site_tree"):
        run(defs, defs.bindings("local"), started_at=NOW)

    assert not site.exists()


def test_parity_reports_no_differences_for_an_identical_tree(site: Path, raw: Path) -> None:
    io = defs.bindings("local")

    result = run(defs, io, started_at=NOW)

    assert report(io, result) == {"identical": True, "only_ours": [], "only_snackers": [], "differing": []}


def test_parity_names_a_changed_value_and_the_run_still_succeeds(site: Path, raw: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_tree = site_module.write_tree

    def with_a_wrong_location(tree: dict[str, Any], root: Path) -> None:
        # Change one value after the contract check passed, as a publishing bug would.
        tree = {**tree, "locations.json": {"locations": [{"id": "all"}, {"id": "nowhere"}]}}
        write_tree(tree, root)

    io = defs.bindings("local")
    monkeypatch.setattr(site_module, "write_tree", with_a_wrong_location)

    result = run(defs, io, started_at=NOW)

    parity = report(io, result)
    assert parity["identical"] is False
    assert [d["path"] for d in parity["differing"]] == ["locations.json"]
    assert parity["differing"][0]["at"].startswith("$.locations[1]")
