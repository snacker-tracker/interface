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
        {"8851959132012": ("Coca Cola", "Coke"), "8850999220000": (None, None), "http://oishidrink.com/m/": (None, None)},
        # Only the Snacker archive names the QR code.
        archive_names={"http://oishidrink.com/m/": "Oishi green tea"},
        details={"8851959132012": {
            "quantity": "325 ml",
            "categories": ["Sodas"],
            "image_url": "https://images.openfoodfacts.org/images/products/885/195/913/2012/front_en.4.400.jpg",
            "nutri_score": "E",
            "nova_group": 4,
            "green_score": "D",
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
        "product": {"code": "005", "name": None, "name_source": None, "brands": None, "known": False, "nutri_score": None},
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
        (
            code_scans_file(product={**valid_scan_row()["product"], "code": None}),
            "recent/0/product/code: None is not of type 'string'",
        ),
        # Fields the contract doesn't describe are rejected, so additions are deliberate.
        (code_scans_file(scanned_by="someone"), "recent/0: Additional properties are not allowed ('scanned_by' was unexpected)"),
    ],
)
def test_the_schema_rejects_documents_that_break_the_contract(document: dict[str, Any], expected_error: str) -> None:
    assert schema_errors("CodeScansFile", document) == [expected_error]


def test_every_field_is_required_even_when_it_may_be_null() -> None:
    row = valid_scan_row()
    del row["product"]["name"]

    assert schema_errors("CodeScansFile", {**code_scans_file(), "recent": [row]}) == [
        "recent/0/product: 'name' is a required property"
    ]


def test_index_files_must_list_every_period() -> None:
    every_period: dict[str, list[Any]] = {
        period: [] for period in (
            "today", "this-work-week", "last-7-days", "this-month",
            "last-30-days", "this-year", "last-365-days", "all-time",
        )
    }
    without_today = {period: lists for period, lists in every_period.items() if period != "today"}
    no_products = {"healthiest": [], "least_healthy": [], "graded_scans": 0, "scans": 0}
    index = {
        "location": "all", "top_scans": without_today, "top_unknown_scans": every_period,
        "healthiest_and_least_healthy": {period: no_products for period in every_period},
        "period_days": {period: {"first_day": None, "last_day": None} for period in every_period},
        "daily": [], "recent": [],
    }

    assert schema_errors("IndexFile", index) == ["top_scans: 'today' is a required property"]


def edit_all_time_health(edit: Callable[[Any], None]) -> Callable[[Path], None]:
    """A breakage of the all index file's all-time healthiest and least healthy products, where
    Coca Cola (graded E) is the only graded product. `graded(...)` makes more graded rows."""
    return lambda data: edit_json(
        data, "index/by-location/all.json", lambda content: edit(content["healthiest_and_least_healthy"]["all-time"])
    )


def graded(lists: Any, code: str, nutri_score: str) -> dict[str, Any]:
    row = lists["healthiest"][0]
    return {**row, "product": {**row["product"], "code": code, "nutri_score": nutri_score}}


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
                data, "index/by-location/all.json", lambda content: content["top_unknown_scans"]["all-time"][0]["product"].update(known=True)
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
            lambda data: edit_json(data, KITCHEN_CODE_SCANS, lambda content: content["recent"][0]["product"].update(name_source=None)),
            f"{KITCHEN_CODE_SCANS}: recent/0: name_source is null but the name isn't",
        ),
        (
            lambda data: edit_json(
                data,
                "index/by-location/all.json",
                lambda content: content["top_unknown_scans"]["all-time"][0]["product"].update(name="Soda", name_source="openfoodfacts"),
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
            lambda data: edit_json(
                data, "codes/http:%2F%2Foishidrink.com%2Fm%2F/product.json",
                lambda content: content["product"].update(nutri_score="A"),
            ),
            "codes/http:%2F%2Foishidrink.com%2Fm%2F/product.json: product: grades for a product OpenFoodFacts doesn't have",
        ),
        (
            lambda data: edit_json(
                data,
                "index/by-location/all.json",
                lambda content: content["top_unknown_scans"]["all-time"][0]["product"].update(nutri_score="A"),
            ),
            "index/by-location/all.json: top_unknown_scans/all-time/0: a Nutri-Score for a product OpenFoodFacts doesn't have",
        ),
        (
            lambda data: edit_json(
                data, "scanners/by-location/all.json",
                lambda content: next(s for s in content["scanners"] if s["last_scan"])["last_scan"]["product"].update(name="Soda", name_source=None),
            ),
            "scanners/by-location/all.json: rpi-pico-w-01 last_scan: name_source is null but the name isn't",
        ),
        (
            edit_all_time_health(lambda lists: lists.update(healthiest=[graded(lists, "water", "E")])),
            "index/by-location/all.json: code 'water' has no product file",
        ),
        (
            edit_all_time_health(lambda lists: lists["least_healthy"].append(lists["healthiest"][0])),
            "index/by-location/all.json: healthiest_and_least_healthy/all-time: a product is in both lists",
        ),
        (
            edit_all_time_health(lambda lists: lists["healthiest"][0]["product"].update(nutri_score=None)),
            "index/by-location/all.json: healthiest_and_least_healthy/all-time: lists a product without a Nutri-Score",
        ),
        (
            edit_all_time_health(lambda lists: lists["healthiest"].append(graded(lists, "water", "E"))),
            "index/by-location/all.json: healthiest_and_least_healthy/all-time: isn't split in halves",
        ),
        (
            edit_all_time_health(lambda lists: lists.update(
                healthiest=[graded(lists, "water", "A"), graded(lists, "milk", "C")],
                least_healthy=[graded(lists, "chips", "D"), graded(lists, "cake", "E")],
            )),
            "index/by-location/all.json: healthiest_and_least_healthy/all-time: least_healthy isn't worst grade first, then most scanned",
        ),
        (
            edit_all_time_health(lambda lists: lists.update(
                healthiest=[graded(lists, "water", "A"), graded(lists, "chips", "E")],
                least_healthy=[graded(lists, "cake", "D"), graded(lists, "milk", "C")],
            )),
            "index/by-location/all.json: healthiest_and_least_healthy/all-time: a least healthy product is graded better than a healthiest one",
        ),
        (
            edit_all_time_health(lambda lists: lists.update(
                healthiest=[graded(lists, f"water-{n}", "A") for n in range(11)],
                least_healthy=[graded(lists, f"chips-{n}", "E") for n in range(11)],
            )),
            "index/by-location/all.json: healthiest_and_least_healthy/all-time: healthiest lists 11 products, more than 10",
        ),
        (
            edit_all_time_health(lambda lists: lists.update(graded_scans=lists["scans"] + 1)),
            "index/by-location/all.json: healthiest_and_least_healthy/all-time: more graded scans than scans",
        ),
        (
            lambda data: edit_json(
                data, "index/by-location/all.json",
                lambda content: content["period_days"]["today"].update(first_day="2026-10-20"),
            ),
            "index/by-location/all.json: period_days/today: first_day is after last_day",
        ),
        (
            lambda data: edit_json(
                data, "index/by-location/all.json",
                lambda content: content["period_days"]["all-time"].update(first_day="2023-01-01"),
            ),
            "index/by-location/all.json: period_days/all-time: doesn't start on the first scanned day",
        ),
        (
            lambda data: edit_json(
                data, "index/by-location/all.json",
                lambda content: content["period_days"]["this-month"].update(last_day="2026-10-18"),
            ),
            "index/by-location/all.json: period_days: the periods end on different days",
        ),
        (
            lambda data: edit_json(
                data, "index/by-location/all.json",
                lambda content: content.update(period_days={
                    period: {**days, "last_day": "2026-10-25"} for period, days in content["period_days"].items()
                }),
            ),
            "index/by-location/all.json: period_days: last_day 2026-10-25 isn't the day the data was built",
        ),
        (
            lambda data: edit_json(
                data, "index/by-location/all.json", lambda content: content["period_days"]["today"].update(first_day=None),
            ),
            "index/by-location/all.json: period_days/today: days are null though there are scans",
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
        "name without a source", "OpenFoodFacts name for an unknown product", "product name without a source",
        "grades for an unknown product",
        "Nutri-Score for an unknown product in a list", "last scan name without a source", "health-list code without a product file", "product in both health lists", "ungraded product in a health list",
        "health lists not split in halves", "least healthy out of order", "health lists overlap in grade",
        "health list over the limit", "more graded scans than scans",
        "period starts after it ends", "all time not from the first scan", "periods end on different days",
        "periods end on another day than the build", "null period days with scans", "generated_at not in UTC",
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
    assert schema_errors("MetaFile", {"generated_at": "2026-10-19T12:00:00Z", "contract_version": 2}) == [
        "contract_version: 3 was expected"
    ]
