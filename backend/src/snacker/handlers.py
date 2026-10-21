"""The Lambda handlers: one image runs the build or the extraction, chosen by the handler
(aws-deployment ticket 04). Settings come from environment variables."""

import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import boto3
import polars as pl

from snacker.build import ContractBroken, build
from snacker.extraction import OPENFOODFACTS, fetched_table, scanned_codes, signed_hf_url, update_products_at
from snacker.products import PRODUCTS_SCHEMA, covers
from snacker.scans import normalise_scans
from snacker.storage import Bucket, S3Bucket, fetch, s3_location


@dataclass(frozen=True)
class Settings:
    """Where a deployment's inputs and outputs live."""

    raw: str
    """The raw scanner events: s3://<raw bucket>/raw/data/scanner."""
    products: str
    """The products table: s3://<working bucket>/products.parquet."""
    archive: str
    """The Snacker archive: s3://<working bucket>/snacker-archive.csv."""
    site: str
    """The site bucket, s3://<site bucket>; the build writes its data/."""
    food: str
    """OpenFoodFacts: hf://datasets/openfoodfacts/product-database/food.parquet."""
    extract_function: str
    """The extraction function the build starts when the table is missing scanned codes."""

    @classmethod
    def from_env(cls) -> "Settings":
        """The function's settings, from its SNACKER_* environment variables."""
        return cls(
            raw=os.environ["SNACKER_RAW"],
            products=os.environ["SNACKER_PRODUCTS"],
            archive=os.environ["SNACKER_ARCHIVE"],
            site=os.environ["SNACKER_SITE"],
            food=os.environ.get("SNACKER_FOOD", OPENFOODFACTS),
            extract_function=os.environ["SNACKER_EXTRACT_FUNCTION"],
        )


@dataclass(frozen=True)
class BuildRun:
    """What a build run did, returned as the build function's result."""

    uploaded: int
    deleted: int
    extraction_started: bool


def build_handler(event: object, context: object) -> dict[str, object]:
    """The build function: build, publish, and start an extraction if codes are missing."""
    settings = Settings.from_env()

    def start_extraction() -> None:
        # Asynchronous: the extraction takes minutes, and this build has already published.
        boto3.client("lambda").invoke(FunctionName=settings.extract_function, InvocationType="Event")

    try:
        run = handle_build(settings, open_bucket=S3Bucket, start_extraction=start_extraction, now=datetime.now(UTC))
    except ContractBroken as broken:
        for violation in broken.violations[:50]:
            print(f"  {violation}")
        raise
    print(
        f"Published to {settings.site}: uploaded {run.uploaded}, deleted {run.deleted}; "
        f"extraction {'started' if run.extraction_started else 'not needed'}"
    )
    return asdict(run)


def extract_handler(event: object, context: object) -> dict[str, object]:
    """The extraction function: look up the scanned codes the products table lacks."""
    settings = Settings.from_env()
    codes = scanned_codes(settings.raw, S3Bucket)
    update = update_products_at(
        settings.food, codes, settings.products, archive=settings.archive,
        open_bucket=S3Bucket, resolve_hf=signed_hf_url,
    )
    print(f"Looked up {len(codes)} scanned codes: {'wrote' if update.extracted else 'already covered by'} {settings.products}")
    return asdict(update)


def handle_build(
    settings: Settings,
    *,
    open_bucket: Callable[[str], Bucket],
    start_extraction: Callable[[], None],
    now: datetime,
) -> BuildRun:
    """Build from the deployment's inputs and publish to its site bucket, then start an
    extraction if the table is missing any scanned code. Those codes are unknown products in
    this build; a later build reads the new table.
    """
    site = s3_location(settings.site)
    if site is None:
        raise ValueError(f"the site must be an s3:// bucket, not {settings.site}")
    with tempfile.TemporaryDirectory(prefix="snacker-") as scratch:
        raw_dir = fetch(settings.raw, Path(scratch) / "raw", open_bucket)
        products_parquet = fetched_table(settings.products, Path(scratch) / "products", open_bucket)
        if not products_parquet.exists():
            # Before the first extraction every code is an unknown product.
            products_parquet.parent.mkdir(parents=True, exist_ok=True)
            pl.DataFrame(schema=PRODUCTS_SCHEMA).write_parquet(products_parquet)
        published = build(
            raw_dir=raw_dir,
            products_parquet=products_parquet,
            out_dir=Path(scratch) / "out",
            generated_at=now,
            site=open_bucket(site[0]),
        )
        assert published is not None  # a build given a site bucket publishes to it
        table_lacks_codes = not covers(products_parquet, normalise_scans(raw_dir)["code"].unique().to_list())
    if table_lacks_codes:
        start_extraction()
    return BuildRun(uploaded=len(published.uploaded), deleted=len(published.deleted), extraction_started=table_lacks_codes)
