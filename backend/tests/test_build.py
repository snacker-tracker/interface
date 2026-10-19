"""End-to-end tests at the build seam: raw event files in, static JSON tree out."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from raw_events import backfill_scan, live_scan, write_events
from snacker.build import build

GENERATED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    path = tmp_path / "raw"
    (path / "scans").mkdir(parents=True)
    return path


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "out"


def run_build(raw_dir: Path, out_dir: Path) -> None:
    build(raw_dir=raw_dir, out_dir=out_dir, generated_at=GENERATED_AT)


def read_json(out_dir: Path, relative_path: str) -> Any:
    return json.loads((out_dir / relative_path).read_text())


def test_meta_file_records_when_the_data_was_built(raw_dir: Path, out_dir: Path) -> None:
    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/meta.json") == {"generated_at": "2026-10-19T12:00:00Z"}


def test_all_index_counts_scans_per_day(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2023/01/08/backfill-2023-01-08.jsonl", [
        backfill_scan("8850999220000", scanned_at="2023-01-08T03:10:22.444637+00:00"),
        backfill_scan("8851959132012", scanned_at="2023-01-08T05:00:00.000000+00:00"),
    ])
    write_events(raw_dir, "scans/2023/01/11/backfill-2023-01-11.jsonl", [
        backfill_scan("8850999220000", scanned_at="2023-01-11T02:32:32.203884+00:00"),
    ])

    run_build(raw_dir, out_dir)

    index = read_json(out_dir, "data/index/by-location/all.json")
    assert index["location"] == "all"
    assert index["daily"] == [
        {"date": "2023-01-08", "count": 2},
        {"date": "2023-01-11", "count": 1},
    ]


def test_live_scans_without_a_device_timestamp_are_placed_by_when_they_were_reported(
    raw_dir: Path, out_dir: Path
) -> None:
    write_events(raw_dir, "scans/2026/09/23/snacker-tracker-prod-1-2026-09-23-06-05-43-x", [
        live_scan("8853333010015", time="2026-09-23T06:05:42Z"),
    ])
    write_events(raw_dir, "scans/2023/01/08/backfill-2023-01-08.jsonl", [
        backfill_scan("8850999220000", scanned_at="2023-01-08T03:10:22.444637+00:00"),
    ])

    run_build(raw_dir, out_dir)

    index = read_json(out_dir, "data/index/by-location/all.json")
    assert index["daily"] == [
        {"date": "2023-01-08", "count": 1},
        {"date": "2026-09-23", "count": 1},
    ]


def test_a_redelivered_event_is_counted_once(raw_dir: Path, out_dir: Path) -> None:
    scan = live_scan("8853333010015", time="2026-09-23T06:05:42Z", event_id="ef5c58ca-dup")
    write_events(raw_dir, "scans/2026/09/23/delivery-a", [scan])
    write_events(raw_dir, "scans/2026/09/23/delivery-b", [scan])

    run_build(raw_dir, out_dir)

    index = read_json(out_dir, "data/index/by-location/all.json")
    assert index["daily"] == [{"date": "2026-09-23", "count": 1}]


def test_all_index_lists_the_25_most_recent_scans_newest_first(
    raw_dir: Path, out_dir: Path
) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [
        live_scan(f"88500000000{minute:02d}", time=f"2026-09-23T06:{minute:02d}:00Z")
        for minute in range(27)
    ])

    run_build(raw_dir, out_dir)

    recent = read_json(out_dir, "data/index/by-location/all.json")["recent"]
    assert len(recent) == 25
    assert recent[0] == {
        "code": "8850000000026",
        "location": "thailand:bangkok:main-kitchen",
        "scanned_at": "2026-09-23T06:26:00Z",
    }
    assert recent[-1]["scanned_at"] == "2026-09-23T06:02:00Z"


def test_a_scan_from_an_unknown_source_stops_the_build(raw_dir: Path, out_dir: Path) -> None:
    scan = live_scan("8853333010015", time="2026-09-23T06:05:42Z")
    scan["source"] = "somewhere-new"
    write_events(raw_dir, "scans/2026/09/23/delivery", [scan])

    with pytest.raises(ValueError, match="unknown scan source 'somewhere-new'"):
        run_build(raw_dir, out_dir)


def test_a_scan_timestamp_without_a_timezone_stops_the_build(
    raw_dir: Path, out_dir: Path
) -> None:
    write_events(raw_dir, "scans/2023/01/08/backfill-2023-01-08.jsonl", [
        backfill_scan("8850999220000", scanned_at="2023-01-08T03:10:22"),
    ])

    with pytest.raises(ValueError, match="timestamp without a timezone: '2023-01-08T03:10:22'"):
        run_build(raw_dir, out_dir)
