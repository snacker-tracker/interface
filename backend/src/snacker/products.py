"""Products: what each scanned code is, taken from the OpenFoodFacts food parquet and,
for names OpenFoodFacts lacks, the Snacker archive (GLOSSARY.md).

The food parquet is about 8 GB, so products are extracted once into a small table
holding one row per scanned code, and the build reads only that table. Every scanned
code gets a row, which records that it was looked up. A code is a known product when
OpenFoodFacts has it (`known`), even if OpenFoodFacts has no name for it; otherwise it
is an unknown product and its details are null, apart from a name the archive may give it.
`name_source` says where each name came from.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from snacker.contract import NameSource, Product

PRODUCTS_SCHEMA = pl.Schema({
    "code": pl.String(),
    "known": pl.Boolean(),
    "name": pl.String(),
    "name_source": pl.Enum(["openfoodfacts", "snacker-archive"]),
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


@dataclass(frozen=True)
class Archive:
    """The Snacker archive's product names (see read_archive)."""

    names: dict[str, str]
    """Name by code, for every code with exactly one archive record."""
    duplicated: list[str]
    """Codes with more than one record, in code order; they get no archive name."""


def read_archive(archive_csv: Path) -> Archive:
    """The archive's names: only `name` is used, trimmed. A code recorded more than once
    can't be trusted (short codes were reused for different products), so it is left out."""
    records = pl.read_csv(archive_csv, columns=["code", "name"], infer_schema=False)
    counted = records.group_by("code").agg(pl.len(), pl.col("name").first()).sort("code")
    return Archive(
        names={
            row["code"]: name
            for row in counted.filter(pl.col("len") == 1).iter_rows(named=True)
            if (name := (row["name"] or "").strip())
        },
        duplicated=counted.filter(pl.col("len") > 1)["code"].to_list(),
    )


def extract_products(food_parquet: Path, codes: Iterable[str], *, archive: Archive | None = None) -> pl.DataFrame:
    """One row per code, in code order; an unknown product's details are null.

    A name from OpenFoodFacts wins; the archive only names products OpenFoodFacts can't,
    whether it lacks the product or just its name.
    """
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
    archive_names = archive.names if archive else {}
    return pl.DataFrame(
        [
            named(describe(by_code[code]) if code in by_code else {"code": code, "known": False}, archive_names)
            for code in requested
        ],
        schema=PRODUCTS_SCHEMA,
    )


def named(product: dict[str, Any], archive_names: dict[str, str]) -> dict[str, Any]:
    """The products-table row with its name's source, falling back to the archive's name."""
    source: NameSource | None = "openfoodfacts" if product.get("name") else None
    if source is None and product["code"] in archive_names:
        source = "snacker-archive"
        product = {**product, "name": archive_names[product["code"]]}
    return {**product, "name_source": source}


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
    food_parquet: Path,
    codes: Iterable[str],
    products_parquet: Path,
    *,
    archive: Archive | None = None,
    force: bool = False,
) -> bool:
    """Write the products table for `codes`, unless every code was already looked up.

    Returns whether the food parquet was read. Re-extraction covers every code, so
    it also picks up products OpenFoodFacts has learned about since the last run. The
    archive is frozen, so it is merged only when the table is written.
    """
    codes = set(codes)
    if not force and products_parquet.exists():
        existing = pl.read_parquet(products_parquet)
        # A table written before a column was added is out of date, whatever codes it has.
        if existing.schema == PRODUCTS_SCHEMA and codes <= set(existing["code"].to_list()):
            return False
    products_parquet.parent.mkdir(parents=True, exist_ok=True)
    extract_products(food_parquet, codes, archive=archive).write_parquet(products_parquet)
    return True


def with_products(scans: pl.DataFrame, products_parquet: Path) -> pl.DataFrame:
    """Attach each scan's product as `product_name`, `product_name_source`, `product_brands`
    and `product_known` columns.

    Brands are null, and known is false, for unknown products, including codes scanned
    since the last extraction; the name is null unless the Snacker archive gives one.
    """
    products = pl.read_parquet(products_parquet, columns=PRODUCTS_SCHEMA.names()).select(
        "code",
        pl.col("name").alias("product_name"),
        pl.col("name_source").cast(pl.String()).alias("product_name_source"),
        pl.col("brands").alias("product_brands"),
        pl.col("known").alias("product_known"),
    )
    return scans.join(products, on="code", how="left", maintain_order="left").with_columns(
        pl.col("product_known").fill_null(False)
    )


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

