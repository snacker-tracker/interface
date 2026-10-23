"""Tests at the event cache's seam: raw events and the cache in buckets, the scans and
heartbeats a build reads out (ADR 0011)."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fake_bucket import FakeBucket, opener
from raw_events import Event, heartbeat_v2, live_scan, write_events
from snacker.event_cache import load_events, load_scans

RAW = "s3://raw/raw/data/scanner"
CACHE = "s3://working/cache"
VERSION = "sha256:aaaa"
T0 = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)


def add(raw: FakeBucket, path: str, events: list[Event], *, modified: datetime) -> str:
    """A raw file, delivered at `modified`, under the scanner prefix."""
    key = f"raw/data/scanner/{path}"
    raw.objects[key] = "".join(json.dumps(event) + "\n" for event in events).encode()
    raw.modified_at[key] = modified
    return key


@pytest.fixture
def buckets() -> dict[str, FakeBucket]:
    raw = FakeBucket()
    add(raw, "scans/2026/10/21/a", [live_scan("111", time="2026-10-21T03:00:00Z", event_id="s1")], modified=T0)
    add(raw, "heartbeats/2026/10/21/b", [heartbeat_v2(time="2026-10-21T03:00:00Z", device_name="kitchen")], modified=T0)
    add(raw, "heartbeats/2026/10/21/c", [heartbeat_v2(time="2026-10-21T02:00:00Z", device_name="kitchen")], modified=T0)
    return {"raw": raw, "working": FakeBucket()}


def load(buckets: dict[str, FakeBucket], *, version: str | None = VERSION, save: bool = True) -> tuple[list[str], list[tuple[str, str]]]:
    """Load through the cache; the scanned codes and (scanner, last seen) it gave."""
    events = load_events(RAW, cache=CACHE, version=version, open_bucket=opener(buckets), save=save)
    heartbeats = [(row["scanner"], row["sent_at"].isoformat()) for row in events.heartbeats.iter_rows(named=True)]
    return sorted(events.scans["code"].to_list()), heartbeats


def reset(bucket: FakeBucket) -> None:
    bucket.gets.clear()
    bucket.listings.clear()
    bucket.calls.clear()


def test_without_a_cache_every_raw_file_is_read_and_the_cache_written(buckets: dict[str, FakeBucket]) -> None:
    codes, heartbeats = load(buckets)

    assert codes == ["111"]
    assert heartbeats == [("kitchen", "2026-10-21T03:00:00+00:00")]
    assert len(buckets["raw"].gets) == 3
    assert sorted(buckets["working"].puts()) == ["cache/heartbeats.parquet", "cache/scans.parquet"]


def test_with_a_current_cache_files_older_than_the_margin_are_not_read_again(buckets: dict[str, FakeBucket]) -> None:
    old = "raw/data/scanner/scans/2026/10/21/a"  # modified at T0
    load(buckets)
    add(buckets["raw"], "scans/2026/10/21/d", [live_scan("222", time="2026-10-21T04:00:00Z")], modified=T0 + timedelta(hours=1))
    load(buckets)  # the watermark is now an hour after the old file
    reset(buckets["raw"])
    new = add(buckets["raw"], "scans/2026/10/21/e", [live_scan("333", time="2026-10-21T04:05:00Z")],
              modified=T0 + timedelta(hours=1, minutes=5))

    codes, _ = load(buckets)

    assert codes == ["111", "222", "333"]
    assert new in buckets["raw"].gets
    assert old not in buckets["raw"].gets
    # Each listing starts at the day folder before the watermark's day.
    assert buckets["raw"].listings == [
        ("raw/data/scanner/scans/", "raw/data/scanner/scans/2026/10/20/"),
        ("raw/data/scanner/heartbeats/", "raw/data/scanner/heartbeats/2026/10/20/"),
    ]


def test_nothing_new_rereads_only_the_margin_and_writes_no_cache(buckets: dict[str, FakeBucket]) -> None:
    add(buckets["raw"], "heartbeats/2026/10/21/old", [heartbeat_v2(time="2026-10-21T01:00:00Z", device_name="lobby")],
        modified=T0 - timedelta(hours=2))
    load(buckets)
    reset(buckets["raw"])
    reset(buckets["working"])

    load(buckets)

    assert sorted(buckets["raw"].gets) == [
        "raw/data/scanner/heartbeats/2026/10/21/b",
        "raw/data/scanner/heartbeats/2026/10/21/c",
        "raw/data/scanner/scans/2026/10/21/a",
    ]
    assert buckets["working"].puts() == []


def test_a_file_in_the_margin_is_read_again_but_counted_once(buckets: dict[str, FakeBucket]) -> None:
    add(buckets["raw"], "scans/2026/10/21/e", [live_scan("333", time="2026-10-21T03:05:00Z", event_id="s3")],
        modified=T0 + timedelta(minutes=10))
    load(buckets)  # watermark T0+10m; the margin reaches back to T0-5m, past both scan files
    reset(buckets["raw"])
    reset(buckets["working"])

    codes, heartbeats = load(buckets)

    assert codes == ["111", "333"]
    assert heartbeats == [("kitchen", "2026-10-21T03:00:00+00:00")]
    assert len(buckets["raw"].gets) == 4  # everything was within the margin
    assert buckets["working"].puts() == []


def test_a_file_that_lands_late_with_an_earlier_name_is_picked_up(buckets: dict[str, FakeBucket]) -> None:
    add(buckets["raw"], "scans/2026/10/21/z", [live_scan("999", time="2026-10-21T03:20:00Z")],
        modified=T0 + timedelta(minutes=20))
    load(buckets)  # watermark T0+20m
    # Named for its buffer's start, before z, but written 5 minutes after the watermark.
    late = add(buckets["raw"], "scans/2026/10/21/m", [live_scan("444", time="2026-10-21T03:10:00Z")],
               modified=T0 + timedelta(minutes=25))

    codes, _ = load(buckets)

    assert "444" in codes
    assert late in buckets["raw"].gets


def test_after_a_gap_of_days_every_heartbeat_in_the_gap_is_considered(buckets: dict[str, FakeBucket]) -> None:
    load(buckets)
    add(buckets["raw"], "heartbeats/2026/10/23/f", [heartbeat_v2(time="2026-10-23T09:00:00Z", device_name="lobby")],
        modified=T0 + timedelta(days=2))
    add(buckets["raw"], "heartbeats/2026/10/25/g", [heartbeat_v2(time="2026-10-25T09:00:00Z", device_name="kitchen")],
        modified=T0 + timedelta(days=4))

    _, heartbeats = load(buckets)

    assert heartbeats == [("kitchen", "2026-10-25T09:00:00+00:00"), ("lobby", "2026-10-23T09:00:00+00:00")]


def test_a_cache_from_another_code_version_is_rebuilt_from_raw(buckets: dict[str, FakeBucket]) -> None:
    load(buckets)
    reset(buckets["raw"])

    load(buckets, version="sha256:bbbb")

    assert len(buckets["raw"].gets) == 3
    assert buckets["raw"].listings == [("raw/data/scanner/scans/", ""), ("raw/data/scanner/heartbeats/", "")]


def test_without_a_code_version_raw_is_read_in_full_and_no_cache_is_written(buckets: dict[str, FakeBucket]) -> None:
    load(buckets)
    reset(buckets["raw"])
    reset(buckets["working"])

    codes, _ = load(buckets, version=None)

    assert codes == ["111"]
    assert len(buckets["raw"].gets) == 3
    assert buckets["working"].puts() == []


def test_a_reader_that_does_not_save_leaves_the_cache_alone(buckets: dict[str, FakeBucket]) -> None:
    load(buckets, save=False)

    assert buckets["working"].puts() == []


def test_scans_alone_are_loaded_without_reading_heartbeats(buckets: dict[str, FakeBucket]) -> None:
    scans = load_scans(RAW, cache=CACHE, version=VERSION, open_bucket=opener(buckets), save=False)

    assert scans["code"].to_list() == ["111"]
    assert all(not key.startswith("raw/data/scanner/heartbeats/") for key in buckets["raw"].gets)


def test_a_raw_location_with_nothing_in_it_stops_the_build(buckets: dict[str, FakeBucket]) -> None:
    buckets["raw"].objects.clear()

    with pytest.raises(FileNotFoundError, match="raw/data/scanner"):
        load(buckets)


def test_heartbeats_without_any_scans_yet_still_build(buckets: dict[str, FakeBucket]) -> None:
    del buckets["raw"].objects["raw/data/scanner/scans/2026/10/21/a"]

    codes, heartbeats = load(buckets)
    codes_again, _ = load(buckets)

    assert codes == codes_again == []
    assert heartbeats == [("kitchen", "2026-10-21T03:00:00+00:00")]


def test_a_local_raw_directory_and_cache_directory_work_as_buckets_do(tmp_path: Path) -> None:
    raw_dir, cache_dir = tmp_path / "raw", tmp_path / "cache"

    def deliver(path: str, events: list[Event], modified: datetime) -> None:
        write_events(raw_dir, path, events)
        os.utime(raw_dir / path, (modified.timestamp(), modified.timestamp()))

    deliver("scans/2026/10/21/a", [live_scan("111", time="2026-10-21T03:00:00Z")], T0)
    deliver("heartbeats/2026/10/21/b", [heartbeat_v2(time="2026-10-21T03:00:00Z", device_name="kitchen")], T0)

    first = load_events(str(raw_dir), cache=str(cache_dir), version=VERSION, open_bucket=opener({}))
    written = {path.name: path.stat().st_mtime_ns for path in cache_dir.iterdir()}
    deliver("scans/2026/10/21/c", [live_scan("222", time="2026-10-21T04:00:00Z")], T0 + timedelta(hours=1))
    second = load_events(str(raw_dir), cache=str(cache_dir), version=VERSION, open_bucket=opener({}))

    assert first.scans["code"].to_list() == ["111"]
    assert sorted(second.scans["code"].to_list()) == ["111", "222"]
    assert sorted(written) == ["heartbeats.parquet", "scans.parquet"]
