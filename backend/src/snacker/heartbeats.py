"""Heartbeats: each scanner's periodic sign of life, and what it says about the scanner.

Scanner firmware has sent three heartbeat payload shapes, all carrying the same facts:

- flat, unversioned (v0.1.35): `device_name`, `location`, `version`
- flat with telemetry (v0.1.36): the same keys, plus `serial_number`, `telemetry`, ...
- `schema_version` 2 (v0.1.37+): `device.name`, `device.location`, `app.version`

The EventBridge envelope `time` is when the heartbeat arrived.
"""

from pathlib import Path
from typing import Any, TypedDict

import polars as pl

from snacker.events import read_events
from snacker.timestamps import UTC_TIMESTAMP_FORMAT, parse_aware_timestamp

HEARTBEATS_SCHEMA = pl.Schema({
    "scanner": pl.String(),
    "location": pl.String(),
    "app_version": pl.String(),
    "sent_at": pl.Datetime("us", "UTC"),
})


class ScannerStatus(TypedDict):
    name: str
    """The scanner's name, e.g. "rpi-pico-w-01"."""
    location: str
    """Where its latest heartbeat said it was."""
    app_version: str
    """From its latest heartbeat."""
    last_seen: str
    """UTC time of its latest heartbeat, e.g. "2026-10-19T09:45:47Z"."""


def normalise_heartbeats(raw_dir: Path) -> pl.DataFrame:
    """Every heartbeat as one row: which scanner, where it is, its app version, when it was sent."""
    rows = [normalise_heartbeat_event(event) for event in read_events(raw_dir / "heartbeats")]
    return pl.DataFrame(rows, schema=HEARTBEATS_SCHEMA)


def normalise_heartbeat_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event["detail"]["payload"]
    unknown_shape = ValueError(f"heartbeat in an unknown shape in event {event['id']}: {sorted(payload)}")
    try:
        if payload.get("schema_version") == 2:
            device, app = payload["device"], payload["app"]
            scanner, location, app_version = device["name"], device["location"], app["version"]
        elif "schema_version" not in payload:
            scanner, location, app_version = payload["device_name"], payload["location"], payload["version"]
        else:
            raise unknown_shape
    except KeyError:
        raise unknown_shape from None
    return {
        "scanner": scanner,
        "location": location,
        "app_version": app_version,
        "sent_at": parse_aware_timestamp(event["time"]),
    }


def scanner_statuses(heartbeats: pl.DataFrame) -> list[ScannerStatus]:
    """Each scanner as its latest heartbeat describes it, ordered by name."""
    latest = (
        heartbeats.sort("sent_at", descending=True)
        .unique("scanner", keep="first")
        .sort("scanner")
    )
    return [
        ScannerStatus(
            name=row["scanner"],
            location=row["location"],
            app_version=row["app_version"],
            last_seen=row["sent_at"].strftime(UTC_TIMESTAMP_FORMAT),
        )
        for row in latest.iter_rows(named=True)
    ]
