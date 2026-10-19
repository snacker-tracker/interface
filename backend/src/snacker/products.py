"""Products: what each scanned code is, taken from the OpenFoodFacts food parquet.

The food parquet is about 8 GB, so products are extracted once into a small table
holding one row per scanned code, and the build reads only that table. Every scanned
code gets a row, which records that it was looked up. A code is a known product when
OpenFoodFacts has it (`known`), even if OpenFoodFacts has no name for it; otherwise it
is an unknown product and its details are null.
"""

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypedDict

import polars as pl

PRODUCTS_SCHEMA = pl.Schema({
    "code": pl.String(),
    "known": pl.Boolean(),
    "name": pl.String(),
    "brands": pl.String(),
    "quantity": pl.String(),
    "categories": pl.List(pl.String()),
    "image_url": pl.String(),
    "off_url": pl.String(),
})

OPENFOODFACTS_PRODUCT_PAGE = "https://world.openfoodfacts.org/product/{code}"
OPENFOODFACTS_IMAGE = "https://images.openfoodfacts.org/images/products/{folder}/{key}.{rev}.{size}.jpg"
IMAGE_SIZE = 400
"""Width class of the image linked from a code page (see docs/adr/0001)."""


def extract_products(food_parquet: Path, codes: Iterable[str]) -> pl.DataFrame:
    """One row per code, in code order; an unknown product's details are null."""
    requested = sorted(set(codes))
    found = (
        pl.scan_parquet(food_parquet)
        .select("code", "product_name", "brands", "quantity", "categories", "lang", "images")
        .filter(pl.col("code").is_in(requested))
        .unique("code", keep="first", maintain_order=True)
        .collect()
    )
    # Only a few hundred rows survive the filter, so each is described in plain Python.
    by_code = {row["code"]: row for row in found.iter_rows(named=True)}
    return pl.DataFrame(
        [describe(by_code[code]) if code in by_code else {"code": code, "known": False} for code in requested],
        schema=PRODUCTS_SCHEMA,
    )


def describe(food_row: dict[str, Any]) -> dict[str, Any]:
    """A products-table row for a code OpenFoodFacts has."""
    code = food_row["code"]
    return {
        "code": code,
        "known": True,
        "name": product_name(food_row["product_name"]),
        "brands": blank_to_none(food_row["brands"]),
        "quantity": blank_to_none(food_row["quantity"]),
        "categories": category_names(food_row["categories"]),
        "image_url": front_image_url(code, food_row["lang"], food_row["images"]),
        "off_url": OPENFOODFACTS_PRODUCT_PAGE.format(code=code),
    }


def product_name(names: list[dict[str, str | None]] | None) -> str | None:
    """The `main` entry of the multilingual `product_name` list, else its first entry."""
    by_lang = {entry["lang"]: blank_to_none(entry["text"]) for entry in reversed(names or [])}
    return by_lang.get("main") or (blank_to_none(names[0]["text"]) if names else None)


def blank_to_none(text: str | None) -> str | None:
    return text if text and text.strip() else None


def category_names(categories: str | None) -> list[str]:
    """`"เครื่องดื่ม, en:Carbonated drinks"` -> `["เครื่องดื่ม", "Carbonated drinks"]`, without repeats."""
    names = (re.sub(r"^[a-z]{2,3}:", "", part.strip()) for part in (categories or "").split(","))
    return list(dict.fromkeys(name for name in names if name))


def front_image_url(code: str, lang: str | None, images: list[dict[str, Any]] | None) -> str | None:
    """The selected front image in the product's language, else English, else any (docs/adr/0001)."""
    fronts = {image["key"]: image["rev"] for image in images or [] if image["key"].startswith("front_")}
    for key in (f"front_{lang}", "front_en", *fronts):
        if fronts.get(key) is not None:
            return OPENFOODFACTS_IMAGE.format(folder=image_folder(code), key=key, rev=fronts[key], size=IMAGE_SIZE)
    return None


def image_folder(code: str) -> str:
    """`8850999220000` -> `885/099/922/0000`: padded to 13 digits, split 3/3/3/rest."""
    padded = code.zfill(13)
    return f"{padded[:3]}/{padded[3:6]}/{padded[6:9]}/{padded[9:]}"


def update_products(
    food_parquet: Path, codes: Iterable[str], products_parquet: Path, *, force: bool = False
) -> bool:
    """Write the products table for `codes`, unless every code was already looked up.

    Returns whether the food parquet was read. Re-extraction covers every code, so
    it also picks up products OpenFoodFacts has learned about since the last run.
    """
    codes = set(codes)
    if not force and products_parquet.exists():
        existing = pl.read_parquet(products_parquet)
        # A table written before a column was added is out of date, whatever codes it has.
        if existing.schema == PRODUCTS_SCHEMA and codes <= set(existing["code"].to_list()):
            return False
    products_parquet.parent.mkdir(parents=True, exist_ok=True)
    extract_products(food_parquet, codes).write_parquet(products_parquet)
    return True


def with_products(scans: pl.DataFrame, products_parquet: Path) -> pl.DataFrame:
    """Attach each scan's product as `product_name`, `product_brands` and `product_known` columns.

    Name and brands are null, and known is false, for unknown products, including codes
    scanned since the last extraction.
    """
    products = pl.read_parquet(products_parquet, columns=PRODUCTS_SCHEMA.names()).select(
        "code",
        pl.col("name").alias("product_name"),
        pl.col("brands").alias("product_brands"),
        pl.col("known").alias("product_known"),
    )
    return scans.join(products, on="code", how="left", maintain_order="left").with_columns(
        pl.col("product_known").fill_null(False)
    )


class Product(TypedDict):
    """What a code page shows about a product (PRD R5)."""

    name: str | None
    brands: str | None
    quantity: str | None
    categories: list[str]
    image_url: str | None
    off_url: str


def known_products(products_parquet: Path) -> dict[str, Product]:
    """Each known product by code; unknown products are left out."""
    products = pl.read_parquet(products_parquet, columns=PRODUCTS_SCHEMA.names())
    return {
        row["code"]: Product(
            name=row["name"],
            brands=row["brands"],
            quantity=row["quantity"],
            categories=row["categories"] or [],
            image_url=row["image_url"],
            off_url=row["off_url"],
        )
        for row in products.filter(pl.col("known")).iter_rows(named=True)
    }

