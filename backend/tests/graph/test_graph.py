"""The example's graph, run by stepdag's local executor on fixture raw files, with Delta tables in a directory."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from snacker.graph.definitions import defs
from snacker.scans import SCANS_SCHEMA, normalise_scans
from stepdag import run
from stepdag.assets import Bindings
from graph.raw_events import backfill_scan, live_scan, write_raw


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
    return frame


def test_scans_holds_every_scan_from_both_eras(io: Bindings, raw: Path) -> None:
    write_raw(raw, "2019/03/01", "old", [backfill_scan("111", scanned_at="2019-03-01T02:00:00+00:00", event_id="b1")], "2026-10-01T00:00:00+00:00")
    write_raw(raw, "2026/10/20", "new", [live_scan("222", time="2026-10-20T03:30:00Z", event_id="l1")], "2026-10-20T03:35:00+00:00")

    scans = table(io, run(defs, io), "scans").sort("event_id")

    assert scans.select("event_id", "code", "origin", "scanned_at_source", "api_key", "raw_key").to_dicts() == [
        {"event_id": "b1", "code": "111", "origin": "backfill", "scanned_at_source": "device", "api_key": None, "raw_key": "scans/2019/03/01/old"},
        {"event_id": "l1", "code": "222", "origin": "live", "scanned_at_source": "reported", "api_key": "s8ma4oq3ue", "raw_key": "scans/2026/10/20/new"},
    ]
    assert scans["scanned_at"].to_list() == [datetime(2019, 3, 1, 2, tzinfo=UTC), datetime(2026, 10, 20, 3, 30, tzinfo=UTC)]
    assert scans["source_last_modified"].to_list() == [datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 20, 3, 35, tzinfo=UTC)]


def test_an_event_delivered_in_two_files_appears_once(io: Bindings, raw: Path) -> None:
    event = live_scan("333", time="2026-10-21T01:00:00Z", event_id="dup")
    write_raw(raw, "2026/10/21", "a", [event], "2026-10-21T01:05:00+00:00")
    write_raw(raw, "2026/10/21", "b", [event], "2026-10-21T01:06:00+00:00")

    scans = table(io, run(defs, io), "scans")

    assert scans.select("event_id", "raw_key").to_dicts() == [{"event_id": "dup", "raw_key": "scans/2026/10/21/a"}]


def test_scans_holds_snackers_columns_with_the_values_snackers_normaliser_gives(io: Bindings, raw: Path) -> None:
    write_raw(raw, "2019/03/01", "old", [backfill_scan("111", scanned_at="2019-03-01T09:00:00.444637+07:00", location="thailand:chiang-mai")], "2026-10-01T00:00:00+00:00")
    write_raw(raw, "2026/10/20", "a", [live_scan("222", time="2026-10-20T03:30:00Z"), live_scan("333", time="2026-10-20T03:31:00Z")], "2026-10-20T03:35:00+00:00")
    write_raw(raw, "2026/10/20", "b", [live_scan("http://oishidrink.com/m/", time="2026-10-20T04:00:00Z")], "2026-10-20T04:05:00+00:00")

    scans = table(io, run(defs, io), "scans")

    assert scans.columns == [*SCANS_SCHEMA.names(), "raw_key", "source_last_modified"]
    assert scans.drop("raw_key", "source_last_modified").sort("event_id").equals(normalise_scans(raw).sort("event_id"))
