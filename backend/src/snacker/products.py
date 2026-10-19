"""Products: what each scanned code is, taken from the OpenFoodFacts food parquet.

The food parquet is about 8 GB, so products are extracted once into a small table
holding one row per scanned code, and the build reads only that table. Codes
OpenFoodFacts doesn't know are kept with no name or brands, which records that they
were looked up (and shows them as unknown products).
"""

from collections.abc import Iterable
from pathlib import Path

import polars as pl

PRODUCTS_SCHEMA = pl.Schema({
    "code": pl.String(),
    "name": pl.String(),
    "brands": pl.String(),
})


def extract_products(food_parquet: Path, codes: Iterable[str]) -> pl.DataFrame:
    """One row per code, in code order; name and brands are null when the code is unknown."""
    requested = pl.DataFrame({"code": sorted(set(codes))}, schema={"code": pl.String()})
    found = (
        pl.scan_parquet(food_parquet)
        .select("code", "product_name", "brands")
        .filter(pl.col("code").is_in(requested["code"].implode()))
        .select(
            "code",
            product_name().alias("name"),
            blank_as_null(pl.col("brands")).alias("brands"),
        )
        .unique("code", keep="first", maintain_order=True)
        .collect()
    )
    return requested.join(found, on="code", how="left").select(PRODUCTS_SCHEMA.names())


def product_name() -> pl.Expr:
    """The `main` entry of the multilingual `product_name` list, else its first entry."""
    names = pl.col("product_name")
    main = names.list.eval(
        pl.element().filter(pl.element().struct.field("lang") == "main").struct.field("text")
    ).list.first()
    first = names.list.first().struct.field("text")
    return pl.coalesce(blank_as_null(main), blank_as_null(first))


def blank_as_null(text: pl.Expr) -> pl.Expr:
    return pl.when(text.str.strip_chars() == "").then(None).otherwise(text)


def update_products(
    food_parquet: Path, codes: Iterable[str], products_parquet: Path, *, force: bool = False
) -> bool:
    """Write the products table for `codes`, unless every code was already looked up.

    Returns whether the food parquet was read. Re-extraction covers every code, so
    it also picks up products OpenFoodFacts has learned about since the last run.
    """
    codes = set(codes)
    if not force and products_parquet.exists():
        looked_up = set(pl.read_parquet(products_parquet, columns=["code"])["code"].to_list())
        if codes <= looked_up:
            return False
    products_parquet.parent.mkdir(parents=True, exist_ok=True)
    extract_products(food_parquet, codes).write_parquet(products_parquet)
    return True


def with_products(scans: pl.DataFrame, products_parquet: Path) -> pl.DataFrame:
    """Attach each scan's product as `product_name` and `product_brands` columns.

    Both are null for unknown products, including codes scanned since the last extraction.
    """
    products = pl.read_parquet(products_parquet, columns=PRODUCTS_SCHEMA.names()).select(
        "code",
        pl.col("name").alias("product_name"),
        pl.col("brands").alias("product_brands"),
    )
    return scans.join(products, on="code", how="left", maintain_order="left")
