"""The whole site tree: every file, the values Snacker's legacy build gave them, and checked against the contract."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from snacker import sections as site_module
from snacker.graph.definitions import defs
from stepdag import CheckFailed, run
from graph.food_parquet import food, write_archive, write_food
from graph.raw_events import backfill_scan, heartbeat_flat, heartbeat_v2, live_scan, with_api_key, write_heartbeats, write_raw
from graph.published import files_under

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
ZONES = {"thailand": "Asia/Bangkok", "japan": "Asia/Tokyo"}


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))
    monkeypatch.setenv("SCANS_SITE", str(tmp_path / "site"))
    monkeypatch.setenv("SCANS_OFFICE_TIME_ZONES", json.dumps(ZONES))
    return tmp_path / "site" / "data"


@pytest.fixture
def raw(tmp_path: Path, openfoodfacts: Path, archive: Path) -> Path:
    root = tmp_path / "raw"
    write_raw(root, "2019/03/01", "old", [backfill_scan("111", scanned_at="2019-03-01T02:00:00+00:00")], "2026-10-01T00:00:00+00:00")
    write_raw(root, "2026/10/18", "a", [
        with_api_key(live_scan("222", time="2026-10-18T16:30:00Z"), "key-bkk"),
        with_api_key(live_scan("111", time="2026-10-18T03:00:00Z", location="thailand:bangkok:rooftop"), "key-bkk"),
        with_api_key(live_scan("333", time="2026-10-18T05:00:00Z", location="japan:tokyo:lobby"), "key-tyo"),
        live_scan("https://qrco.de/bbAote", time="2026-10-19T01:00:00Z"),
    ], "2026-10-19T01:05:00+00:00")
    write_heartbeats(root, "2026/10/19", "h", [
        heartbeat_flat(time="2026-10-19T11:00:00Z", api_key="key-bkk"),
        heartbeat_v2(time="2026-10-19T10:00:00Z", device_name="tokyo-1", location="japan:tokyo:lobby", api_key="key-tyo"),
    ], "2026-10-19T11:05:00+00:00")
    write_food(openfoodfacts, [food("111", names=[("main", "One one one")], brands="Acme", nutriscore="b"), food("333", names=[("en", "Three")], nutriscore="e")])
    write_archive(archive, [("222", "Two from the archive")])
    return root


def test_the_whole_tree_has_every_file_and_what_snackers_build_put_in_them(site: Path, raw: Path) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    # Expected values from Snacker's legacy build on these inputs, before it was deleted (#125).
    locations = ["all", "japan", "japan:tokyo", "japan:tokyo:lobby", "thailand", "thailand:bangkok", "thailand:bangkok:main-kitchen", "thailand:bangkok:rooftop"]
    scanned_at = {
        "111": ["all", "thailand", "thailand:bangkok", "thailand:bangkok:rooftop"],
        "222": ["all", "thailand", "thailand:bangkok", "thailand:bangkok:main-kitchen"],
        "333": ["all", "japan", "japan:tokyo", "japan:tokyo:lobby"],
        "https:%2F%2Fqrco.de%2FbbAote": ["all", "thailand", "thailand:bangkok", "thailand:bangkok:main-kitchen"],
    }
    assert sorted(files_under(site)) == sorted([
        "locations.json", "meta.json",
        *(f"{kind}/by-location/{location}.json" for kind in ("index", "scanners") for location in locations),
        *(f"codes/{code}/product.json" for code in scanned_at),
        *(f"codes/{code}/by-location/{location}.json" for code, where in scanned_at.items() for location in where),
    ])
    index = json.loads((site / "index/by-location/all.json").read_text())
    assert index["daily"] == [{"date": "2019-03-01", "count": 1}, {"date": "2026-10-18", "count": 3}, {"date": "2026-10-19", "count": 1}]
    assert [(row["product"]["code"], row["location"], row["scanned_at"]) for row in index["recent"]] == [
        ("https://qrco.de/bbAote", "thailand:bangkok:main-kitchen", "2026-10-19T01:00:00Z"),
        ("222", "thailand:bangkok:main-kitchen", "2026-10-18T16:30:00Z"),
        ("333", "japan:tokyo:lobby", "2026-10-18T05:00:00Z"),
        ("111", "thailand:bangkok:rooftop", "2026-10-18T03:00:00Z"),
        ("111", "thailand:bangkok", "2019-03-01T02:00:00Z"),
    ]
    scanners = json.loads((site / "scanners/by-location/all.json").read_text())["scanners"]
    assert [(s["name"], s["location"], s["last_seen"], s["last_scan"]["product"]["code"]) for s in scanners] == [
        ("rpi-pico-w-01", "thailand:bangkok:main-kitchen", "2026-10-19T11:00:00Z", "222"),
        ("tokyo-1", "japan:tokyo:lobby", "2026-10-19T10:00:00Z", "333"),
    ]
    product = json.loads((site / "codes/222/product.json").read_text())
    assert (product["known"], product["product"]["name"], product["product"]["name_source"]) == (False, "Two from the archive", "snacker-archive")
    rooftop = json.loads((site / "codes/111/by-location/thailand:bangkok:rooftop.json").read_text())
    assert rooftop["daily"] == [{"date": "2026-10-18", "count": 1}]
    assert [hour["hour"] for hour in rooftop["hourly"] if hour["count"]] == [10]  # 03:00 UTC is 10:00 in Bangkok


def test_a_tree_that_breaks_the_contract_fails_at_site_tree_and_publishes_nothing(
    site: Path, raw: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    merged = site_module.merged

    def without_a_scanners_file(bundles: list[site_module.Bundle]) -> dict[str, Any]:
        tree = merged(bundles)
        del tree["scanners/by-location/all.json"]  # The contract wants one per selectable location.
        return tree

    monkeypatch.setattr(site_module, "merged", without_a_scanners_file)

    with pytest.raises(CheckFailed, match="site_tree"):
        run(defs, defs.bindings("local"), started_at=NOW)

    assert not site.exists()



def test_a_tree_whose_sections_disagree_fails_at_site_tree_and_publishes_nothing(
    site: Path, raw: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    merged = site_module.merged

    def without_one_code_page(bundles: list[site_module.Bundle]) -> dict[str, Any]:
        tree = merged(bundles)
        # Not `all`'s, which the contract requires: Japan's index then counts a scan no code page has.
        del tree["codes/333/by-location/japan.json"]
        return tree

    monkeypatch.setattr(site_module, "merged", without_one_code_page)

    with pytest.raises(CheckFailed, match=r"site_tree.*index/by-location/japan\.json.*2026-10-18"):
        run(defs, defs.bindings("local"), started_at=NOW)

    assert not site.exists()

