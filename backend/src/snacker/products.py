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
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_args
from urllib.parse import unquote, urlparse

import polars as pl

from snacker.contract import GreenScore, NameSource, NovaGroup, NutriScore, Product, ProductFile
from snacker.scans import SCANS_SCHEMA
from snacker.storage import S3Bucket, fetch

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
    "nutri_score": pl.Enum(get_args(NutriScore)),
    "nova_group": pl.Int8(),
    "green_score": pl.Enum(get_args(GreenScore)),
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


def extract_products(food_parquet: Path | str, codes: Iterable[str], *, archive: Archive | None = None) -> pl.DataFrame:
    """One row per code, in code order; an unknown product's details are null.

    A name from OpenFoodFacts wins; the archive only names products OpenFoodFacts can't,
    whether it lacks the product or just its name.
    """
    requested = sorted(set(codes))
    found = (
        pl.scan_parquet(food_parquet)
        .select(
            "code", "product_name", "brands", "quantity", "categories", "lang", "images",
            "nutriscore_grade", "nova_group", "environmental_score_grade",
        )
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
        "nutri_score": grade(food_row["nutriscore_grade"], get_args(NutriScore)),
        "nova_group": grade(food_row["nova_group"], get_args(NovaGroup)),
        "green_score": grade(food_row["environmental_score_grade"], get_args(GreenScore)),
    }


def grade[G: (str, int)](value: str | int | None, scale: tuple[G, ...]) -> G | None:
    """`"b"` -> `"B"` and `"a-plus"` -> `"A+"` on its scale; anything off the scale ("unknown",
    "not-applicable") is no grade."""
    value = value.upper().replace("-PLUS", "+") if isinstance(value, str) else value
    return next((step for step in scale if step == value), None)


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
    food_parquet: Path | str,
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
    if not force and covers(products_parquet, codes):
        return False
    products_parquet.parent.mkdir(parents=True, exist_ok=True)
    extract_products(food_parquet, codes, archive=archive).write_parquet(products_parquet)
    return True


def covers(products_parquet: Path, codes: Iterable[str]) -> bool:
    """Whether a products table exists and already looked up every code."""
    if not products_parquet.exists():
        return False
    existing = pl.read_parquet(products_parquet)
    # A table written before a column was added is out of date, whatever codes it has.
    return existing.schema == PRODUCTS_SCHEMA and set(codes) <= set(existing["code"].to_list())


SCANNED_PRODUCT = pl.Struct({
    "code": pl.String(),
    "name": pl.String(),
    "name_source": pl.String(),
    "brands": pl.String(),
    "known": pl.Boolean(),
    "nutri_score": pl.String(),
})
"""A scan's `product` column: its scanned product (GLOSSARY.md), as the scan lists show it."""


def with_products(scans: pl.DataFrame, products_parquet: Path) -> pl.DataFrame:
    """Attach each scan's scanned product as a `product` column (SCANNED_PRODUCT).

    Brands are null, and known is false, for unknown products, including codes scanned
    since the last extraction; the name is null unless the Snacker archive gives one.
    The scan's own `code` column stays, for joining and grouping, and goes into the struct too.
    """
    # Every field but the code comes from the products table, by the same name.
    looked_up = [name for name in SCANNED_PRODUCT.to_schema() if name != "code"]
    products = pl.read_parquet(products_parquet, columns=["code", *looked_up])
    joined = scans.join(products, on="code", how="left", maintain_order="left")
    # Built last, from plain columns: Polars can panic on `when/then` over a field of a
    # struct made of several chunks (see polars_multichunk_struct_when_panic.py).
    filled = {"known": pl.col("known").fill_null(False)}
    product = pl.struct([
        filled.get(name, pl.col(name)).cast(dtype).alias(name) for name, dtype in SCANNED_PRODUCT.to_schema().items()
    ])
    return joined.with_columns(product.alias("product")).drop(looked_up)


def product_files(products_parquet: Path) -> dict[str, ProductFile]:
    """Each looked-up code's product file. The product is null when neither OpenFoodFacts
    nor the Snacker archive has the code; codes scanned since the last extraction are left out."""
    products = pl.read_parquet(products_parquet, columns=PRODUCTS_SCHEMA.names())
    return {
        row["code"]: ProductFile(
            code=row["code"],
            known=row["known"],
            product=Product(
                name=row["name"],
                name_source=row["name_source"],
                brands=row["brands"],
                quantity=row["quantity"],
                categories=row["categories"] or [],
                image_url=row["image_url"],
                off_url=row["off_url"],
                nutri_score=row["nutri_score"],
                nova_group=row["nova_group"],
                green_score=row["green_score"],
            ) if row["known"] or row["name"] else None,
        )
        for row in products.iter_rows(named=True)
    }



# The products table: the products parquet, extracted from a pinned copy of OpenFoodFacts's
# food parquet (`snacker.openfoodfacts`), plus the copy's revision the rows came from. It's
# stored as a Delta table, which keeps Enums as text; `write_parquet` restores them.

PRODUCTS_TABLE_SCHEMA = pl.Schema({
    **PRODUCTS_SCHEMA,
    "revision": pl.String(),  # the copy's revision the row came from
})


def is_current(table: pl.LazyFrame, scans: pl.LazyFrame, revision: str) -> bool:
    """Whether the products `table` came from this `revision` and already describes every scanned code."""
    stale = table.filter(pl.col("revision") != revision).select("code").head(1).collect()
    missing = scans.select("code").unique().join(table.select("code"), on="code", how="anti").head(1).collect()
    return stale.is_empty() and missing.is_empty()


def extract_from_copy(scans: pl.LazyFrame, copy: dict[str, Any], archive: str) -> pl.DataFrame:
    """One row per distinct scanned code (PRODUCTS_TABLE_SCHEMA), by `extract_products` from the copy
    `{uri, revision, …}` and the archive CSV at `archive` (a path, or an `s3://` URI, downloaded first)."""
    codes = scans.select("code").unique().collect()["code"].to_list()
    if not codes:
        return PRODUCTS_TABLE_SCHEMA.to_frame()
    with tempfile.TemporaryDirectory(prefix="archive-") as scratch:
        snacker_archive = read_archive(fetch(archive, Path(scratch), S3Bucket))
    products = extract_products(_local_path(copy["uri"]), codes, archive=snacker_archive)
    return products.with_columns(revision=pl.lit(copy["revision"], pl.String()))


def _local_path(uri: str) -> str:
    """polars reads `s3://` URIs as they are, but a local file by its path, not its `file://` URI."""
    parsed = urlparse(uri)
    return unquote(parsed.path) if parsed.scheme == "file" else uri


def write_parquet(table: pl.LazyFrame, path: Path) -> Path:
    """Write the products `table` as the products parquet (PRODUCTS_SCHEMA, its Enums restored), for
    the functions that read one."""
    table.select(PRODUCTS_SCHEMA.names()).collect().cast(PRODUCTS_SCHEMA).write_parquet(path)
    return path


def described_from_table(table: pl.LazyFrame) -> pl.DataFrame:
    """Scans described by `with_products`, from a table that keeps Enums as text, with their types
    restored."""
    return table.collect().cast(pl.Schema({**dict(SCANS_SCHEMA.items()), "product": SCANNED_PRODUCT}))
