"""`scans` grows incrementally, following ADR 0011's watermark rule, run by stepdag's local executor."""

import json
import os
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from scans_example.graph import defs, scans
from stepdag import Definitions, Pointer, asset, run
from stepdag.assets import Bindings
from tests.raw_events import live_scan, write_raw


@pytest.fixture
def io(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Bindings:
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))
    return defs.bindings("local")


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    return tmp_path / "raw"


def table(io: Bindings, result: Any, name: str) -> pl.DataFrame:
    pointer = result.pointers[name]
    frame: pl.DataFrame = io[pointer.io_manager].load(pointer).collect()
    return frame.sort("event_id")


def rewrite_keeping_mtime(raw: Path, key: str, events: list[dict[str, Any]]) -> None:
    """Change a raw file's contents without changing its last-modified time, so only a full read sees it."""
    path = raw / key
    stat = path.stat()
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    os.utime(path, (stat.st_atime, stat.st_mtime))


def test_a_new_file_adds_only_its_scans(io: Bindings, raw: Path) -> None:
    old = write_raw(raw, "2026/10/20", "a", [live_scan("111", time="2026-10-20T01:00:00Z", event_id="e1")], "2026-10-20T01:05:00+00:00")
    write_raw(raw, "2026/10/20", "b", [live_scan("222", time="2026-10-20T03:30:00Z", event_id="e2")], "2026-10-20T03:35:00+00:00")
    before = table(io, run(defs, io), "scans")
    # Changed in place, but modified long before the watermark (03:35), so only a full read would see it.
    rewrite_keeping_mtime(raw, old, [live_scan("999", time="2026-10-20T01:00:00Z", event_id="e1"), live_scan("999", time="2026-10-20T01:00:00Z", event_id="e9")])
    write_raw(raw, "2026/10/21", "c", [live_scan("333", time="2026-10-21T00:55:00Z", event_id="e3")], "2026-10-21T01:00:00+00:00")

    after = table(io, run(defs, io), "scans")

    assert after.filter(pl.col("event_id") != "e3").equals(before)
    assert after["code"].to_list() == ["111", "222", "333"]


def test_a_file_landing_inside_the_margin_is_read_and_nothing_counts_twice(io: Bindings, raw: Path) -> None:
    write_raw(raw, "2026/10/20", "1000", [live_scan("111", time="2026-10-20T10:00:00Z", event_id="e1")], "2026-10-20T10:10:00+00:00")
    run(defs, io)
    # Named earlier, but written after the last run, 5 minutes before its watermark: Firehose closes buffers late.
    write_raw(raw, "2026/10/20", "0955", [live_scan("222", time="2026-10-20T09:55:00Z", event_id="e2")], "2026-10-20T10:05:00+00:00")

    scans = table(io, run(defs, io), "scans")

    assert scans.select("event_id", "code", "raw_key").to_dicts() == [
        {"event_id": "e1", "code": "111", "raw_key": "scans/2026/10/20/1000"},
        {"event_id": "e2", "code": "222", "raw_key": "scans/2026/10/20/0955"},
    ]


def test_a_run_with_no_new_files_skips_scans_and_downstream_reads_its_existing_pointer(io: Bindings, raw: Path) -> None:
    seen: list[int] = []

    @asset(deps=["scans"], io_manager="delta")
    def scan_count(scans: pl.LazyFrame) -> pl.DataFrame:
        count = scans.select(pl.len()).collect().item()
        seen.append(count)
        return pl.DataFrame({"n": [count]})

    graph = Definitions([scans, scan_count])
    write_raw(raw, "2026/10/20", "a", [live_scan("111", time="2026-10-20T10:00:00Z", event_id="e1")], "2026-10-20T10:10:00+00:00")
    first = run(graph, io)

    second = run(graph, io)

    assert second.skipped == ["scans"]
    assert second.computed == ["scan_count"]
    pointer: Pointer = second.pointers["scans"]
    assert pointer == first.pointers["scans"]
    assert seen == [1, 1]


def test_a_forced_run_reads_every_file_and_leaves_what_a_first_run_would(io: Bindings, raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gone = write_raw(raw, "2026/10/18", "gone", [live_scan("000", time="2026-10-18T10:00:00Z", event_id="e0")], "2026-10-18T10:05:00+00:00")
    old = write_raw(raw, "2026/10/19", "a", [live_scan("111", time="2026-10-19T10:00:00Z", event_id="e1")], "2026-10-19T10:05:00+00:00")
    write_raw(raw, "2026/10/21", "b", [live_scan("222", time="2026-10-21T10:00:00Z", event_id="e2")], "2026-10-21T10:05:00+00:00")
    run(defs, io)
    # Since then: a normaliser-visible change, a file deleted, and a late file in a folder before the listing starts.
    rewrite_keeping_mtime(raw, old, [live_scan("999", time="2026-10-19T10:00:00Z", event_id="e1")])
    (raw / gone).unlink()
    write_raw(raw, "2026/10/17", "late", [live_scan("333", time="2026-10-17T10:00:00Z", event_id="e3")], "2026-10-21T10:06:00+00:00")
    assert table(io, run(defs, io), "scans")["event_id"].to_list() == ["e0", "e1", "e2"]

    forced = table(io, run(defs, io, force=True), "scans")

    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "fresh"))
    fresh_io = defs.bindings("local")
    assert forced.equals(table(fresh_io, run(defs, fresh_io), "scans"))
    assert forced["code"].to_list() == ["999", "222", "333"]
