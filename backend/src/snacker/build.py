"""The build: raw scanner events in, the static JSON tree read by the frontend out."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import polars as pl

from snacker.config import OFFICE_TIME_ZONES, RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT
from snacker.heartbeats import normalise_heartbeats, scanner_statuses
from snacker.locations import Locations
from snacker.products import Product, known_products, with_products
from snacker.scan_summary import summarise, top_scans
from snacker.scans import normalise_scans
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
) -> None:
    """`generated_at` is when the data is built; every top-scans period ends then."""
    data_dir = out_dir / "data"
    write_json(data_dir / "meta.json", {"generated_at": format_utc(generated_at)})

    scans = normalise_scans(raw_dir)
    locations = Locations.from_scans(scans, office_time_zones)
    zoned_scans = locations.with_office_time_zones(scans)
    described_scans = with_products(zoned_scans, products_parquet)

    write_json(
        data_dir / "locations.json",
        {"locations": [{"id": location} for location in locations.selectable()]},
    )
    for location in locations.selectable():
        scans_within = locations.within(described_scans, location)
        summary = summarise(scans_within, recent_limit=recent_limit)
        write_json(
            data_dir / "index" / "by-location" / f"{path_segment(location)}.json",
            {
                "location": location,
                "top_scans": top_scans(scans_within, limit=top_limit, now=generated_at),
                "top_unknown_scans": top_scans(
                    scans_within, limit=top_limit, now=generated_at, unknown_only=True
                ),
                "daily": summary.daily,
                "recent": summary.recent,
            },
        )

    heartbeats = normalise_heartbeats(raw_dir)
    for location in locations.selectable():
        write_json(
            data_dir / "scanners" / "by-location" / f"{path_segment(location)}.json",
            {"location": location, "scanners": scanner_statuses(locations.within(heartbeats, location), described_scans)},
        )

    products = known_products(products_parquet)
    for (code,), code_scans in described_scans.group_by("code"):
        write_code_files(
            data_dir / "codes" / path_segment(code),
            code,
            products.get(code),
            code_scans,
            locations,
            recent_limit,
        )


def write_code_files(
    code_dir: Path,
    code: str,
    product: Product | None,
    code_scans: pl.DataFrame,
    locations: Locations,
    recent_limit: int,
) -> None:
    """A code's product file (product null when unknown), plus a scans file for each
    location the code was scanned in."""
    write_json(code_dir / "product.json", {"code": code, "product": product})

    for location in locations.selectable():
        scans_within = locations.within(code_scans, location)
        if scans_within.is_empty():
            continue
        summary = summarise(scans_within, recent_limit=recent_limit)
        write_json(
            code_dir / "by-location" / f"{path_segment(location)}.json",
            {
                "code": code,
                "location": location,
                "daily": summary.daily,
                "hourly": summary.hourly,
                "recent": summary.recent,
            },
        )


def path_segment(value: str) -> str:
    """A location or code as a file name: percent-encoded like JavaScript's
    encodeURIComponent, except that `:` stays readable (`thailand:bangkok`)."""
    return quote(value, safe="!*'():")


def format_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(UTC_TIMESTAMP_FORMAT)


def write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
