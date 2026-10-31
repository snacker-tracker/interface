"""Snacker's backend as a stepdag graph: raw scanner events into Delta tables and the site's data
tree (the stepdag scans example until #118).

stepdag has no way to give an asset an outside resource, so the raw events' location comes from
`$SCANS_RAW` (a directory, or `s3://bucket/prefix/`), and the tables' root from `$SCANS_TABLES`.
"""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from snacker import heartbeats as heartbeats_module
from snacker import products as products_module
from snacker import scans as scans_module
from snacker import sections
from snacker.graph import parity as parity_module
from snacker.graph.checks import every_scan_has_a_code_and_a_time, keeps_the_contract
from snacker.graph.delta_io import DeltaIO, Merge
from snacker.graph.site_io import SiteIO
from snacker.openfoodfacts import files_at, openfoodfacts_source
from snacker.raw import RawEvents
from stepdag import UNCHANGED, Definitions, RunContext, asset
from stepdag.assets import Bindings
from stepdag.json_io import DirectoryStore, FixedJson, RunJson, S3Store, Store


@asset(io_manager="delta", memory=2048, timeout=300, checks=[every_scan_has_a_code_and_a_time])
def scans(*, previous: pl.LazyFrame | None) -> Any:
    """Every scan in the raw events, from both eras, by Snacker's normaliser, loaded incrementally
    by ADR 0011's rule.

    With no table yet, or in a forced run (`previous` is None), every raw scan file is read.
    Otherwise the watermark is the newest source last-modified time in the table. Listing starts
    at the day folder before it, and only files modified after the watermark minus 15 minutes are
    read: Firehose can write a file after a later-named one. Scans already in the table are dropped,
    so the merge on event ID receives only new ones, and a run that finds none is skipped.
    """
    new = scans_module.new_scans(RawEvents.at(os.environ["SCANS_RAW"]), previous)
    return UNCHANGED if new is None else new


@asset(io_manager="fixed_json", memory=1024, timeout=900)
def openfoodfacts_copy(*, previous: dict[str, Any] | None, context: RunContext) -> Any:
    """OpenFoodFacts's `food.parquet`, copied from `$SCANS_OPENFOODFACTS` (`hf`, or a local file) into
    `$SCANS_FILES`, under a key named after its revision so a copy never changes under a reader.

    Copies when there's no copy yet (or it has expired), when the run config asks for a download
    and the revision is new, or in a forced run (where `previous` is None). An ordinary run never
    copies 8 GB.
    """
    source = openfoodfacts_source(os.environ["SCANS_OPENFOODFACTS"])
    files = files_at(os.environ["SCANS_FILES"])
    if previous is not None and files.exists(previous["uri"]):
        if not context.config.get("download") or source.revision() == previous["revision"]:
            return UNCHANGED
    revision = source.revision()
    stream = source.open()
    try:
        uri, size = files.upload(f"openfoodfacts/{revision}/food.parquet", stream)
    finally:
        stream.close()
    return {"uri": uri, "revision": revision, "bytes": size, "copied_at": datetime.now(UTC).isoformat()}


@asset(deps=["scans", "openfoodfacts_copy"], io_manager="delta", memory=3008, timeout=900)
def products(scans: pl.LazyFrame, copy: dict[str, Any], *, previous: pl.LazyFrame | None) -> Any:
    """Snacker's extraction of every scanned code, known or not, from OpenFoodFacts's copy and the
    Snacker archive at `$SCANS_ARCHIVE` (a path, or an `s3://` URI).

    Extracts every scanned code again when there's no table yet or in a forced run (`previous` is
    None), when the copy's revision isn't the one the table came from, or when a scanned code is
    missing from the table. Otherwise skipped, so an ordinary run doesn't scan 8 GB.
    """
    if previous is not None and products_module.is_current(previous, scans, copy["revision"]):
        return UNCHANGED
    return products_module.extract_from_copy(scans, copy, os.environ["SCANS_ARCHIVE"])


def _json_store(tables: str) -> Store:
    """The JSON IO manager's objects live beside the tables, under `json/`."""
    if tables.startswith("s3://"):
        import boto3

        bucket, _, prefix = tables.removeprefix("s3://").partition("/")
        return S3Store(boto3.client("s3"), bucket, f"{prefix.rstrip('/')}/json/".lstrip("/"))
    return DirectoryStore(os.path.join(tables, "json"))


def bindings() -> Bindings:
    """The same everywhere: `$SCANS_TABLES` is a directory locally and `s3://…` in Lambda, where
    deltalake writes safely without a lock (S3 conditional writes) and takes credentials from the
    environment."""
    tables = os.environ["SCANS_TABLES"]
    return {
        "delta": DeltaIO(
            tables,
            merges={
                "scans": Merge(keys=["event_id"]),
                # Only a newer heartbeat replaces a scanner's row, even if an overlapping run merged first.
                "heartbeats": Merge(keys=["scanner"], update_when="s.sent_at > t.sent_at"),
            },
        ),
        "fixed_json": FixedJson(_json_store(tables)),
        "run_json": RunJson(_json_store(tables)),
        "site": SiteIO(os.environ["SCANS_SITE"]),
    }


@asset(deps=["scans", "products"], io_manager="delta", memory=1024, timeout=300)
def scanned(scans: pl.LazyFrame, products: pl.LazyFrame) -> pl.DataFrame:
    """Every scan with its office time zone and scanned product, as Snacker's build describes them.
    A location with no office time zone fails here, as it stops Snacker's build."""
    snacker = scans_module.from_table(scans)
    with tempfile.TemporaryDirectory() as scratch:
        products_parquet = products_module.write_parquet(products, Path(scratch) / "products.parquet")
        return products_module.with_products(sections.locations_of(snacker).with_office_time_zones(snacker), products_parquet)


@asset(deps=["scanned"], io_manager="run_json")
def locations_file(scanned: pl.LazyFrame) -> sections.Bundle:
    """`locations.json`: every selectable location."""
    return sections.locations_file(scanned)


# The index sections. Every period ends at the run's start time, as at Snacker's single `now`.


@asset(deps=["scanned"], io_manager="run_json")
def top_scans(scanned: pl.LazyFrame, *, context: RunContext) -> sections.Bundle:
    """Each index file's `location` and `top_scans`, for every selectable location."""
    return sections.top_scans_section(scanned, datetime.fromisoformat(context.started_at))


@asset(deps=["scanned"], io_manager="run_json")
def top_unknown_scans(scanned: pl.LazyFrame, *, context: RunContext) -> sections.Bundle:
    """Each index file's `top_unknown_scans`."""
    return sections.top_unknown_scans_section(scanned, datetime.fromisoformat(context.started_at))


@asset(deps=["scanned"], io_manager="run_json")
def healthiest_and_least_healthy(scanned: pl.LazyFrame, *, context: RunContext) -> sections.Bundle:
    """Each index file's `healthiest_and_least_healthy`."""
    return sections.healthiest_and_least_healthy_section(scanned, datetime.fromisoformat(context.started_at))


@asset(deps=["scanned"], io_manager="run_json")
def nutri_score_distribution(scanned: pl.LazyFrame, *, context: RunContext) -> sections.Bundle:
    """Each index file's `nutri_score_distribution`."""
    return sections.nutri_score_distribution_section(scanned, datetime.fromisoformat(context.started_at))


@asset(deps=["scanned"], io_manager="run_json")
def period_days(scanned: pl.LazyFrame, *, context: RunContext) -> sections.Bundle:
    """Each index file's `period_days`."""
    return sections.period_days_section(scanned, datetime.fromisoformat(context.started_at))


@asset(deps=["scanned"], io_manager="run_json")
def daily_and_recent(scanned: pl.LazyFrame) -> sections.Bundle:
    """Each index file's `daily` and `recent` scans."""
    return sections.daily_and_recent_section(scanned)


@asset(deps=["scanned"], io_manager="run_json", memory=1024, timeout=300)
def code_pages(scanned: pl.LazyFrame) -> sections.Bundle:
    """Each scanned code's daily, hourly and recent scans, for every selectable location where it was scanned."""
    return sections.code_pages(scanned)


@asset(deps=["scanned", "products"], io_manager="run_json")
def product_files(scanned: pl.LazyFrame, products: pl.LazyFrame) -> sections.Bundle:
    """Each scanned code's product file, with unknown products marked as such."""
    return sections.product_files(scanned, products)


# A forced run reads every heartbeat file (about 12k): the default 60 s isn't enough.
@asset(io_manager="delta", memory=1024, timeout=900)
def heartbeats(*, previous: pl.LazyFrame | None) -> Any:
    """Each scanner's latest heartbeat, by Snacker's normaliser, loaded incrementally by `scans`'
    watermark rule over the heartbeats folder (everything with no table, or in a forced run).
    Only heartbeats newer than a scanner's row are returned; a run that finds none is skipped."""
    new = heartbeats_module.new_latest_heartbeats(RawEvents.at(os.environ["SCANS_RAW"]), previous)
    return UNCHANGED if new is None else new


@asset(deps=["heartbeats", "scanned"], io_manager="run_json")
def scanners(heartbeats: pl.LazyFrame, scanned: pl.LazyFrame) -> sections.Bundle:
    """Every selectable location's scanners file, each scanner with its last scan by API key (ADR 0002)."""
    return sections.scanners_files(heartbeats, scanned)


@asset(
    deps=[
        "locations_file",
        "top_scans",
        "top_unknown_scans",
        "healthiest_and_least_healthy",
        "nutri_score_distribution",
        "period_days",
        "daily_and_recent",
        "code_pages",
        "product_files",
        "scanners",
    ],
    io_manager="site",
    checks=[keeps_the_contract],
    # Stages the tree twice (the contract check, then publishing) and diff-publishes about 3,500 files.
    memory=2048,
    timeout=600,
)
def site_tree(
    locations: sections.Bundle,
    top_scans: sections.Bundle,
    top_unknown_scans: sections.Bundle,
    healthiest_and_least_healthy: sections.Bundle,
    nutri_score_distribution: sections.Bundle,
    period_days: sections.Bundle,
    daily_and_recent: sections.Bundle,
    code_pages: sections.Bundle,
    product_files: sections.Bundle,
    scanners: sections.Bundle,
    *,
    context: RunContext,
) -> dict[str, Any]:
    """The whole site data tree: `meta.json`, then every section's bundle, merged into files.
    (stepdag passes parents positionally and counts them, so each section is its own parameter.)
    The index sections come in `IndexFile`'s key order, which the merge keeps in each index file."""
    return sections.merged([
        sections.meta(datetime.fromisoformat(context.started_at)),
        locations,
        top_scans,
        top_unknown_scans,
        healthiest_and_least_healthy,
        nutri_score_distribution,
        period_days,
        daily_and_recent,
        code_pages,
        product_files,
        scanners,
    ])


# Runs Snacker's whole build, then reads every published file (about 3,500) back.
@asset(deps=["site_tree", "scans", "heartbeats", "products"], io_manager="run_json", memory=2048, timeout=600)
def parity(
    published: dict[str, bytes], scans: pl.LazyFrame, heartbeats: pl.LazyFrame, products: pl.LazyFrame, *, context: RunContext
) -> dict[str, Any]:
    """Snacker's own build on this run's inputs and start time, diffed with what `site_tree` published.
    A difference is recorded, never a failure, so the shadow site keeps updating while it's investigated."""
    now = datetime.fromisoformat(context.started_at)
    snackers = parity_module.snackers_tree(scans_module.from_table(scans), heartbeats_module.from_table(heartbeats), products, now)
    return parity_module.report(published, snackers)


defs = Definitions(
    [
        scans,
        openfoodfacts_copy,
        products,
        scanned,
        locations_file,
        top_scans,
        top_unknown_scans,
        healthiest_and_least_healthy,
        nutri_score_distribution,
        period_days,
        daily_and_recent,
        code_pages,
        product_files,
        heartbeats,
        scanners,
        site_tree,
        parity,
    ],
    environments={"local": bindings, "lambda": bindings},
)
