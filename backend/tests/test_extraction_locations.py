"""Tests at the located extraction seam: OpenFoodFacts on Hugging Face, the archive and the
products table in S3 or on disk."""

import io
from pathlib import Path

import polars as pl
import pytest

from fake_bucket import FakeBucket, opener
from food_parquet import food_product, write_food_parquet
from snacker.products import extract_products
from snacker.extraction import update_products_at

FOOD = "hf://datasets/openfoodfacts/product-database/food.parquet"


class Resolver:
    """Stands in for Hugging Face: every hf:// location resolves to one local food parquet."""

    def __init__(self, food_parquet: Path) -> None:
        self.food_parquet = food_parquet
        self.calls: list[str] = []

    def __call__(self, location: str) -> str:
        self.calls.append(location)
        return str(self.food_parquet)


@pytest.fixture
def food(tmp_path: Path) -> Path:
    return write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Singha Soda"}),
        food_product("8851959132012", names={"main": "Coca Cola"}),
    )


def parquet_bytes(table: pl.DataFrame) -> bytes:
    buffer = io.BytesIO()
    table.write_parquet(buffer)
    return buffer.getvalue()


def test_a_table_in_s3_that_covers_every_code_reads_nothing_from_hugging_face(food: Path) -> None:
    working = FakeBucket({"products.parquet": parquet_bytes(extract_products(food, ["8850999220000"]))})
    resolver = Resolver(food)

    update = update_products_at(
        FOOD, ["8850999220000"], "s3://working/products.parquet",
        open_bucket=opener({"working": working}), resolve_hf=resolver,
    )

    assert update.extracted is False
    assert resolver.calls == []
    assert working.calls == []


def test_a_new_code_resolves_hugging_face_once_and_writes_the_table_back_to_s3(food: Path) -> None:
    working = FakeBucket({"products.parquet": parquet_bytes(extract_products(food, ["8850999220000"]))})
    resolver = Resolver(food)

    update = update_products_at(
        FOOD, ["8850999220000", "8851959132012"], "s3://working/products.parquet",
        open_bucket=opener({"working": working}), resolve_hf=resolver,
    )

    assert update.extracted is True
    assert resolver.calls == [FOOD]
    assert working.puts() == ["products.parquet"]
    written = pl.read_parquet(io.BytesIO(working.objects["products.parquet"]))
    assert dict(zip(written["code"], written["name"])) == {"8850999220000": "Singha Soda", "8851959132012": "Coca Cola"}


def test_a_table_not_yet_in_s3_is_extracted_and_written(food: Path) -> None:
    working = FakeBucket()

    update = update_products_at(
        FOOD, ["8851959132012"], "s3://working/products.parquet",
        open_bucket=opener({"working": working}), resolve_hf=Resolver(food),
    )

    assert update.extracted is True
    assert pl.read_parquet(io.BytesIO(working.objects["products.parquet"]))["code"].to_list() == ["8851959132012"]


def test_an_archive_in_s3_names_what_openfoodfacts_cannot_and_its_duplicates_are_reported(food: Path) -> None:
    working = FakeBucket({"snacker-archive.csv": b"code,name\n005,Lays\n006,Pocky\n006,Pringles\n"})

    update = update_products_at(
        FOOD, ["005", "8851959132012"], "s3://working/products.parquet",
        archive="s3://working/snacker-archive.csv",
        open_bucket=opener({"working": working}), resolve_hf=Resolver(food),
    )

    assert update.duplicated == ["006"]
    written = pl.read_parquet(io.BytesIO(working.objects["products.parquet"]))
    assert dict(zip(written["code"], written["name"])) == {"005": "Lays", "8851959132012": "Coca Cola"}


def test_a_covered_run_still_reports_the_archives_duplicated_codes(food: Path) -> None:
    working = FakeBucket({
        "products.parquet": parquet_bytes(extract_products(food, ["8850999220000"])),
        "snacker-archive.csv": b"code,name\n006,Pocky\n006,Pringles\n",
    })

    update = update_products_at(
        FOOD, ["8850999220000"], "s3://working/products.parquet",
        archive="s3://working/snacker-archive.csv",
        open_bucket=opener({"working": working}), resolve_hf=Resolver(food),
    )

    assert update.extracted is False
    assert update.duplicated == ["006"]
