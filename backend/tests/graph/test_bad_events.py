"""Events `scans` can't trust fail the run, and leave the `scans` table as it was.

Snacker's normaliser rejects unknown sources and naive timestamps with its own `ValueError`s."""

from pathlib import Path

import pytest

from snacker.graph.definitions import defs
from stepdag import CheckFailed, run
from stepdag.assets import Bindings
from graph.raw_events import Event, backfill_scan, live_scan, write_raw


@pytest.fixture
def io(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Bindings:
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))
    return defs.bindings("local")


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    return tmp_path / "raw"


def test_an_empty_code_fails_the_check_and_leaves_scans_unchanged(io: Bindings, raw: Path) -> None:
    write_raw(raw, "2026/10/20", "good", [live_scan("111", time="2026-10-20T03:30:00Z")], "2026-10-20T03:35:00+00:00")
    before = run(defs, io).pointers["scans"]
    write_raw(raw, "2026/10/21", "bad", [live_scan("", time="2026-10-21T03:30:00Z", event_id="empty")], "2026-10-21T03:35:00+00:00")

    with pytest.raises(CheckFailed) as failed:
        run(defs, io)

    assert failed.value.asset == "scans"
    assert "every_scan_has_a_code_and_a_time" in failed.value.failures
    assert "code" in failed.value.failures["every_scan_has_a_code_and_a_time"]
    assert io["delta"].latest("scans") == before


def test_an_unknown_source_fails_the_run_naming_the_event(io: Bindings, raw: Path) -> None:
    event = live_scan("111", time="2026-10-20T03:30:00Z", event_id="odd-one") | {"source": "toaster"}
    write_raw(raw, "2026/10/20", "odd", [event], "2026-10-20T03:35:00+00:00")

    with pytest.raises(ValueError, match="toaster.*odd-one"):
        run(defs, io)

    assert io["delta"].latest("scans") is None


def test_a_timestamp_without_a_timezone_fails_the_run_naming_the_value(io: Bindings, raw: Path) -> None:
    write_raw(raw, "2019/03/01", "naive", [backfill_scan("111", scanned_at="2019-03-01T02:00:00")], "2026-10-01T00:00:00+00:00")

    with pytest.raises(ValueError, match="2019-03-01T02:00:00"):
        run(defs, io)

    assert io["delta"].latest("scans") is None


BAD_EVENTS = {
    "empty code": live_scan("", time="2026-10-21T03:30:00Z"),
    "unknown source": live_scan("222", time="2026-10-21T03:30:00Z") | {"source": "toaster"},
    "naive timestamp": backfill_scan("222", scanned_at="2026-10-21T03:30:00"),
}


@pytest.mark.parametrize("bad", BAD_EVENTS.values(), ids=BAD_EVENTS.keys())
def test_after_a_failure_the_next_run_without_the_bad_file_succeeds(io: Bindings, raw: Path, bad: Event) -> None:
    write_raw(raw, "2026/10/20", "good", [live_scan("111", time="2026-10-20T03:30:00Z", event_id="g1")], "2026-10-20T03:35:00+00:00")
    bad_key = write_raw(raw, "2026/10/21", "bad", [bad], "2026-10-21T03:35:00+00:00")
    with pytest.raises((CheckFailed, ValueError)):
        run(defs, io)

    (raw / bad_key).unlink()
    result = run(defs, io)

    pointer = result.pointers["scans"]
    assert io[pointer.io_manager].load(pointer).collect()["event_id"].to_list() == ["g1"]
