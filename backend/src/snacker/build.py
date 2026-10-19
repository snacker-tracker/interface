"""The build: raw scanner events in, the static JSON tree read by the frontend out."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from snacker.config import OFFICE_TIME_ZONES, RECENT_SCANS_LIMIT
from snacker.locations import Locations
from snacker.products import with_products
from snacker.scan_summary import summarise
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
) -> None:
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
        summary = summarise(locations.within(described_scans, location), recent_limit=recent_limit)
        write_json(
            data_dir / "index" / "by-location" / f"{path_segment(location)}.json",
            {"location": location, "daily": summary.daily, "recent": summary.recent},
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
