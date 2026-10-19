"""The build: raw scanner events in, the static JSON tree read by the frontend out."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from snacker.locations import Locations
from snacker.scan_summary import summarise
from snacker.scans import normalise_scans
from snacker.timestamps import UTC_TIMESTAMP_FORMAT


RECENT_SCANS_LIMIT = 25


def build(
    *,
    raw_dir: Path,
    out_dir: Path,
    generated_at: datetime,
    recent_limit: int = RECENT_SCANS_LIMIT,
) -> None:
    data_dir = out_dir / "data"
    write_json(data_dir / "meta.json", {"generated_at": format_utc(generated_at)})

    scans = normalise_scans(raw_dir)
    locations = Locations.from_scans(scans)
    zoned_scans = locations.with_office_time_zones(scans)

    for location in locations.selectable():
        summary = summarise(locations.within(zoned_scans, location), recent_limit=recent_limit)
        write_json(
            data_dir / "index" / "by-location" / f"{location}.json",
            {"location": location, "daily": summary.daily, "recent": summary.recent},
        )


def format_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(UTC_TIMESTAMP_FORMAT)


def write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
