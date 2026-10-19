"""Tests at the contract seam: the published JSON Schema, and built output checked against it."""

from pathlib import Path
from typing import Any

import pytest

from built_output import run_build, write_products
from raw_events import backfill_scan, heartbeat_flat, heartbeat_v2, live_scan, write_events
from snacker.check import contract_violations
from snacker.schema import schema_errors, schema_json

COMMITTED_SCHEMA = Path(__file__).parents[2] / "contract" / "static-json.schema.json"


def build_every_kind_of_file(raw_dir: Path, out_dir: Path) -> Path:
    """A build with each kind of value the contract allows; returns its data directory."""
    write_events(raw_dir, "scans/2023/01/08/backfill", [
        backfill_scan("8850999220000", scanned_at="2023-01-08T03:10:22.444637+00:00"),
    ])
    write_events(raw_dir, "scans/2026/10/19/delivery", [
        live_scan("8851959132012", time="2026-10-19T02:00:00Z"),
        live_scan("http://oishidrink.com/m/", time="2026-10-19T03:00:00Z", location="thailand:staff room"),
        live_scan("005", time="2026-10-19T04:00:00Z", location="thailand:test"),
    ])
    write_events(raw_dir, "heartbeats/2026/10/19/a", [
        heartbeat_v2(time="2026-10-19T11:55:00Z"),
        # Unversioned heartbeats carry no API key, so this scanner has no last scan.
        heartbeat_flat(time="2026-10-19T11:50:00Z", device_name="rpi-pico-w-02", location="thailand:test"),
    ])
    write_products(
        raw_dir,
        {"8851959132012": ("Coca Cola", "Coke"), "8850999220000": (None, None)},
        details={"8851959132012": {
            "quantity": "325 ml",
            "categories": ["Sodas"],
            "image_url": "https://images.openfoodfacts.org/images/products/885/195/913/2012/front_en.4.400.jpg",
        }},
    )
    run_build(raw_dir, out_dir)
    return out_dir / "data"


def test_the_committed_schema_is_generated_from_the_contract() -> None:
    assert COMMITTED_SCHEMA.read_text() == schema_json(), (
        "contract/static-json.schema.json is out of date: "
        "run `uv run snacker schema --out ../contract/static-json.schema.json` in backend/"
    )


def test_every_built_file_matches_its_schema(raw_dir: Path, out_dir: Path) -> None:
    data_dir = build_every_kind_of_file(raw_dir, out_dir)

    assert contract_violations(data_dir) == []
    # The build above reaches every kind of file, so the check covered each document.
    assert (data_dir / "codes/http:%2F%2Foishidrink.com%2Fm%2F/by-location/thailand:staff%20room.json").exists()
    assert (data_dir / "scanners/by-location/thailand:test.json").exists()


def valid_scan_row() -> dict[str, Any]:
    return {
        "code": "005",
        "name": None,
        "brands": None,
        "location": "thailand:test",
        "scanned_at": "2026-10-19T04:00:00Z",
        "office_time": "2026-10-19T11:00:00+07:00",
        "office_time_zone": "Asia/Bangkok",
    }


def code_scans_file(**recent_row_changes: Any) -> dict[str, Any]:
    row = {**valid_scan_row(), **recent_row_changes}
    return {"code": "005", "location": "all", "daily": [], "hourly": [], "recent": [row]}


def test_a_valid_document_has_no_schema_errors() -> None:
    assert schema_errors("CodeScansFile", code_scans_file()) == []


@pytest.mark.parametrize(
    ("document", "expected_error"),
    [
        # A field may be null only where the contract says so.
        (code_scans_file(code=None), "recent/0/code: None is not of type 'string'"),
        # Fields the contract doesn't describe are rejected, so additions are deliberate.
        (code_scans_file(scanned_by="someone"), "recent/0: Additional properties are not allowed ('scanned_by' was unexpected)"),
    ],
)
def test_the_schema_rejects_documents_that_break_the_contract(document: dict[str, Any], expected_error: str) -> None:
    assert schema_errors("CodeScansFile", document) == [expected_error]


def test_every_field_is_required_even_when_it_may_be_null() -> None:
    row = valid_scan_row()
    del row["name"]

    assert schema_errors("CodeScansFile", {**code_scans_file(), "recent": [row]}) == [
        "recent/0: 'name' is a required property"
    ]


def test_index_files_must_list_every_period() -> None:
    every_period: dict[str, list[Any]] = {
        period: [] for period in (
            "today", "this-work-week", "last-7-days", "this-month",
            "last-30-days", "this-year", "last-365-days", "all-time",
        )
    }
    without_today = {period: lists for period, lists in every_period.items() if period != "today"}
    index = {"location": "all", "top_scans": without_today, "top_unknown_scans": every_period, "daily": [], "recent": []}

    assert schema_errors("IndexFile", index) == ["top_scans: 'today' is a required property"]
