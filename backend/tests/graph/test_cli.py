"""`stepdag run` on the example, with its local bindings."""

import json
from pathlib import Path

import pytest

from snacker.graph.definitions import defs
from stepdag.cli import main
from graph.raw_events import live_scan, write_raw


def test_stepdag_run_builds_the_tables_in_a_local_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_raw(tmp_path / "raw", "2026/10/20", "f", [live_scan("222", time="2026-10-20T03:30:00Z")], "2026-10-20T03:35:00+00:00")
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))

    assert main(["run", "snacker.graph.definitions:defs"]) == 0

    out = json.loads(capsys.readouterr().out)
    assert set(out["computed"]) == set(defs.names)
    assert out["values"]["scans"] == "<LazyFrame>"
    assert (tmp_path / "tables" / "scans" / "_delta_log").is_dir()
