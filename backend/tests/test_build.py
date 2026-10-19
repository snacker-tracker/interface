"""End-to-end tests at the build seam: raw event files in, static JSON tree out."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from raw_events import (
    backfill_scan,
    heartbeat_flat,
    heartbeat_flat_with_telemetry,
    heartbeat_v2,
    live_scan,
    write_events,
)
from snacker.build import build
from snacker.products import OPENFOODFACTS_PRODUCT_PAGE, PRODUCTS_SCHEMA

GENERATED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    path = tmp_path / "raw"
    (path / "scans").mkdir(parents=True)
    return path


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "out"


def products_parquet(raw_dir: Path) -> Path:
    return raw_dir.parent / "products.parquet"


def write_products(
    raw_dir: Path,
    products: dict[str, tuple[str | None, str | None]],
    details: dict[str, dict[str, Any]] | None = None,
) -> None:
    """The extracted products table: code -> (name, brands), plus optional details by code.

    A code whose name and brands are both None is an unknown product.
    """
    def row(code: str, name: str | None, brands: str | None) -> dict[str, Any]:
        if name is None and brands is None:
            return {"code": code, "known": False}
        known = {"known": True, "off_url": OPENFOODFACTS_PRODUCT_PAGE.format(code=code), "categories": []}
        return {"code": code, "name": name, "brands": brands, **known, **(details or {}).get(code, {})}

    pl.DataFrame(
        [row(code, name, brands) for code, (name, brands) in products.items()],
        schema=PRODUCTS_SCHEMA,
    ).write_parquet(products_parquet(raw_dir))


def run_build(raw_dir: Path, out_dir: Path) -> None:
    if not products_parquet(raw_dir).exists():
        write_products(raw_dir, {})
    build(
        raw_dir=raw_dir,
        out_dir=out_dir,
        products_parquet=products_parquet(raw_dir),
        generated_at=GENERATED_AT,
    )


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
        # Scans from 2023 fall only in all time, as of the 2026 build; equal counts go to the latest.
        "top_scans": {
            **{period: [] for period in (
                "today", "this-work-week", "last-7-days", "this-month",
                "last-30-days", "this-year", "last-365-days",
            )},
            "all-time": [
                {"code": "8851959132012", "name": None, "brands": None, "known": False, "count": 1, "share": 0.5},
                {"code": "8850999220000", "name": None, "brands": None, "known": False, "count": 1, "share": 0.5},
            ],
        },
        "daily": [{"date": "2023-01-08", "count": 2}],
        "recent": [
            {
                "code": "8851959132012",
                "name": None,
                "brands": None,
                "location": "thailand:bangkok",
                "scanned_at": "2023-01-08T05:00:00Z",
                "office_time": "2023-01-08T12:00:00+07:00",
                "office_time_zone": "Asia/Bangkok",
            },
            {
                "code": "8850999220000",
                "name": None,
                "brands": None,
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


def test_scan_rows_carry_product_names_from_the_extracted_products(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [
        live_scan("8851959132012", time="2026-09-23T06:03:00Z"),
        live_scan("http://oishidrink.com/m/", time="2026-09-23T06:02:00Z"),
        live_scan("8850999220000", time="2026-09-23T06:01:00Z"),
    ])
    write_products(raw_dir, {
        "8851959132012": ("Coca Cola", "Coke, coca cola"),
        "http://oishidrink.com/m/": (None, None),
        # 8850999220000 was scanned after the last extraction, so it isn't in the table yet.
    })

    run_build(raw_dir, out_dir)

    recent = read_json(out_dir, "data/index/by-location/all.json")["recent"]
    assert [(row["code"], row["name"], row["brands"]) for row in recent] == [
        ("8851959132012", "Coca Cola", "Coke, coca cola"),
        ("http://oishidrink.com/m/", None, None),
        ("8850999220000", None, None),
    ]


def test_every_scanned_code_gets_a_product_file(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [
        live_scan("8851959132012", time="2026-09-23T06:03:00Z"),
        live_scan("http://oishidrink.com/m/", time="2026-09-23T06:02:00Z"),
        live_scan("005", time="2026-09-23T06:01:00Z"),
    ])
    write_products(
        raw_dir,
        {"8851959132012": ("Coca Cola", "Coke, coca cola"), "http://oishidrink.com/m/": (None, None)},
        details={"8851959132012": {
            "quantity": "325 ml",
            "categories": ["Carbonated drinks", "Sodas"],
            "image_url": "https://images.openfoodfacts.org/images/products/885/195/913/2012/front_en.4.400.jpg",
        }},
    )

    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/codes/8851959132012/product.json") == {
        "code": "8851959132012",
        "product": {
            "name": "Coca Cola",
            "brands": "Coke, coca cola",
            "quantity": "325 ml",
            "categories": ["Carbonated drinks", "Sodas"],
            "image_url": "https://images.openfoodfacts.org/images/products/885/195/913/2012/front_en.4.400.jpg",
            "off_url": "https://world.openfoodfacts.org/product/8851959132012",
        },
    }
    assert read_json(out_dir, "data/codes/http:%2F%2Foishidrink.com%2Fm%2F/product.json") == {
        "code": "http://oishidrink.com/m/",
        "product": None,
    }
    url_code_scans = read_json(out_dir, "data/codes/http:%2F%2Foishidrink.com%2Fm%2F/by-location/all.json")
    assert url_code_scans["code"] == "http://oishidrink.com/m/"
    assert read_json(out_dir, "data/codes/005/product.json") == {"code": "005", "product": None}


def test_a_code_gets_a_scans_file_for_each_location_it_was_scanned_in(
    raw_dir: Path, out_dir: Path
) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [
        live_scan("8851959132012", time="2026-09-23T02:15:00Z", location="thailand:bangkok:main-kitchen"),
        live_scan("8850999220000", time="2026-09-23T02:20:00Z", location="thailand:test"),
    ])

    run_build(raw_dir, out_dir)

    by_location = out_dir / "data/codes/8851959132012/by-location"
    assert sorted(p.name for p in by_location.iterdir()) == [
        "all.json",
        "thailand.json",
        "thailand:bangkok.json",
        "thailand:bangkok:main-kitchen.json",
    ]
    kitchen = read_json(out_dir, "data/codes/8851959132012/by-location/thailand:bangkok:main-kitchen.json")
    assert kitchen["code"] == "8851959132012"
    assert kitchen["location"] == "thailand:bangkok:main-kitchen"
    assert kitchen["daily"] == [{"date": "2026-09-23", "count": 1}]
    assert len(kitchen["hourly"]) == 24
    assert kitchen["hourly"][9] == {"hour": 9, "count": 1}  # 02:15 UTC is 09:15 in Bangkok
    assert [row["code"] for row in kitchen["recent"]] == ["8851959132012"]


def test_a_scanner_is_listed_from_its_latest_heartbeat_in_any_shape(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [live_scan("8850999220000", time="2026-09-23T06:00:00Z")])
    write_events(raw_dir, "heartbeats/2026/09/04/a", [heartbeat_flat(time="2026-09-04T11:27:30Z", version="v0.1.35")])
    write_events(raw_dir, "heartbeats/2026/09/08/b", [
        heartbeat_flat_with_telemetry(time="2026-09-08T17:40:59Z", version="v0.1.36"),
    ])
    write_events(raw_dir, "heartbeats/2026/10/19/c", [
        heartbeat_v2(time="2026-10-19T09:45:47Z", version="v0.1.42"),
        heartbeat_v2(time="2026-10-19T09:15:47Z", version="v0.1.41"),
    ])

    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/scanners/by-location/all.json") == {
        "location": "all",
        "scanners": [{
            "name": "rpi-pico-w-01",
            "location": "thailand:bangkok:main-kitchen",
            "app_version": "v0.1.42",
            "last_seen": "2026-10-19T09:45:47Z",
        }],
    }


def test_scanners_are_listed_under_their_location_and_every_location_above_it(
    raw_dir: Path, out_dir: Path
) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [
        live_scan("8850999220000", time="2026-09-23T06:00:00Z", location="thailand:bangkok:main-kitchen"),
        live_scan("8850999220000", time="2026-09-23T06:01:00Z", location="thailand:test"),
    ])
    write_events(raw_dir, "heartbeats/2026/09/23/delivery", [
        heartbeat_flat(time="2026-09-23T06:00:00Z", device_name="kitchen-flat"),
        heartbeat_flat_with_telemetry(time="2026-09-23T06:00:00Z", device_name="test-bench",
                                      location="thailand:test"),
        heartbeat_v2(time="2026-09-23T06:00:00Z", device_name="kitchen-v2"),
    ])

    run_build(raw_dir, out_dir)

    def names(location: str) -> list[str]:
        scanners = read_json(out_dir, f"data/scanners/by-location/{location}.json")["scanners"]
        return [scanner["name"] for scanner in scanners]

    assert names("all") == ["kitchen-flat", "kitchen-v2", "test-bench"]
    assert names("thailand") == ["kitchen-flat", "kitchen-v2", "test-bench"]
    assert names("thailand:bangkok") == ["kitchen-flat", "kitchen-v2"]
    assert names("thailand:bangkok:main-kitchen") == ["kitchen-flat", "kitchen-v2"]
    assert names("thailand:test") == ["test-bench"]


def test_without_heartbeats_every_location_lists_no_scanners(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [live_scan("8850999220000", time="2026-09-23T06:00:00Z")])

    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/scanners/by-location/all.json") == {"location": "all", "scanners": []}


def test_a_heartbeat_in_an_unknown_shape_stops_the_build(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/09/23/delivery", [live_scan("8850999220000", time="2026-09-23T06:00:00Z")])
    odd = heartbeat_v2(time="2026-09-23T06:00:00Z")
    odd["detail"]["payload"] = {"schema_version": 3, "scanner": {"name": "rpi-pico-w-02"}}
    write_events(raw_dir, "heartbeats/2026/09/23/delivery", [odd])

    with pytest.raises(ValueError, match="heartbeat in an unknown shape"):
        run_build(raw_dir, out_dir)


def test_index_files_list_top_scans_for_every_period(raw_dir: Path, out_dir: Path) -> None:
    # GENERATED_AT is 2026-10-19 12:00 UTC (19:00 Monday in Bangkok).
    write_events(raw_dir, "scans/2026/10/19/delivery", [
        live_scan("8851959132012", time="2026-10-19T03:00:00Z"),
        live_scan("8851959132012", time="2026-10-19T04:00:00Z"),
        live_scan("005", time="2026-10-19T05:00:00Z"),
    ])
    write_events(raw_dir, "scans/2023/01/08/backfill-2023-01-08.jsonl", [
        backfill_scan("8850999220000", scanned_at="2023-01-08T03:10:22Z", location="thailand:bangkok"),
    ])
    write_products(raw_dir, {"8851959132012": ("Coca Cola", "Coke"), "005": (None, None)})

    run_build(raw_dir, out_dir)

    top_scans = read_json(out_dir, "data/index/by-location/all.json")["top_scans"]
    assert list(top_scans) == [
        "today", "this-work-week", "last-7-days", "this-month",
        "last-30-days", "this-year", "last-365-days", "all-time",
    ]
    assert top_scans["today"] == [
        {"code": "8851959132012", "name": "Coca Cola", "brands": "Coke", "known": True, "count": 2, "share": 0.6667},
        {"code": "005", "name": None, "brands": None, "known": False, "count": 1, "share": 0.3333},
    ]
    assert [row["code"] for row in top_scans["all-time"]] == ["8851959132012", "005", "8850999220000"]
    kitchen = read_json(out_dir, "data/index/by-location/thailand:bangkok:main-kitchen.json")
    assert [row["code"] for row in kitchen["top_scans"]["all-time"]] == ["8851959132012", "005"]
