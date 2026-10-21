"""The build: raw scanner events in, the static JSON tree read by the frontend out."""

import json
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from snacker.check import Violation, contract_violations
from snacker.config import OFFICE_TIME_ZONES, RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT
from snacker.contract import (
    CONTRACT_VERSION,
    CodeScansFile,
    ContractFile,
    IndexFile,
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
)
from snacker.heartbeats import normalise_heartbeats, scanner_statuses
from snacker.locations import Locations
from snacker.products import product_files, with_products
from snacker.scan_summary import healthiest_and_least_healthy, period_days, summarise, top_scans
from snacker.scans import normalise_scans
from snacker.storage import Bucket, Published, publish_to_bucket
from snacker.timestamps import UTC_TIMESTAMP_FORMAT


def build(
    *,
    raw_dir: Path,
    products_parquet: Path,
    out_dir: Path,
    generated_at: datetime,
    office_time_zones: Mapping[str, str] = OFFICE_TIME_ZONES,
    recent_limit: int = RECENT_SCANS_LIMIT,
    top_limit: int = TOP_SCANS_LIMIT,
    site: Bucket | None = None,
) -> Published | None:
    """Write the static JSON to `out_dir/data`, replacing what's there, but only if it keeps
    the output contract: otherwise raise ContractBroken and leave the previous data alone.

    `generated_at` is when the data is built; every top-scans period ends then. With a `site`
    bucket, the checked build goes to its data/ instead, and only `out_dir` stages it.
    """
    staging_dir = out_dir / ".data-building"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)  # left by an earlier build that broke the contract
    write_data(
        staging_dir,
        raw_dir=raw_dir,
        products_parquet=products_parquet,
        generated_at=generated_at,
        office_time_zones=office_time_zones,
        recent_limit=recent_limit,
        top_limit=top_limit,
    )
    violations = contract_violations(staging_dir, recent_limit=recent_limit, top_limit=top_limit)
    if violations:
        raise ContractBroken(staging_dir, violations)
    if site is not None:
        return publish_to_bucket(staging_dir, site)
    publish(staging_dir, out_dir / "data")
    return None


class ContractBroken(Exception):
    def __init__(self, staging_dir: Path, violations: list[Violation]) -> None:
        super().__init__(f"the build breaks the output contract in {len(violations)} places; see {staging_dir}")
        self.staging_dir = staging_dir
        self.violations = violations


def publish(staging_dir: Path, data_dir: Path) -> None:
    """Swap the checked build in for the previous one."""
    previous = data_dir.with_name(".data-previous")
    if previous.exists():
        shutil.rmtree(previous)
    if data_dir.exists():
        data_dir.rename(previous)
    staging_dir.rename(data_dir)
    if previous.exists():
        shutil.rmtree(previous)


def write_data(
    data_dir: Path,
    *,
    raw_dir: Path,
    products_parquet: Path,
    generated_at: datetime,
    office_time_zones: Mapping[str, str],
    recent_limit: int,
    top_limit: int,
) -> None:
    """Every file of the static JSON, under `data_dir`."""
    write_json(data_dir / meta_path(), MetaFile(generated_at=format_utc(generated_at), contract_version=CONTRACT_VERSION))

    scans = normalise_scans(raw_dir)
    locations = Locations.from_scans(scans, office_time_zones)
    zoned_scans = locations.with_office_time_zones(scans)
    described_scans = with_products(zoned_scans, products_parquet)

    write_json(
        data_dir / locations_path(),
        LocationsFile(locations=[SelectableLocation(id=location) for location in locations.selectable()]),
    )
    for location in locations.selectable():
        scans_within = locations.within(described_scans, location)
        summary = summarise(scans_within, recent_limit=recent_limit)
        write_json(
            data_dir / index_path(location),
            IndexFile(
                location=location,
                top_scans=top_scans(scans_within, limit=top_limit, now=generated_at),
                top_unknown_scans=top_scans(scans_within, limit=top_limit, now=generated_at, unknown_only=True),
                healthiest_and_least_healthy=healthiest_and_least_healthy(scans_within, limit=top_limit, now=generated_at),
                period_days=period_days(scans_within, now=generated_at),
                daily=summary.daily,
                recent=summary.recent,
            ),
        )

    heartbeats = normalise_heartbeats(raw_dir)
    for location in locations.selectable():
        write_json(
            data_dir / scanners_path(location),
            ScannersFile(
                location=location,
                scanners=scanner_statuses(locations.within(heartbeats, location), described_scans),
            ),
        )

    products = product_files(products_parquet)
    for (code,), code_scans in described_scans.group_by("code"):
        product = products.get(code, ProductFile(code=code, known=False, product=None))
        write_code_files(data_dir, product, code_scans, locations, recent_limit)


def write_code_files(
    data_dir: Path,
    product: ProductFile,
    code_scans: pl.DataFrame,
    locations: Locations,
    recent_limit: int,
) -> None:
    """A code's product file, plus a scans file for each location the code was scanned in."""
    code = product["code"]
    write_json(data_dir / product_path(code), product)

    for location in locations.selectable():
        scans_within = locations.within(code_scans, location)
        if scans_within.is_empty():
            continue
        summary = summarise(scans_within, recent_limit=recent_limit)
        write_json(
            data_dir / code_scans_path(code, location),
            CodeScansFile(
                code=code,
                location=location,
                daily=summary.daily,
                hourly=summary.hourly,
                recent=summary.recent,
            ),
        )


def format_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(UTC_TIMESTAMP_FORMAT)


def write_json(path: Path, content: ContractFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
