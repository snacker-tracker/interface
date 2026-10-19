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


def test_the_all_index_file_summarises_every_scan(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2023/01/08/backfill-2023-01-08.jsonl", [
        backfill_scan("8850999220000", scanned_at="2023-01-08T03:10:22.444637+00:00"),
        backfill_scan("8851959132012", scanned_at="2023-01-08T05:00:00.000000+00:00"),
    ])

    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/index/by-location/all.json") == {
        "location": "all",
        "daily": [{"date": "2023-01-08", "count": 2}],
        "recent": [
            {
                "code": "8851959132012",
                "location": "thailand:bangkok",
                "scanned_at": "2023-01-08T05:00:00Z",
                "office_time": "2023-01-08T12:00:00+07:00",
                "office_time_zone": "Asia/Bangkok",
            },
            {
                "code": "8850999220000",
                "location": "thailand:bangkok",
                "scanned_at": "2023-01-08T03:10:22Z",
                "office_time": "2023-01-08T10:10:22+07:00",
                "office_time_zone": "Asia/Bangkok",
            },
        ],
    }


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


def test_every_selectable_location_gets_its_own_index_file(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2023/01/08/backfill-2023-01-08.jsonl", [
        backfill_scan("8850999220000", scanned_at="2023-01-08T03:10:22Z", location="thailand:bangkok"),
    ])
    write_events(raw_dir, "scans/2026/09/23/delivery", [
        live_scan("8853333010015", time="2026-09-23T06:05:42Z", location="thailand:bangkok:main-kitchen"),
    ])

    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/locations.json") == {"locations": [
        {"id": "all"},
        {"id": "thailand"},
        {"id": "thailand:bangkok"},
        {"id": "thailand:bangkok:main-kitchen"},
    ]}
    assert sorted(p.name for p in (out_dir / "data/index/by-location").iterdir()) == [
        "all.json",
        "thailand.json",
        "thailand:bangkok.json",
        "thailand:bangkok:main-kitchen.json",
    ]
    kitchen = read_json(out_dir, "data/index/by-location/thailand:bangkok:main-kitchen.json")
    assert kitchen["location"] == "thailand:bangkok:main-kitchen"
    assert [row["code"] for row in kitchen["recent"]] == ["8853333010015"]


def test_location_file_names_are_percent_encoded_but_keep_colons_readable(
    raw_dir: Path, out_dir: Path
) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [
        live_scan("8853333010015", time="2026-09-23T06:05:42Z", location="thailand:staff room/2"),
    ])

    run_build(raw_dir, out_dir)

    index = read_json(out_dir, "data/index/by-location/thailand:staff%20room%2F2.json")
    assert index["location"] == "thailand:staff room/2"


def test_days_are_counted_in_the_office_time_zone(raw_dir: Path, out_dir: Path) -> None:
    # 18:30 UTC on the 22nd is 01:30 on the 23rd in Bangkok, where Thai locations are.
    write_events(raw_dir, "scans/2026/09/22/delivery", [
        live_scan("8853333010015", time="2026-09-22T18:30:00Z", location="thailand:bangkok:main-kitchen"),
    ])

    run_build(raw_dir, out_dir)

    index = read_json(out_dir, "data/index/by-location/all.json")
    assert index["daily"] == [{"date": "2026-09-23", "count": 1}]
    assert index["recent"][0]["office_time"] == "2026-09-23T01:30:00+07:00"


def test_a_location_without_an_office_time_zone_stops_the_build(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [
        live_scan("8853333010015", time="2026-09-23T06:05:42Z", location="vietnam:hanoi"),
    ])

    with pytest.raises(ValueError, match="no office time zone for location 'vietnam:hanoi'"):
        run_build(raw_dir, out_dir)
