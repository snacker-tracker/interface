"""Code pages and product files, compared byte for byte with Snacker's own build on the same inputs and `now`."""

import json
from pathlib import Path

import pytest

from snacker.graph.definitions import defs
from stepdag import run
from graph.food_parquet import food, write_archive, write_food
from graph.raw_events import backfill_scan, live_scan, write_raw
from graph.snacker_oracle import differences, files_under, snacker_tree
from graph.test_site_parity import NOW, ZONES, site

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


def code_files(tree: dict[str, bytes]) -> dict[str, bytes]:
    return {path: data for path, data in tree.items() if path.startswith("codes/")}


def test_every_code_page_and_product_file_matches_snackers_build(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    ours = files_under(site)
    theirs = snacker_tree(raw, *inputs, now=NOW, office_time_zones=ZONES)

    assert set(code_files(ours)) == set(code_files(theirs))
    assert "codes/https:%2F%2Fqrco.de%2FbbAote/product.json" in ours
    assert "codes/a%20%22quoted%22%20code/by-location/japan:tokyo.json" in ours
    assert json.loads(ours["codes/999/product.json"])["known"] is False
    assert json.loads(ours["codes/222/product.json"])["product"]["name_source"] == "snacker-archive"
    assert differences(ours, theirs) == []


def test_a_code_page_is_written_only_for_locations_where_the_code_was_scanned(site: Path, raw: Path, inputs: tuple[Path, Path]) -> None:
    run(defs, defs.bindings("local"), started_at=NOW)

    pages = sorted(p.stem for p in (site / "codes" / "333" / "by-location").iterdir())

    assert pages == ["all", "japan", "japan:tokyo", "japan:tokyo:lobby"]
