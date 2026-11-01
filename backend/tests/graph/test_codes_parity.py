"""Code pages and product files: the values Snacker's legacy build gave them on the same inputs and `now`."""

import json
from typing import Any
from pathlib import Path

import pytest

from snacker.graph.definitions import defs
from stepdag import run
from graph.food_parquet import food, write_archive, write_food
from graph.raw_events import backfill_scan, live_scan, write_raw
from graph.published import files_under
from graph.test_site_parity import NOW, site

__all__ = ["site"]

QR = "https://qrco.de/bbAote"
QUOTED = 'a "quoted" code'


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    write_raw(root, "2019/03/01", "old", [backfill_scan("111", scanned_at="2019-03-01T02:00:00+00:00")], "2026-10-01T00:00:00+00:00")
    write_raw(root, "2026/10/18", "a", [
        live_scan("111", time="2026-10-18T03:00:00Z", location="thailand:bangkok:rooftop"),
        live_scan("222", time="2026-10-18T16:30:00Z"),  # Named from the archive; already the 19th in Bangkok.
        live_scan("333", time="2026-10-18T05:00:00Z", location="japan:tokyo:lobby"),
        live_scan("999", time="2026-10-18T06:00:00Z"),  # Unknown: in neither OpenFoodFacts nor the archive.
        live_scan(QR, time="2026-10-18T07:00:00Z", location="japan:tokyo:lobby"),
        live_scan(QR, time="2026-10-18T08:00:00Z"),
        live_scan(QUOTED, time="2026-10-18T15:30:00Z", location="japan:tokyo:lobby"),  # Already the 19th in Tokyo.
    ], "2026-10-18T16:35:00+00:00")
    return root


@pytest.fixture
def inputs(openfoodfacts: Path, archive: Path) -> tuple[Path, Path]:
    write_food(openfoodfacts, [food("111", names=[("main", "One one one")], brands="Acme", nutriscore="b"), food("333", names=[("en", "Three")])])
    write_archive(archive, [("222", "Two from the archive")])
    return openfoodfacts, archive


def page(site: Path, code: str, location: str) -> dict[str, Any]:
    return dict(json.loads((site / "codes" / code / "by-location" / f"{location}.json").read_text()))


def test_every_code_page_and_product_file_has_what_snackers_build_wrote(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    # Expected values from Snacker's legacy build on these inputs, before it was deleted (#125).
    bangkok = ["all", "thailand", "thailand:bangkok", "thailand:bangkok:main-kitchen"]
    tokyo = ["all", "japan", "japan:tokyo", "japan:tokyo:lobby"]
    scanned_at = {
        "111": ["all", "thailand", "thailand:bangkok", "thailand:bangkok:rooftop"],
        "222": bangkok,
        "333": tokyo,
        "999": bangkok,
        "a%20%22quoted%22%20code": tokyo,
        "https:%2F%2Fqrco.de%2FbbAote": sorted({*bangkok, *tokyo}),
    }
    assert sorted(path for path in files_under(site) if path.startswith("codes/")) == sorted([
        *(f"codes/{code}/product.json" for code in scanned_at),
        *(f"codes/{code}/by-location/{location}.json" for code, where in scanned_at.items() for location in where),
    ])
    one = json.loads((site / "codes/111/product.json").read_text())
    assert (one["known"], one["product"]["name"], one["product"]["brands"], one["product"]["nutri_score"]) == (True, "One one one", "Acme", "B")
    assert json.loads((site / "codes/999/product.json").read_text())["known"] is False
    assert json.loads((site / "codes/222/product.json").read_text())["product"]["name_source"] == "snacker-archive"
    assert page(site, "111", "all")["daily"] == [{"date": "2019-03-01", "count": 1}, {"date": "2026-10-18", "count": 1}]
    qr = page(site, "https:%2F%2Fqrco.de%2FbbAote", "all")
    # One scan at 08:00 UTC in Bangkok (15:00 there), one at 07:00 UTC in Tokyo (16:00 there).
    assert (qr["daily"], [h["hour"] for h in qr["hourly"] if h["count"]]) == ([{"date": "2026-10-18", "count": 2}], [15, 16])
    quoted = page(site, "a%20%22quoted%22%20code", "japan:tokyo")
    assert (quoted["daily"], [h["hour"] for h in quoted["hourly"] if h["count"]]) == ([{"date": "2026-10-19", "count": 1}], [0])


def test_a_code_page_is_written_only_for_locations_where_the_code_was_scanned(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    pages = sorted(p.stem for p in (site / "codes" / "333" / "by-location").iterdir())

    assert pages == ["all", "japan", "japan:tokyo", "japan:tokyo:lobby"]
