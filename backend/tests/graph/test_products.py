"""`products`, run by the local executor on fixture raw files, a fixture OpenFoodFacts `food.parquet`
and a fixture Snacker archive.

Snacker's own `extract_products` is the oracle for the rows; the skip-rule tests' values are written
by hand from the fixtures.
"""

from pathlib import Path
from typing import Any

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from snacker.graph.definitions import defs
from snacker.products import PRODUCTS_SCHEMA, extract_products, read_archive
from stepdag import run
from stepdag.assets import Bindings
from graph.food_parquet import food, write_archive, write_food
from graph.raw_events import backfill_scan, live_scan, write_raw


@pytest.fixture
def io(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Bindings:
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))
    return defs.bindings("local")


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    return tmp_path / "raw"


def table(io: Bindings, result: Any, name: str) -> pl.DataFrame:
    pointer = result.pointers[name]
    frame: pl.DataFrame = io[pointer.io_manager].load(pointer).collect()
    return frame


def products(io: Bindings, result: Any) -> list[dict[str, Any]]:
    """The products table's rows without the revision, by code."""
    rows: list[dict[str, Any]] = table(io, result, "products").sort("code").select("code", "known", "name", "brands", "nutri_score").to_dicts()
    return rows


def revision_of_copy(io: Bindings, result: Any) -> str:
    pointer = result.pointers["openfoodfacts_copy"]
    revision: str = io[pointer.io_manager].load(pointer)["revision"]
    return revision


def scan(raw: Path, name: str, *codes: str, day: str = "2026/10/20") -> None:
    """One raw file of live scans of `codes`, a minute apart."""
    events = [live_scan(code, time=f"{day.replace('/', '-')}T03:{i:02d}:00Z") for i, code in enumerate(codes)]
    write_raw(raw, day, name, events, f"{day.replace('/', '-')}T04:00:00+00:00")


CATALOGUE = [
    food("111", names=[("main", "Potato Crisps"), ("th", "มันฝรั่งทอด")], brands="Lay's", nutriscore="b"),
    food("222", names=[("th", "ขนมปังกรอบ"), ("en", "Crackers")], brands="  ", nutriscore="unknown"),
    food("333", names=[("main", "  ")], brands="Oreo", nutriscore="not-applicable"),
    food("444", names=[("main", "Green Tea")], brands="Oishi, Ichitan", nutriscore="E"),
    food("999", names=[("main", "Never Scanned")], brands="Nobody", nutriscore="a"),
]


def test_products_are_the_rows_snackers_extraction_gives_from_the_copy_and_the_archive(io: Bindings, raw: Path, openfoodfacts: Path, archive: Path) -> None:
    write_food(openfoodfacts, [
        *CATALOGUE,
        food(
            "555", names=[("th", "โค๊ก"), ("main", "Coca Cola")], brands="Coke", quantity="325 ml",
            categories="เครื่องดื่ม, en:Carbonated drinks", lang="th", front_images={"front_th": 4, "front_en": 6},
            nutriscore="e", nova_group=4, green_score="a-plus",
        ),
        food("666", names=None, brands="Singha"),
    ])
    write_archive(archive, [("666", "  Singha soda water "), ("777", "Curry paste"), ("888", "Isan sausage"), ("888", "Taro fish snack")])
    scan(raw, "new", "222", "333", "111", "444", "555", "666", "777", "888", "999999")

    rows = table(io, run(defs, io), "products").sort("code")

    expected = extract_products(openfoodfacts, ["111", "222", "333", "444", "555", "666", "777", "888", "999999"], archive=read_archive(archive))
    assert rows.columns == [*PRODUCTS_SCHEMA.names(), "revision"]
    # Delta stores Snacker's Enum columns as text; cast back, the rows are exactly Snacker's.
    assert_frame_equal(rows.drop("revision").cast(PRODUCTS_SCHEMA), expected)
    assert set(expected["name_source"].to_list()) == {"openfoodfacts", "snacker-archive", None}


def test_a_first_run_describes_every_distinct_scanned_code(io: Bindings, raw: Path, openfoodfacts: Path) -> None:
    write_food(openfoodfacts, CATALOGUE)
    write_raw(raw, "2019/03/01", "old", [backfill_scan("111", scanned_at="2019-03-01T02:00:00+00:00")], "2026-10-01T00:00:00+00:00")
    scan(raw, "new", "222", "333", "111", "444", "555")

    result = run(defs, io)

    assert products(io, result) == [
        {"code": "111", "known": True, "name": "Potato Crisps", "brands": "Lay's", "nutri_score": "B"},
        {"code": "222", "known": True, "name": "ขนมปังกรอบ", "brands": None, "nutri_score": None},
        {"code": "333", "known": True, "name": None, "brands": "Oreo", "nutri_score": None},
        {"code": "444", "known": True, "name": "Green Tea", "brands": "Oishi, Ichitan", "nutri_score": "E"},
        {"code": "555", "known": False, "name": None, "brands": None, "nutri_score": None},
    ]
    assert table(io, result, "products")["revision"].to_list() == [revision_of_copy(io, result)] * 5


def test_a_run_with_the_same_revision_and_no_new_codes_skips_products(io: Bindings, raw: Path, openfoodfacts: Path) -> None:
    write_food(openfoodfacts, CATALOGUE)
    scan(raw, "first", "111", "555")
    first = run(defs, io)
    scan(raw, "second", "111", "555", day="2026/10/21")  # More scans, but of codes already described.

    second = run(defs, io, config={"download": True})

    assert "products" in second.skipped
    assert second.pointers["products"] == first.pointers["products"]


def test_a_newly_scanned_code_triggers_re_extraction(io: Bindings, raw: Path, openfoodfacts: Path) -> None:
    write_food(openfoodfacts, CATALOGUE)
    scan(raw, "first", "111")
    run(defs, io)
    scan(raw, "second", "444", day="2026/10/21")

    result = run(defs, io)

    assert "products" in result.computed
    assert products(io, result) == [
        {"code": "111", "known": True, "name": "Potato Crisps", "brands": "Lay's", "nutri_score": "B"},
        {"code": "444", "known": True, "name": "Green Tea", "brands": "Oishi, Ichitan", "nutri_score": "E"},
    ]


def test_a_new_revision_triggers_re_extraction_and_the_rows_record_it(io: Bindings, raw: Path, openfoodfacts: Path) -> None:
    write_food(openfoodfacts, CATALOGUE)
    scan(raw, "first", "111", "555")
    first = revision_of_copy(io, run(defs, io))  # Read now: the JSON IO manager keeps only the latest description.
    # OpenFoodFacts corrects 111's grade and learns 555.
    write_food(openfoodfacts, [food("111", names=[("main", "Potato Crisps")], brands="Lay's", nutriscore="c"), food("555", names=[("en", "Rice Cracker")])])

    result = run(defs, io, config={"download": True})

    assert "products" in result.computed
    assert products(io, result) == [
        {"code": "111", "known": True, "name": "Potato Crisps", "brands": "Lay's", "nutri_score": "C"},
        {"code": "555", "known": True, "name": "Rice Cracker", "brands": None, "nutri_score": None},
    ]
    revision = revision_of_copy(io, result)
    assert revision != first
    assert table(io, result, "products")["revision"].to_list() == [revision, revision]


def test_a_forced_run_re_extracts(io: Bindings, raw: Path, openfoodfacts: Path) -> None:
    write_food(openfoodfacts, CATALOGUE)
    scan(raw, "first", "111")
    run(defs, io)

    result = run(defs, io, select=["products"], force=True)

    assert result.computed == ["products"]
    assert products(io, result) == [{"code": "111", "known": True, "name": "Potato Crisps", "brands": "Lay's", "nutri_score": "B"}]


def names(io: Bindings, result: Any) -> dict[str, tuple[str | None, str | None]]:
    """code -> (name, name source)."""
    rows = table(io, result, "products").select("code", "name", "name_source").to_dicts()
    return {row["code"]: (row["name"], row["name_source"]) for row in rows}


def test_a_product_openfoodfacts_cannot_name_takes_the_archive_name(io: Bindings, raw: Path, openfoodfacts: Path, archive: Path) -> None:
    write_food(openfoodfacts, [food("111", names=[("main", "Potato Crisps")]), food("666", names=None, brands="Singha")])
    write_archive(archive, [("111", "Fashion Vintage Ladies Hot Pants"), ("666", "  Singha soda water "), ("777", "Curry paste")])
    scan(raw, "new", "111", "666", "777")

    assert names(io, run(defs, io)) == {
        "111": ("Potato Crisps", "openfoodfacts"),
        "666": ("Singha soda water", "snacker-archive"),
        "777": ("Curry paste", "snacker-archive"),
    }


def test_a_code_the_archive_lists_twice_gets_no_archive_name(io: Bindings, raw: Path, archive: Path) -> None:
    write_archive(archive, [("5", "Ratatouille à la provençale"), ("5", "Otto coffee maker"), ("152", "Curry paste")])
    scan(raw, "new", "5", "152")

    assert names(io, run(defs, io)) == {"152": ("Curry paste", "snacker-archive"), "5": (None, None)}
