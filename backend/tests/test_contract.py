"""Tests at the contract seam: the published JSON Schema, and built output checked against the
whole contract (shapes, which files exist, and the rules across them)."""

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import snacker.build
from built_output import products_parquet, read_json, run_build, write_products
from raw_events import backfill_scan, heartbeat_flat, heartbeat_v2, live_scan, write_events
from snacker import scan_summary
from snacker.build import ContractBroken, build
from snacker.check import contract_violations
from snacker.scan_summary import ScanSummary
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
        # Only the Snacker archive names the QR code.
        archive_names={"http://oishidrink.com/m/": "Oishi green tea"},
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
        "name_source": None,
        "brands": None,
        "known": False,
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


def edit_json(data_dir: Path, relative_path: str, edit: Callable[[Any], None]) -> None:
    file = data_dir / relative_path
    content = json.loads(file.read_text())
    edit(content)
    file.write_text(json.dumps(content))


KITCHEN_CODE_SCANS = "codes/8851959132012/by-location/thailand:bangkok:main-kitchen.json"


@pytest.mark.parametrize(
    ("breakage", "expected"),
    [
        (
            lambda data: (data / "index/by-location/thailand:test.json").unlink(),
            "index/by-location/thailand:test.json: missing: every selectable location has one ('thailand:test')",
        ),
        (
            lambda data: (data / "codes/005/product.json").unlink(),
            "codes/005/by-location/all.json: codes/005/product.json is missing",
        ),
        (
            lambda data: (data / "stray.json").write_text("{}"),
            "stray.json: not a file the contract describes",
        ),
        (
            # Written at a single-encoded path, as if the encoding rule had changed.
            lambda data: (data / "index/by-location/thailand:staff%20room.json").rename(
                data / "index/by-location/thailand:staff room.json"
            ),
            "index/by-location/thailand:staff room.json: its content belongs at index/by-location/thailand:staff%20room.json",
        ),
        (
            lambda data: edit_json(data, KITCHEN_CODE_SCANS, lambda content: content["hourly"].pop()),
            f"{KITCHEN_CODE_SCANS}: hourly: isn't exactly hours 0 to 23 in order",
        ),
        (
            lambda data: edit_json(data, "locations.json", lambda content: content["locations"].remove({"id": "thailand:test"})),
            "index/by-location/thailand:test.json: location 'thailand:test' isn't selectable",
        ),
        (
            lambda data: edit_json(
                data, KITCHEN_CODE_SCANS, lambda content: content["recent"][0].update(office_time="2026-10-19T02:00:00+07:00")
            ),
            f"{KITCHEN_CODE_SCANS}: recent/0: office_time '2026-10-19T02:00:00+07:00' isn't the moment 2026-10-19T02:00:00Z",
        ),
        (
            lambda data: edit_json(
                data, KITCHEN_CODE_SCANS, lambda content: content["recent"][0].update(office_time="2026-10-19T03:00:00+01:00")
            ),
            f"{KITCHEN_CODE_SCANS}: recent/0: office_time '2026-10-19T03:00:00+01:00' isn't in Asia/Bangkok",
        ),
        (
            lambda data: edit_json(data, "index/by-location/all.json", lambda content: content["daily"].reverse()),
            "index/by-location/all.json: daily: dates aren't unique and oldest first",
        ),
        (
            lambda data: edit_json(data, "index/by-location/all.json", lambda content: content["recent"].reverse()),
            "index/by-location/all.json: recent: isn't newest first",
        ),
        (
            lambda data: edit_json(
                data, "index/by-location/all.json", lambda content: content["top_unknown_scans"]["all-time"][0].update(known=True)
            ),
            "index/by-location/all.json: top_unknown_scans/all-time: lists a known product",
        ),
        (
            lambda data: edit_json(
                data, "index/by-location/all.json", lambda content: content["top_scans"]["all-time"][0].update(share=0.9)
            ),
            "index/by-location/all.json: top_scans/all-time: shares add up to more than 1",
        ),
        (
            lambda data: edit_json(data, KITCHEN_CODE_SCANS, lambda content: content["recent"][0].update(name_source=None)),
            f"{KITCHEN_CODE_SCANS}: recent/0: name_source is null but the name isn't",
        ),
        (
            lambda data: edit_json(
                data,
                "index/by-location/all.json",
                lambda content: content["top_unknown_scans"]["all-time"][0].update(name="Soda", name_source="openfoodfacts"),
            ),
            "index/by-location/all.json: top_unknown_scans/all-time/0: an OpenFoodFacts name for a product OpenFoodFacts doesn't have",
        ),
        (
            lambda data: edit_json(
                data, "codes/8851959132012/product.json", lambda content: content["product"].update(name_source=None)
            ),
            "codes/8851959132012/product.json: product: name_source is null but the name isn't",
        ),
        (
            lambda data: edit_json(data, "meta.json", lambda content: content.update(generated_at="2026-10-19T12:00:00+00:00")),
            "meta.json: generated_at: '2026-10-19T12:00:00+00:00' isn't a UTC time like 2026-10-19T12:00:00Z",
        ),
    ],
    ids=[
        "missing index file", "missing product file", "stray file", "wrong encoding", "23-entry hourly",
        "unselectable location", "office time a different moment", "office time in another zone",
        "daily out of order", "recent out of order", "known product in unknown-only list", "shares over 1",
        "name without a source", "OpenFoodFacts name for an unknown product", "product name without a source", "generated_at not in UTC",
    ],
)
def test_the_check_names_each_way_a_build_breaks_the_contract(
    raw_dir: Path, out_dir: Path, breakage: Callable[[Path], object], expected: str
) -> None:
    data_dir = build_every_kind_of_file(raw_dir, out_dir)

    breakage(data_dir)

    assert expected in [str(violation) for violation in contract_violations(data_dir)]


def test_a_build_that_breaks_the_contract_is_not_published(
    raw_dir: Path, out_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_events(raw_dir, "scans/2026/10/19/delivery", [live_scan("005", time="2026-10-19T04:00:00Z")])
    run_build(raw_dir, out_dir)
    previous = read_json(out_dir, "data/meta.json")

    def summarise_losing_an_hour(scans: Any, *, recent_limit: int) -> ScanSummary:
        summary = scan_summary.summarise(scans, recent_limit=recent_limit)
        return replace(summary, hourly=summary.hourly[:23])

    monkeypatch.setattr(snacker.build, "summarise", summarise_losing_an_hour)
    with pytest.raises(ContractBroken) as broken:
        build(
            raw_dir=raw_dir,
            out_dir=out_dir,
            products_parquet=products_parquet(raw_dir),
            generated_at=datetime(2026, 10, 20, tzinfo=UTC),
        )

    assert [str(violation) for violation in broken.value.violations] == [
        "codes/005/by-location/all.json: hourly: isn't exactly hours 0 to 23 in order",
        "codes/005/by-location/thailand.json: hourly: isn't exactly hours 0 to 23 in order",
        "codes/005/by-location/thailand:bangkok.json: hourly: isn't exactly hours 0 to 23 in order",
        "codes/005/by-location/thailand:bangkok:main-kitchen.json: hourly: isn't exactly hours 0 to 23 in order",
    ]
    assert read_json(out_dir, "data/meta.json") == previous
    assert (broken.value.staging_dir / "codes/005/by-location/all.json").exists()  # kept to inspect


def test_a_build_replaces_the_previous_data_entirely(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/10/19/delivery", [live_scan("005", time="2026-10-19T04:00:00Z")])
    run_build(raw_dir, out_dir)
    (raw_dir / "scans/2026/10/19/delivery").unlink()
    write_events(raw_dir, "scans/2026/10/19/redelivery", [live_scan("006", time="2026-10-19T04:00:00Z")])

    run_build(raw_dir, out_dir)

    assert sorted(path.name for path in (out_dir / "data/codes").iterdir()) == ["006"]
    assert sorted(path.name for path in out_dir.iterdir()) == ["data"]


def test_meta_must_name_this_contract_version() -> None:
    assert schema_errors("MetaFile", {"generated_at": "2026-10-19T12:00:00Z", "contract_version": 1}) == [
        "contract_version: 2 was expected"
    ]
