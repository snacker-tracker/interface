"""The published site tree, compared byte for byte with Snacker's own build on the same inputs and `now`."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scans_example.graph import defs
from stepdag import run
from stepdag.manifest import render
from stepdag.assets import Bindings
from tests.food_parquet import food, write_archive, write_food
from tests.raw_events import backfill_scan, live_scan, write_raw
from tests.snacker_oracle import differences, files_under, snacker_tree

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
def raw(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    write_raw(root, "2019/03/01", "old", [backfill_scan("111", scanned_at="2019-03-01T02:00:00+00:00")], "2026-10-01T00:00:00+00:00")
    write_raw(root, "2026/10/18", "a", [
        live_scan("222", time="2026-10-18T16:30:00Z"),  # Already the 19th in Bangkok.
        live_scan("111", time="2026-10-18T03:00:00Z", location="thailand:bangkok:rooftop"),
        live_scan("333", time="2026-10-18T05:00:00Z", location="japan:tokyo:lobby"),
    ], "2026-10-18T16:35:00+00:00")
    # NOW is Monday 19 October 2026, 19:00 in Bangkok and 21:00 in Tokyo: every period, both offices.
    write_raw(root, "2026/10/18", "periods", [
        live_scan("444", time="2026-10-18T16:59:00Z"),  # Sunday 23:59 in Bangkok: last work week.
        live_scan("444", time="2026-10-18T17:00:00Z"),  # Monday 00:00 in Bangkok: this work week starts.
        live_scan("555", time="2026-10-18T14:59:00Z", location="japan:tokyo:lobby"),  # Sunday 23:59 in Tokyo.
        live_scan("555", time="2026-10-18T15:00:00Z", location="japan:tokyo:lobby"),  # Monday 00:00 in Tokyo.
        live_scan("666", time="2026-10-19T11:59:00Z"),  # Today, a minute before NOW.
        live_scan("666", time="2026-10-19T12:00:00Z"),  # Exactly NOW: in every period.
        live_scan("777", time="2026-10-19T12:01:00Z"),  # After NOW: in no period.
        live_scan("888", time="2026-10-01T05:00:00Z", location="japan:tokyo:lobby"),  # This month.
        live_scan("888", time="2026-09-30T14:59:00Z", location="japan:tokyo:lobby"),  # 23:59 last month in Tokyo.
        live_scan("999", time="2026-10-12T12:00:00Z"),  # Exactly 7 days before NOW.
        live_scan("999", time="2026-09-19T12:00:00Z"),  # Exactly 30 days before NOW.
        live_scan("111", time="2026-03-15T08:00:00Z"),  # This year.
        live_scan("444", time="2025-12-20T08:00:00Z", location="thailand:bangkok:rooftop"),  # Last 365 days, last year.
        live_scan("555", time="2025-10-19T12:00:00Z"),  # Exactly 365 days before NOW.
        live_scan("000", time="2025-06-01T08:00:00Z", location="japan:tokyo:lobby"),  # Older than 365 days.
        live_scan("unknown-1", time="2026-10-19T03:00:00Z"),
        live_scan("unknown-1", time="2026-10-15T03:00:00Z", location="japan:tokyo:lobby"),
        live_scan("unknown-2", time="2026-10-02T03:00:00Z", location="thailand:bangkok:rooftop"),
    ], "2026-10-19T12:05:00+00:00")
    return root


@pytest.fixture
def inputs(openfoodfacts: Path, archive: Path) -> tuple[Path, Path]:
    write_food(openfoodfacts, [
        food("111", names=[("main", "One one one")], brands="Acme", nutriscore="b"),
        food("333", names=[("en", "Three")]),
        food("444", names=[("main", "Four")], nutriscore="a"),
        food("555", names=[("main", "Five")], nutriscore="e"),
        food("666", names=[("main", "Six")], nutriscore="c"),
        food("888", names=[("main", "Eight")], nutriscore="d"),
        food("999", names=[("main", "Nine")], nutriscore="a"),
        food("000", names=[("main", "Zero")], nutriscore="e"),
    ])
    write_archive(archive, [("222", "Two from the archive")])
    return openfoodfacts, archive


def test_locations_and_meta_match_snackers_build(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    io: Bindings = defs.bindings("local")
    run(defs, io, started_at=NOW)

    ours = files_under(site)
    theirs = snacker_tree(raw, *inputs, now=NOW, office_time_zones=ZONES)

    assert {"meta.json", "locations.json"} <= set(ours)
    assert differences(ours, theirs) == []


def test_every_locations_index_matches_snackers_build(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    ours = files_under(site)
    theirs = snacker_tree(raw, *inputs, now=NOW, office_time_zones=ZONES)

    indexes = {path for path in theirs if path.startswith("index/")}
    assert len(indexes) > 4  # all, both countries, cities and offices
    assert indexes <= set(ours)
    assert differences(ours, theirs) == []


def test_the_index_sections_run_in_parallel() -> None:
    states = render(defs, "scans_example.graph:defs")["state_machine"]["States"]

    sections = {"top_scans", "top_unknown_scans", "healthiest_and_least_healthy", "nutri_score_distribution", "period_days", "daily_and_recent"}
    parallel = [{branch["StartAt"] for branch in state["Branches"]} for state in states.values() if state["Type"] == "Parallel"]
    [level] = [level for level in parallel if sections & level]
    assert sections <= level


def test_a_location_with_no_office_time_zone_fails_at_scanned(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    write_raw(raw, "2026/10/18", "b", [live_scan("444", time="2026-10-18T06:00:00Z", location="france:paris")], "2026-10-18T16:36:00+00:00")

    with pytest.raises(Exception, match="france"):
        run(defs, defs.bindings("local"), started_at=NOW)

    assert not site.exists()


def test_the_comparison_names_a_file_that_differs(tmp_path: Path) -> None:
    assert differences({"a.json": b"1", "b.json": b"2"}, {"a.json": b"1", "b.json": b"3"}) == ["b.json"]

