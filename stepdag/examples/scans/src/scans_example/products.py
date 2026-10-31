"""Products: Snacker's extraction (`extract_products`, with the Snacker archive's names) of every
scanned code from a pinned copy of OpenFoodFacts's `food.parquet` (8 GB in full).

The table is Snacker's products schema plus `revision`, the copy's revision the rows came from,
which the skip rule needs; Snacker's own table has no such column.
"""

import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import polars as pl

from snacker.products import PRODUCTS_SCHEMA as SNACKER_PRODUCTS_SCHEMA
from snacker.products import extract_products, read_archive
from snacker.storage import S3Bucket, fetch

PRODUCTS_SCHEMA = pl.Schema({
    **SNACKER_PRODUCTS_SCHEMA,
    "revision": pl.String(),  # the copy's revision the row came from
})


def is_current(previous: pl.LazyFrame, scans: pl.LazyFrame, revision: str) -> bool:
    """Whether `previous` came from this `revision` and already describes every scanned code."""
    stale = previous.filter(pl.col("revision") != revision).select("code").head(1).collect()
    missing = scans.select("code").unique().join(previous.select("code"), on="code", how="anti").head(1).collect()
    return stale.is_empty() and missing.is_empty()


def extract(scans: pl.LazyFrame, copy: dict[str, Any], archive: str) -> pl.DataFrame:
    """One row per distinct scanned code, by Snacker's extraction from the copy `{uri, revision, …}`
    and the archive CSV at `archive` (a path, or an `s3://` URI, downloaded first)."""
    codes = scans.select("code").unique().collect()["code"].to_list()
    if not codes:
        return PRODUCTS_SCHEMA.to_frame()
    with tempfile.TemporaryDirectory(prefix="archive-") as scratch:
        snacker_archive = read_archive(fetch(archive, Path(scratch), S3Bucket))
    products = extract_products(_path(copy["uri"]), codes, archive=snacker_archive)
    return products.with_columns(revision=pl.lit(copy["revision"], pl.String()))


def _path(uri: str) -> str:
    """polars reads `s3://` URIs as they are, but a local file by its path, not its `file://` URI."""
    parsed = urlparse(uri)
    return unquote(parsed.path) if parsed.scheme == "file" else uri
