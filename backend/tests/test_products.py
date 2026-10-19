"""Tests at the product extraction seam: the OpenFoodFacts parquet and scanned codes in, products out."""

from pathlib import Path

import polars as pl

from food_parquet import food_product, write_food_parquet
from snacker.products import extract_products, update_products


def products_by_code(food: Path, codes: list[str]) -> dict[str, dict[str, str | None]]:
    products = extract_products(food, codes)
    return {row["code"]: {"name": row["name"], "brands": row["brands"]} for row in products.to_dicts()}


def test_a_product_is_named_by_its_main_name_with_its_brands(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8851959132012", names={"th": "โค๊ก", "main": "Coca Cola", "en": "Coke"},
                     brands="Coke, coca cola"),
    )

    assert products_by_code(food, ["8851959132012"]) == {
        "8851959132012": {"name": "Coca Cola", "brands": "Coke, coca cola"},
    }


def test_without_a_main_name_the_first_name_is_used(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850269522902", names={"th": "แคบหมู", "en": "Crispy Pork Rinds"}),
    )

    assert products_by_code(food, ["8850269522902"])["8850269522902"]["name"] == "แคบหมู"


def test_a_product_with_no_names_has_no_name(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names=None, brands="Singha"))

    assert products_by_code(food, ["8850999220000"]) == {"8850999220000": {"name": None, "brands": "Singha"}}


def test_when_openfoodfacts_lists_a_code_twice_the_first_listing_wins(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda water"}),
        food_product("8850999220000", names={"main": "Club soda"}),
    )

    assert products_by_code(food, ["8850999220000"])["8850999220000"]["name"] == "Soda water"


def test_only_scanned_codes_are_kept(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda water"}, brands="Singha"),
        food_product("3017620422003", names={"main": "Nutella"}, brands="Ferrero"),
    )

    assert list(products_by_code(food, ["8850999220000"])) == ["8850999220000"]


def test_a_code_openfoodfacts_does_not_know_is_kept_with_no_product(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))

    assert products_by_code(food, ["http://oishidrink.com/m/"]) == {
        "http://oishidrink.com/m/": {"name": None, "brands": None},
    }


def test_empty_brands_count_as_no_brands(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8858702410304", names={"main": "Big folly"}, brands=""),
    )

    assert products_by_code(food, ["8858702410304"])["8858702410304"]["brands"] is None


def test_products_are_written_the_first_time(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))
    products = tmp_path / "products.parquet"

    assert update_products(food, ["8850999220000", "005"], products) is True
    assert pl.read_parquet(products)["code"].to_list() == ["005", "8850999220000"]


def test_the_food_file_is_not_read_again_when_every_code_was_already_looked_up(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))
    products = tmp_path / "products.parquet"
    update_products(food, ["8850999220000", "005"], products)

    # A missing food file proves it isn't opened.
    assert update_products(tmp_path / "gone.parquet", ["005", "8850999220000"], products) is False


def test_a_newly_scanned_code_triggers_a_fresh_extraction(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda water"}),
        food_product("8851959132012", names={"main": "Coca Cola"}),
    )
    products = tmp_path / "products.parquet"
    update_products(food, ["8850999220000"], products)

    assert update_products(food, ["8850999220000", "8851959132012"], products) is True
    assert pl.read_parquet(products)["name"].to_list() == ["Soda water", "Coca Cola"]


def test_forcing_extracts_again_even_when_nothing_is_new(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda"}))
    products = tmp_path / "products.parquet"
    update_products(food, ["8850999220000"], products)
    write_food_parquet(food, food_product("8850999220000", names={"main": "Soda water"}))

    assert update_products(food, ["8850999220000"], products, force=True) is True
    assert pl.read_parquet(products)["name"].to_list() == ["Soda water"]
