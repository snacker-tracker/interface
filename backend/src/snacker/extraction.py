"""Product extraction with its inputs and output wherever they live: OpenFoodFacts on Hugging
Face or disk, the Snacker archive and the products table in S3 or on disk."""

import http.client
import os
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin

import polars as pl

from snacker.event_cache import load_scans
from snacker.products import covers, read_archive, update_products
from snacker.storage import Bucket, fetch, s3_location

HF_SCHEME = "hf://"
OPENFOODFACTS = "hf://datasets/openfoodfacts/product-database/food.parquet"
"""The OpenFoodFacts food parquet on Hugging Face, always the latest data."""
HF_HOST = "huggingface.co"
REDIRECTS = {301, 302, 303, 307, 308}
PARQUET_CONTENT_TYPE = "application/vnd.apache.parquet"


@dataclass(frozen=True)
class ProductsUpdate:
    """What an extraction run did."""

    extracted: bool
    """Whether OpenFoodFacts was read and the table written; not when it already covered every code."""
    duplicated: list[str] = field(default_factory=list)
    """The archive's codes recorded more than once, which get no archive name."""
    named: dict[str, int] = field(default_factory=dict)
    """How many products each name source named, when the table was written."""


def update_products_at(
    food: str,
    codes: Iterable[str],
    products: str,
    *,
    archive: str | None = None,
    force: bool = False,
    open_bucket: Callable[[str], Bucket],
    resolve_hf: Callable[[str], str],
) -> ProductsUpdate:
    """`update_products` for locations: `food` is a path or hf:// (resolved only if the table
    must be written), and `products` and `archive` are paths or s3:// URIs.
    """
    codes = set(codes)
    s3_products = s3_location(products)
    with tempfile.TemporaryDirectory(prefix="snacker-") as scratch:
        snacker_archive = read_archive(fetch(archive, Path(scratch) / "archive", open_bucket)) if archive else None
        duplicated = snacker_archive.duplicated if snacker_archive else []
        local_products = fetched_table(products, Path(scratch) / "products", open_bucket)
        if not force and covers(local_products, codes):
            return ProductsUpdate(extracted=False, duplicated=duplicated)
        food_parquet = resolve_hf(food) if food.startswith(HF_SCHEME) else food
        update_products(food_parquet, codes, local_products, archive=snacker_archive, force=True)
        sources = pl.read_parquet(local_products)["name_source"].drop_nulls().value_counts()
        named = dict(zip(sources["name_source"].cast(pl.String).to_list(), sources["count"].to_list()))
        if s3_products is not None:
            bucket_name, key = s3_products
            open_bucket(bucket_name).put(
                key, local_products.read_bytes(), content_type=PARQUET_CONTENT_TYPE, cache_control="no-cache"
            )
    return ProductsUpdate(extracted=True, duplicated=duplicated, named=named)


def scanned_codes(
    raw: str, open_bucket: Callable[[str], Bucket], *, cache: str | None = None, version: str | None = None
) -> list[str]:
    """Every scanned code in the raw events, a path or an s3:// prefix, read through the scans
    cache if there is one. Only the build writes the cache, so this never does (ADR 0011)."""
    scans = load_scans(raw, cache=cache, version=version, open_bucket=open_bucket, save=False)
    return scans["code"].unique().to_list()


def fetched_table(products: str, local_dir: Path, open_bucket: Callable[[str], Bucket]) -> Path:
    """Where to read and write the products table locally; a table not in S3 yet is a
    local path that doesn't exist, as for a first local extraction."""
    try:
        return fetch(products, local_dir, open_bucket)
    except FileNotFoundError:
        return local_dir / PurePosixPath(products).name


def signed_hf_url(location: str) -> str:
    """The signed CDN URL that `hf://<datasets|models>/<org>/<repo>/<file>` redirects to.

    Polars' own hf:// reads send every range request through Hugging Face's resolver, whose
    anonymous quota (3,000 per 5 minutes) one scan of the food parquet exceeds; scanning the
    signed URL takes one resolver request (aws-deployment ticket 01). HF_TOKEN, if set, is sent.
    """
    kind, org, repo, file = location.removeprefix(HF_SCHEME).split("/", 3)
    headers = {"Authorization": f"Bearer {token}"} if (token := os.environ.get("HF_TOKEN")) else {}
    connection = http.client.HTTPSConnection(HF_HOST, timeout=60)
    try:
        connection.request("HEAD", f"/{kind}/{org}/{repo}/resolve/main/{file}", headers=headers)
        reply = connection.getresponse()
        signed = reply.getheader("Location")
        if reply.status not in REDIRECTS or signed is None:
            raise RuntimeError(f"{location}: Hugging Face replied {reply.status} {reply.reason}, not a redirect")
    finally:
        connection.close()
    return urljoin(f"https://{HF_HOST}/", signed)
