"""The published site's meta, locations and index files: the values Snacker's legacy build gave them on the same inputs and `now`."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from snacker.graph.definitions import defs
from stepdag import run
from stepdag.manifest import render
from graph.food_parquet import food, write_archive, write_food
from graph.raw_events import backfill_scan, live_scan, write_raw

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


# Expected values from Snacker's legacy build on these inputs, before it was deleted (#125).


def test_locations_and_meta_are_what_snackers_build_wrote(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    assert json.loads((site / "meta.json").read_text()) == {"generated_at": "2026-10-19T12:00:00Z", "contract_version": 4}
    assert [location["id"] for location in json.loads((site / "locations.json").read_text())["locations"]] == [
        "all", "japan", "japan:tokyo", "japan:tokyo:lobby", "thailand", "thailand:bangkok", "thailand:bangkok:main-kitchen", "thailand:bangkok:rooftop",
    ]


def top(site: Path, location: str, section: str) -> dict[str, list[tuple[str, int]]]:
    """Each period's (code, count) rows in a location's index file."""
    index = json.loads((site / "index" / "by-location" / f"{location}.json").read_text())
    return {period: [(row["product"]["code"], row["count"]) for row in rows] for period, rows in index[section].items()}


def test_each_periods_top_scans_count_the_scans_snackers_build_counted(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    assert len(list((site / "index" / "by-location").iterdir())) == 8  # all, both countries, cities and offices
    assert top(site, "all", "top_scans") == {
        "today": [('666', 2), ('unknown-1', 1), ('444', 1), ('555', 1)],
        "this-work-week": [('666', 2), ('unknown-1', 1), ('444', 1), ('555', 1)],
        "last-7-days": [('666', 2), ('unknown-1', 2), ('444', 2), ('555', 2), ('222', 1), ('333', 1), ('111', 1), ('999', 1)],
        "this-month": [('666', 2), ('unknown-1', 2), ('444', 2), ('555', 2), ('222', 1), ('333', 1), ('111', 1), ('999', 1), ('unknown-2', 1), ('888', 1)],
        "last-30-days": [('666', 2), ('unknown-1', 2), ('444', 2), ('555', 2), ('999', 2), ('888', 2), ('222', 1), ('333', 1), ('111', 1), ('unknown-2', 1)],
        "this-year": [('666', 2), ('unknown-1', 2), ('444', 2), ('555', 2), ('111', 2), ('999', 2), ('888', 2), ('222', 1), ('333', 1), ('unknown-2', 1)],
        "last-365-days": [('444', 3), ('555', 3), ('666', 2), ('unknown-1', 2), ('111', 2), ('999', 2), ('888', 2), ('222', 1), ('333', 1), ('unknown-2', 1)],
        "all-time": [('444', 3), ('555', 3), ('111', 3), ('666', 2), ('unknown-1', 2), ('999', 2), ('888', 2), ('222', 1), ('333', 1), ('unknown-2', 1)],
    }
    assert top(site, "all", "top_unknown_scans") == {
        "today": [('unknown-1', 1)],
        "this-work-week": [('unknown-1', 1)],
        "last-7-days": [('unknown-1', 2), ('222', 1)],
        "this-month": [('unknown-1', 2), ('222', 1), ('unknown-2', 1)],
        "last-30-days": [('unknown-1', 2), ('222', 1), ('unknown-2', 1)],
        "this-year": [('unknown-1', 2), ('222', 1), ('unknown-2', 1)],
        "last-365-days": [('unknown-1', 2), ('222', 1), ('unknown-2', 1)],
        "all-time": [('unknown-1', 2), ('222', 1), ('unknown-2', 1)],
    }
    # Tokyo's own day boundaries: Monday starts at 15:00 UTC on the 18th there.
    assert top(site, "japan", "top_scans") == {
        "today": [('555', 1)],
        "this-work-week": [('555', 1)],
        "last-7-days": [('555', 2), ('333', 1), ('unknown-1', 1)],
        "this-month": [('555', 2), ('333', 1), ('unknown-1', 1), ('888', 1)],
        "last-30-days": [('555', 2), ('888', 2), ('333', 1), ('unknown-1', 1)],
        "this-year": [('555', 2), ('888', 2), ('333', 1), ('unknown-1', 1)],
        "last-365-days": [('555', 2), ('888', 2), ('333', 1), ('unknown-1', 1)],
        "all-time": [('555', 2), ('888', 2), ('333', 1), ('unknown-1', 1), ('000', 1)],
    }


def test_the_index_sections_run_in_parallel() -> None:
    states = render(defs, "snacker.graph.definitions:defs")["state_machine"]["States"]

    sections = {"top_scans", "top_unknown_scans", "healthiest_and_least_healthy", "nutri_score_distribution", "period_days", "daily_and_recent"}
    parallel = [{branch["StartAt"] for branch in state["Branches"]} for state in states.values() if state["Type"] == "Parallel"]
    [level] = [level for level in parallel if sections & level]
    assert sections <= level


def test_a_location_with_no_office_time_zone_fails_at_scanned(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    write_raw(raw, "2026/10/18", "b", [live_scan("444", time="2026-10-18T06:00:00Z", location="france:paris")], "2026-10-18T16:36:00+00:00")

    with pytest.raises(Exception, match="france"):
        run(defs, defs.bindings("local"), started_at=NOW)

    assert not site.exists()

