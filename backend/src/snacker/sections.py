"""The site's data tree, built in sections and merged into files (PRD.md §7).

A section is a bundle, `{site path: contract file or fragment}`, with each path relative to the
site's `data/`. A whole file, such as a code page, is in one section. An index file is made of
fragments, one per section, each holding some of `IndexFile`'s keys; `merged` joins them, in
section order, which keeps `IndexFile`'s key order.

Each section is built from `scanned`, every scan described with its office time zone and scanned
product (`snacker.products.with_products`), as a table that keeps Enums as text.

The legacy build (`snacker.build.write_data`) builds the same tree in one pass; it's kept
unchanged, as the parity reference, until the switchover (#117).
"""

import tempfile
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from snacker.config import RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT, office_time_zones
from snacker.contract import (
    CONTRACT_VERSION,
    CodeScansFile,
    LocationsFile,
    MetaFile,
    ProductFile,
    ScannersFile,
    SelectableLocation,
    code_scans_path,
    index_path,
    locations_path,
    meta_path,
    product_path,
    scanners_path,
    write_json,
)
from snacker.heartbeats import from_table as heartbeats_from_table
from snacker.heartbeats import latest_heartbeats, scanner_statuses
from snacker.locations import Locations
from snacker.products import described_from_table, write_parquet
from snacker.products import product_files as products_by_code
from snacker.scan_summary import healthiest_and_least_healthy, nutri_score_distribution, period_days, summarise, top_scans
from snacker.timestamps import format_utc

Bundle = dict[str, Any]
Fragment = Callable[[str, pl.DataFrame], dict[str, Any]]


def locations_of(scans: pl.DataFrame) -> Locations:
    return Locations.from_scans(scans, office_time_zones())


def meta(generated_at: datetime) -> Bundle:
    """`meta.json`."""
    return {meta_path().as_posix(): MetaFile(generated_at=format_utc(generated_at), contract_version=CONTRACT_VERSION)}


def locations_file(scanned: pl.LazyFrame) -> Bundle:
    """`locations.json`: every selectable location."""
    locations = locations_of(described_from_table(scanned))
    return {locations_path().as_posix(): LocationsFile(locations=[SelectableLocation(id=loc) for loc in locations.selectable()])}


# The index files' sections. Every period ends at `now`, the build's start time.


def index_bundle(scanned: pl.LazyFrame, fragment: Fragment) -> Bundle:
    """`fragment(location, scans within it)` for every selectable location, by its index file's path."""
    described = described_from_table(scanned)
    locations = locations_of(described)
    return {
        index_path(location).as_posix(): fragment(location, locations.within(described, location))
        for location in locations.selectable()
    }


def top_scans_section(scanned: pl.LazyFrame, now: datetime) -> Bundle:
    """The index file's `location` (its first key) and `top_scans`."""
    return index_bundle(scanned, lambda location, scans: {
        "location": location,
        "top_scans": top_scans(scans, limit=TOP_SCANS_LIMIT, now=now),
    })


def top_unknown_scans_section(scanned: pl.LazyFrame, now: datetime) -> Bundle:
    return index_bundle(scanned, lambda _, scans: {
        "top_unknown_scans": top_scans(scans, limit=TOP_SCANS_LIMIT, now=now, unknown_only=True),
    })


def healthiest_and_least_healthy_section(scanned: pl.LazyFrame, now: datetime) -> Bundle:
    return index_bundle(scanned, lambda _, scans: {
        "healthiest_and_least_healthy": healthiest_and_least_healthy(scans, limit=TOP_SCANS_LIMIT, now=now),
    })


def nutri_score_distribution_section(scanned: pl.LazyFrame, now: datetime) -> Bundle:
    return index_bundle(scanned, lambda _, scans: {"nutri_score_distribution": nutri_score_distribution(scans, now=now)})


def period_days_section(scanned: pl.LazyFrame, now: datetime) -> Bundle:
    return index_bundle(scanned, lambda _, scans: {"period_days": period_days(scans, now=now)})


def daily_and_recent_section(scanned: pl.LazyFrame) -> Bundle:
    """The index's `daily` and `recent` from the scan summary (its `hourly` is only for code files)."""

    def fragment(_: str, scans: pl.DataFrame) -> dict[str, Any]:
        summary = summarise(scans, recent_limit=RECENT_SCANS_LIMIT)
        return {"daily": summary.daily, "recent": summary.recent}

    return index_bundle(scanned, fragment)


# The code pages, product files and scanners files.


def code_pages(scanned: pl.LazyFrame) -> Bundle:
    """Each scanned code's daily, hourly and recent scans, for every selectable location where it was scanned."""
    described = described_from_table(scanned)
    locations = locations_of(described)
    bundle: Bundle = {}
    for (code,), code_scans in described.group_by("code"):
        for location in locations.selectable():
            scans_within = locations.within(code_scans, location)
            if scans_within.is_empty():
                continue
            summary = summarise(scans_within, recent_limit=RECENT_SCANS_LIMIT)
            bundle[code_scans_path(code, location).as_posix()] = CodeScansFile(
                code=code,
                location=location,
                daily=summary.daily,
                hourly=summary.hourly,
                recent=summary.recent,
            )
    return bundle


def product_files(scanned: pl.LazyFrame, products: pl.LazyFrame) -> Bundle:
    """Each scanned code's product file; a code with no products row is an unknown product."""
    codes = described_from_table(scanned).get_column("code").unique()
    with tempfile.TemporaryDirectory() as scratch:
        files = products_by_code(write_parquet(products, Path(scratch) / "products.parquet"))
    return {
        product_path(code).as_posix(): files.get(code, ProductFile(code=code, known=False, product=None))
        for code in codes
    }


def scanners_files(heartbeats: pl.LazyFrame, scanned: pl.LazyFrame) -> Bundle:
    """Every selectable location's scanners file, from the heartbeats table, each scanner with its
    last scan by API key (ADR 0002)."""
    described = described_from_table(scanned)
    locations = locations_of(described)
    latest = latest_heartbeats(heartbeats_from_table(heartbeats))
    return {
        scanners_path(location).as_posix(): ScannersFile(
            location=location,
            scanners=scanner_statuses(locations.within(latest, location), described),
        )
        for location in locations.selectable()
    }


# The whole tree.


def merged(bundles: list[Bundle]) -> dict[str, Any]:
    """The whole tree. A path in several bundles is one file made of their fragments, in bundle order."""
    tree: dict[str, Any] = {}
    for bundle in bundles:
        for path, content in bundle.items():
            if path in tree and isinstance(tree[path], dict) and isinstance(content, dict):
                tree[path] = {**tree[path], **content}
            else:
                tree[path] = content
    return tree


def write_tree(tree: Mapping[str, Any], root: Path) -> None:
    """Write every file of the tree under `root`, for publishing."""
    write_files(tree, root)


def write_files(tree: Mapping[str, Any], root: Path) -> None:
    """Write every file of the tree under `root`. (`write_tree` is what publishing calls.)"""
    for path, content in tree.items():
        write_json(root / path, content)
