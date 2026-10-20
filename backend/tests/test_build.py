"""End-to-end tests at the build seam: raw event files in, static JSON tree out."""

from pathlib import Path

import pytest

from built_output import read_json, run_build, write_products
from raw_events import (
    backfill_scan,
    heartbeat_flat,
    heartbeat_flat_with_telemetry,
    heartbeat_v2,
    live_scan,
    write_events,
)


def test_meta_file_records_when_the_data_was_built_and_to_which_contract(raw_dir: Path, out_dir: Path) -> None:
    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/meta.json") == {"generated_at": "2026-10-19T12:00:00Z", "contract_version": 3}


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
                {"code": "8851959132012", "name": None, "name_source": None, "brands": None, "known": False, "nutri_score": None, "count": 1, "share": 0.5},
                {"code": "8850999220000", "name": None, "name_source": None, "brands": None, "known": False, "nutri_score": None, "count": 1, "share": 0.5},
            ],
        },
        "top_unknown_scans": {
            **{period: [] for period in (
                "today", "this-work-week", "last-7-days", "this-month",
                "last-30-days", "this-year", "last-365-days",
            )},
            "all-time": [
                {"code": "8851959132012", "name": None, "name_source": None, "brands": None, "known": False, "nutri_score": None, "count": 1, "share": 0.5},
                {"code": "8850999220000", "name": None, "name_source": None, "brands": None, "known": False, "nutri_score": None, "count": 1, "share": 0.5},
            ],
        },
        # Neither product has a Nutri-Score, so only the coverage counts are filled in.
        "healthiest_and_least_healthy": {
            **{period: {"healthiest": [], "least_healthy": [], "graded_scans": 0, "scans": 0} for period in (
                "today", "this-work-week", "last-7-days", "this-month",
                "last-30-days", "this-year", "last-365-days",
            )},
            "all-time": {"healthiest": [], "least_healthy": [], "graded_scans": 0, "scans": 2},
        },
        "daily": [{"date": "2023-01-08", "count": 2}],
        "recent": [
            {
                "code": "8851959132012",
                "name": None,
                "name_source": None,
                "brands": None,
                "known": False,
                "nutri_score": None,
                "location": "thailand:bangkok",
                "scanned_at": "2023-01-08T05:00:00Z",
                "office_time": "2023-01-08T12:00:00+07:00",
                "office_time_zone": "Asia/Bangkok",
            },
            {
                "code": "8850999220000",
                "name": None,
                "name_source": None,
                "brands": None,
                "known": False,
                "nutri_score": None,
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
            "nutri_score": "E",
            "nova_group": 4,
            "green_score": "D",
        }},
    )

    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/codes/8851959132012/product.json") == {
        "code": "8851959132012",
        "known": True,
        "product": {
            "name": "Coca Cola",
            "name_source": "openfoodfacts",
            "brands": "Coke, coca cola",
            "quantity": "325 ml",
            "categories": ["Carbonated drinks", "Sodas"],
            "image_url": "https://images.openfoodfacts.org/images/products/885/195/913/2012/front_en.4.400.jpg",
            "off_url": "https://world.openfoodfacts.org/product/8851959132012",
            "nutri_score": "E",
            "nova_group": 4,
            "green_score": "D",
        },
    }
    assert read_json(out_dir, "data/codes/http:%2F%2Foishidrink.com%2Fm%2F/product.json") == {
        "code": "http://oishidrink.com/m/",
        "known": False,
        "product": None,
    }
    url_code_scans = read_json(out_dir, "data/codes/http:%2F%2Foishidrink.com%2Fm%2F/by-location/all.json")
    assert url_code_scans["code"] == "http://oishidrink.com/m/"
    assert read_json(out_dir, "data/codes/005/product.json") == {"code": "005", "known": False, "product": None}


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
            "last_scan": {"scanned_at": "2026-09-23T06:00:00Z", "code": "8850999220000", "product_name": None, "name_source": None, "known": False, "nutri_score": None},
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
        {"code": "8851959132012", "name": "Coca Cola", "name_source": "openfoodfacts", "brands": "Coke", "known": True, "nutri_score": None, "count": 2, "share": 0.6667},
        {"code": "005", "name": None, "name_source": None, "brands": None, "known": False, "nutri_score": None, "count": 1, "share": 0.3333},
    ]
    assert [row["code"] for row in top_scans["all-time"]] == ["8851959132012", "005", "8850999220000"]
    top_unknown = read_json(out_dir, "data/index/by-location/all.json")["top_unknown_scans"]
    assert list(top_unknown) == list(top_scans)
    assert top_unknown["today"] == [
        {"code": "005", "name": None, "name_source": None, "brands": None, "known": False, "nutri_score": None, "count": 1, "share": 0.3333},
    ]
    kitchen = read_json(out_dir, "data/index/by-location/thailand:bangkok:main-kitchen.json")
    assert [row["code"] for row in kitchen["top_scans"]["all-time"]] == ["8851959132012", "005"]


def test_each_scanner_shows_the_last_scan_sent_with_its_api_key(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "heartbeats/2026/10/19/delivery", [
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="kitchen", api_key="key-kitchen"),
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="lobby", api_key="key-lobby"),
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="spare", api_key="key-spare"),
    ])
    write_events(raw_dir, "scans/2026/10/19/delivery", [
        live_scan("8851959132012", time="2026-10-19T08:00:00Z", api_key="key-kitchen"),
        live_scan("8850999220000", time="2026-10-19T07:00:00Z", api_key="key-kitchen"),
        live_scan("005", time="2026-10-19T08:30:00Z", api_key="key-lobby"),
    ])
    # A later backfill scan has no API key, so it is nobody's last scan.
    write_events(raw_dir, "scans/2026/10/19/backfill.jsonl", [
        backfill_scan("8858702410304", scanned_at="2026-10-19T08:45:00Z", location="thailand:bangkok:main-kitchen"),
    ])
    write_products(raw_dir, {"8851959132012": ("Coca Cola", "Coke")})

    run_build(raw_dir, out_dir)

    scanners = read_json(out_dir, "data/scanners/by-location/all.json")["scanners"]
    assert {scanner["name"]: scanner["last_scan"] for scanner in scanners} == {
        "kitchen": {"scanned_at": "2026-10-19T08:00:00Z", "code": "8851959132012", "product_name": "Coca Cola", "name_source": "openfoodfacts", "known": True, "nutri_score": None},
        "lobby": {"scanned_at": "2026-10-19T08:30:00Z", "code": "005", "product_name": None, "name_source": None, "known": False, "nutri_score": None},
        "spare": None,
    }


def test_scan_rows_and_last_scans_say_whether_openfoodfacts_has_the_product(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "heartbeats/2026/10/19/delivery", [
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="kitchen", api_key="key-kitchen"),
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="lobby", api_key="key-lobby"),
    ])
    write_events(raw_dir, "scans/2026/10/19/delivery", [
        live_scan("8851959132012", time="2026-10-19T08:00:00Z", api_key="key-kitchen"),
        live_scan("8850999220000", time="2026-10-19T07:00:00Z"),
        live_scan("005", time="2026-10-19T06:00:00Z", api_key="key-lobby"),
    ])
    # OpenFoodFacts has 8850999220000 but without a name; it doesn't have 005.
    write_products(
        raw_dir,
        {"8851959132012": ("Coca Cola", "Coke"), "8850999220000": (None, None), "005": (None, None)},
        details={"8850999220000": {}},
    )

    run_build(raw_dir, out_dir)

    recent = read_json(out_dir, "data/index/by-location/all.json")["recent"]
    assert [(row["code"], row["name"], row["known"]) for row in recent] == [
        ("8851959132012", "Coca Cola", True),
        ("8850999220000", None, True),
        ("005", None, False),
    ]
    scanners = read_json(out_dir, "data/scanners/by-location/all.json")["scanners"]
    assert {scanner["name"]: scanner["last_scan"] for scanner in scanners} == {
        "kitchen": {"scanned_at": "2026-10-19T08:00:00Z", "code": "8851959132012", "product_name": "Coca Cola", "name_source": "openfoodfacts", "known": True, "nutri_score": None},
        "lobby": {"scanned_at": "2026-10-19T06:00:00Z", "code": "005", "product_name": None, "name_source": None, "known": False, "nutri_score": None},
    }


def test_a_scanner_whose_heartbeats_have_no_api_key_has_no_last_scan(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "heartbeats/2026/10/19/delivery", [
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="keyless", api_key=None),
    ])
    # Backfill scans have no API key either; a missing key must not match them.
    write_events(raw_dir, "scans/2026/10/19/backfill.jsonl", [
        backfill_scan("8858702410304", scanned_at="2026-10-19T08:45:00Z", location="thailand:bangkok:main-kitchen"),
    ])

    run_build(raw_dir, out_dir)

    scanners = read_json(out_dir, "data/scanners/by-location/all.json")["scanners"]
    assert [(scanner["name"], scanner["last_scan"]) for scanner in scanners] == [("keyless", None)]


def test_scan_lists_say_where_each_product_name_came_from(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "heartbeats/2026/10/19/delivery", [
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="kitchen", api_key="key-kitchen"),
    ])
    write_events(raw_dir, "scans/2026/10/19/delivery", [
        live_scan("8851959132012", time="2026-10-19T08:00:00Z"),
        live_scan("220000", time="2026-10-19T07:00:00Z", api_key="key-kitchen"),
        live_scan("005", time="2026-10-19T06:00:00Z"),
    ])
    # OpenFoodFacts names 8851959132012; only the Snacker archive names 220000; nobody names 005.
    write_products(
        raw_dir,
        {"8851959132012": ("Coca Cola", "Coke"), "220000": (None, None), "005": (None, None)},
        archive_names={"220000": "Singha soda 325 ml"},
    )

    run_build(raw_dir, out_dir)

    index = read_json(out_dir, "data/index/by-location/all.json")
    expected = [
        ("8851959132012", "Coca Cola", "openfoodfacts", True),
        ("220000", "Singha soda 325 ml", "snacker-archive", False),
        ("005", None, None, False),
    ]
    assert [(row["code"], row["name"], row["name_source"], row["known"]) for row in index["recent"]] == expected
    assert [
        (row["code"], row["name"], row["name_source"], row["known"]) for row in index["top_scans"]["today"]
    ] == expected
    assert [row["code"] for row in index["top_unknown_scans"]["today"]] == ["220000", "005"]
    last_scan = read_json(out_dir, "data/scanners/by-location/all.json")["scanners"][0]["last_scan"]
    assert (last_scan["product_name"], last_scan["name_source"]) == ("Singha soda 325 ml", "snacker-archive")


def test_a_product_file_has_a_product_whenever_either_source_describes_the_code(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/10/19/delivery", [
        live_scan("220000", time="2026-10-19T08:00:00Z"),
        live_scan("8850999220000", time="2026-10-19T07:00:00Z"),
        live_scan("005", time="2026-10-19T06:00:00Z"),
    ])
    # OpenFoodFacts has 8850999220000 but without a name; only the archive has 220000; nobody has 005.
    write_products(
        raw_dir,
        {"220000": (None, None), "8850999220000": (None, "Singha"), "005": (None, None)},
        archive_names={"220000": "Singha soda 325 ml", "8850999220000": "Singha soda water"},
    )

    run_build(raw_dir, out_dir)

    assert read_json(out_dir, "data/codes/220000/product.json") == {
        "code": "220000",
        "known": False,
        "product": {
            "name": "Singha soda 325 ml",
            "name_source": "snacker-archive",
            "brands": None,
            "quantity": None,
            "categories": [],
            "image_url": None,
            "off_url": None,
            "nutri_score": None,
            "nova_group": None,
            "green_score": None,
        },
    }
    assert read_json(out_dir, "data/codes/8850999220000/product.json") == {
        "code": "8850999220000",
        "known": True,
        "product": {
            "name": "Singha soda water",
            "name_source": "snacker-archive",
            "brands": "Singha",
            "quantity": None,
            "categories": [],
            "image_url": None,
            "off_url": "https://world.openfoodfacts.org/product/8850999220000",
            "nutri_score": None,
            "nova_group": None,
            "green_score": None,
        },
    }
    assert read_json(out_dir, "data/codes/005/product.json") == {"code": "005", "known": False, "product": None}


def test_scan_lists_carry_the_products_nutri_score(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "heartbeats/2026/10/19/delivery", [
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="kitchen", api_key="key-kitchen"),
        heartbeat_v2(time="2026-10-19T09:00:00Z", device_name="lobby", api_key="key-lobby"),
    ])
    write_events(raw_dir, "scans/2026/10/19/delivery", [
        live_scan("8851959132012", time="2026-10-19T08:00:00Z", api_key="key-kitchen"),
        live_scan("8850999220000", time="2026-10-19T07:00:00Z", api_key="key-lobby"),
        live_scan("005", time="2026-10-19T06:00:00Z"),
    ])
    # Coca Cola is graded E; OpenFoodFacts has 8850999220000 but no Nutri-Score; it doesn't have 005.
    write_products(
        raw_dir,
        {"8851959132012": ("Coca Cola", "Coke"), "8850999220000": ("Soda", None), "005": (None, None)},
        details={"8851959132012": {"nutri_score": "E"}},
    )

    run_build(raw_dir, out_dir)

    index = read_json(out_dir, "data/index/by-location/all.json")
    expected = {"8851959132012": "E", "8850999220000": None, "005": None}
    assert {row["code"]: row["nutri_score"] for row in index["recent"]} == expected
    assert {row["code"]: row["nutri_score"] for row in index["top_scans"]["all-time"]} == expected
    code_scans = read_json(out_dir, "data/codes/8851959132012/by-location/all.json")
    assert [row["nutri_score"] for row in code_scans["recent"]] == ["E"]
    scanners = read_json(out_dir, "data/scanners/by-location/all.json")["scanners"]
    assert {scanner["name"]: scanner["last_scan"]["nutri_score"] for scanner in scanners} == {"kitchen": "E", "lobby": None}


def test_index_files_list_the_healthiest_and_least_healthy_products_for_every_period(raw_dir: Path, out_dir: Path) -> None:
    write_events(raw_dir, "scans/2026/10/19/delivery", [
        live_scan("8850999220000", time="2026-10-19T03:00:00Z"),
        live_scan("8851959132012", time="2026-10-19T04:00:00Z", location="thailand:bangkok:lobby"),
        live_scan("005", time="2026-10-19T05:00:00Z"),
    ])
    write_products(
        raw_dir,
        {"8850999220000": ("Soda water", "Singha"), "8851959132012": ("Coca Cola", "Coke"), "005": (None, None)},
        details={"8850999220000": {"nutri_score": "B"}, "8851959132012": {"nutri_score": "E"}},
    )

    run_build(raw_dir, out_dir)

    lists = read_json(out_dir, "data/index/by-location/all.json")["healthiest_and_least_healthy"]
    assert list(lists) == [
        "today", "this-work-week", "last-7-days", "this-month",
        "last-30-days", "this-year", "last-365-days", "all-time",
    ]
    assert lists["today"] == {
        "healthiest": [
            {"code": "8850999220000", "name": "Soda water", "name_source": "openfoodfacts", "brands": "Singha", "known": True, "nutri_score": "B", "count": 1, "share": 0.3333},
        ],
        "least_healthy": [
            {"code": "8851959132012", "name": "Coca Cola", "name_source": "openfoodfacts", "brands": "Coke", "known": True, "nutri_score": "E", "count": 1, "share": 0.3333},
        ],
        "graded_scans": 2,
        "scans": 3,
    }
    kitchen = read_json(out_dir, "data/index/by-location/thailand:bangkok:main-kitchen.json")["healthiest_and_least_healthy"]
    assert (kitchen["today"]["healthiest"][0]["code"], kitchen["today"]["least_healthy"]) == ("8850999220000", [])
