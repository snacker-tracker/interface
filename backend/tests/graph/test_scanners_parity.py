"""Scanners files, from `heartbeats` and `scanned`, compared byte for byte with Snacker's own build."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from snacker.graph.definitions import defs
from stepdag import run
from stepdag.assets import Bindings
from graph.food_parquet import food, write_archive, write_food
from graph.raw_events import backfill_scan, heartbeat_flat, heartbeat_flat_with_telemetry, heartbeat_v2, live_scan, with_api_key, write_heartbeats, write_raw
from graph.snacker_oracle import differences, files_under, snacker_tree

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
ZONES = {"thailand": "Asia/Bangkok", "japan": "Asia/Tokyo"}


@pytest.fixture
def io(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Bindings:
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))
    monkeypatch.setenv("SCANS_SITE", str(tmp_path / "site"))
    monkeypatch.setenv("SCANS_OFFICE_TIME_ZONES", json.dumps(ZONES))
    return defs.bindings("local")


@pytest.fixture
def site(tmp_path: Path) -> Path:
    return tmp_path / "site" / "data"


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    write_raw(root, "2019/03/01", "old", [backfill_scan("111", scanned_at="2019-03-01T02:00:00+00:00")], "2026-10-01T00:00:00+00:00")
    write_raw(root, "2026/10/18", "a", [
        with_api_key(live_scan("222", time="2026-10-18T16:30:00Z"), "key-kitchen"),
        with_api_key(live_scan("111", time="2026-10-18T03:00:00Z", location="thailand:bangkok:rooftop"), "key-rooftop"),
        with_api_key(live_scan("333", time="2026-10-18T05:00:00Z", location="japan:tokyo:lobby"), "key-lobby"),
    ], "2026-10-18T16:35:00+00:00")
    return root


@pytest.fixture
def inputs(openfoodfacts: Path, archive: Path) -> tuple[Path, Path]:
    write_food(openfoodfacts, [food("111", names=[("main", "One one one")], brands="Acme", nutriscore="b"), food("333", names=[("en", "Three")])])
    write_archive(archive, [("222", "Two from the archive")])
    return openfoodfacts, archive


def scanners_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: data for path, data in files.items() if path.startswith("scanners/")}


def scanner_names(site: Path, location: str) -> list[str]:
    return [s["name"] for s in json.loads((site / "scanners" / "by-location" / f"{location}.json").read_text())["scanners"]]


def test_every_scanners_file_matches_snackers_build(io: Bindings, site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    write_heartbeats(raw, "2026/10/18", "a", [
        heartbeat_flat(time="2026-10-18T09:00:00Z", device_name="kitchen", api_key="key-kitchen"),
        heartbeat_flat_with_telemetry(time="2026-10-18T09:01:00Z", device_name="rooftop", location="thailand:bangkok:rooftop", api_key="key-rooftop"),
        heartbeat_v2(time="2026-10-18T09:02:00Z", device_name="lobby", location="japan:tokyo:lobby", api_key="key-lobby"),
    ], "2026-10-18T09:05:00+00:00")
    write_heartbeats(raw, "2026/10/19", "b", [
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="kitchen", api_key="key-kitchen", version="v0.1.43"),
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="idle", location="thailand:bangkok", api_key="key-idle"),
    ], "2026-10-19T09:05:00+00:00")

    run(defs, io, started_at=NOW)

    ours = files_under(site)
    theirs = snacker_tree(raw, *inputs, now=NOW, office_time_zones=ZONES)
    assert set(scanners_files(ours)) == set(scanners_files(theirs)) != set()
    assert differences(ours, theirs) == []


def test_a_scanner_that_moved_is_listed_only_at_its_latest_heartbeats_location(io: Bindings, site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    write_heartbeats(raw, "2026/10/18", "a", [heartbeat_v2(time="2026-10-18T09:00:00Z", device_name="traveller", api_key="key-kitchen")], "2026-10-18T09:05:00+00:00")
    run(defs, io, started_at=NOW)
    assert scanner_names(site, "thailand") == ["traveller"]
    write_heartbeats(raw, "2026/10/19", "b", [heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="traveller", location="japan:tokyo:lobby", api_key="key-kitchen")], "2026-10-19T09:05:00+00:00")

    run(defs, io, started_at=NOW)

    assert scanner_names(site, "japan") == ["traveller"]
    assert scanner_names(site, "thailand") == []
    assert scanner_names(site, "all") == ["traveller"]
    assert differences(files_under(site), snacker_tree(raw, *inputs, now=NOW, office_time_zones=ZONES)) == []


def test_an_older_heartbeat_read_again_inside_the_margin_doesnt_replace_a_newer_one(io: Bindings, site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    write_heartbeats(raw, "2026/10/19", "0900", [heartbeat_v2(time="2026-10-19T08:59:00Z", device_name="kitchen", location="japan:tokyo:lobby", api_key="key-kitchen")], "2026-10-19T09:00:00+00:00")
    write_heartbeats(raw, "2026/10/19", "1010", [heartbeat_v2(time="2026-10-19T10:09:00Z", device_name="rooftop", api_key="key-rooftop")], "2026-10-19T10:10:00+00:00")
    run(defs, io, started_at=NOW)
    # Written after that run, 5 minutes before its watermark (10:10), holding an older heartbeat
    # than the one `kitchen` has, whose own file (09:00) is outside the margin and isn't read again.
    write_heartbeats(raw, "2026/10/19", "0950", [heartbeat_flat(time="2026-10-19T08:00:00Z", device_name="kitchen", api_key="key-kitchen")], "2026-10-19T10:05:00+00:00")

    run(defs, io, started_at=NOW)

    scanners = json.loads((site / "scanners" / "by-location" / "all.json").read_text())["scanners"]
    assert [(s["name"], s["location"], s["last_seen"]) for s in scanners] == [
        ("kitchen", "japan:tokyo:lobby", "2026-10-19T08:59:00Z"),
        ("rooftop", "thailand:bangkok:main-kitchen", "2026-10-19T10:09:00Z"),
    ]
    assert differences(files_under(site), snacker_tree(raw, *inputs, now=NOW, office_time_zones=ZONES)) == []


def test_a_second_run_with_no_new_heartbeat_files_skips_heartbeats(io: Bindings, site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    # The newest file always sits inside its own watermark's margin, so it is read again each run.
    write_heartbeats(raw, "2026/10/19", "a", [heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="kitchen", api_key="key-kitchen")], "2026-10-19T09:05:00+00:00")
    first = run(defs, io, started_at=NOW)

    second = run(defs, io, started_at=NOW)

    assert "heartbeats" in first.computed
    assert "heartbeats" in second.skipped
    assert second.pointers["heartbeats"] == first.pointers["heartbeats"]


def test_each_scanners_last_scan_is_the_latest_sent_with_its_api_key(io: Bindings, site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    # Two scanners in one pantry: matching by location would give both the same last scan.
    write_raw(raw, "2026/10/19", "b", [
        with_api_key(live_scan("111", time="2026-10-19T08:00:00Z"), "key-left"),
        with_api_key(live_scan("333", time="2026-10-19T07:00:00Z"), "key-right"),
        with_api_key(live_scan("222", time="2026-10-19T06:00:00Z"), "key-left"),
    ], "2026-10-19T08:05:00+00:00")
    write_heartbeats(raw, "2026/10/19", "a", [
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="left", api_key="key-left"),
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="right", api_key="key-right"),
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="silent", api_key="key-silent"),
    ], "2026-10-19T09:05:00+00:00")

    run(defs, io, started_at=NOW)

    scanners = json.loads((site / "scanners" / "by-location" / "thailand:bangkok:main-kitchen.json").read_text())["scanners"]
    last_scans = {s["name"]: s["last_scan"] and (s["last_scan"]["product"]["code"], s["last_scan"]["scanned_at"]) for s in scanners}
    assert last_scans == {"left": ("111", "2026-10-19T08:00:00Z"), "right": ("333", "2026-10-19T07:00:00Z"), "silent": None}
    assert differences(files_under(site), snacker_tree(raw, *inputs, now=NOW, office_time_zones=ZONES)) == []
