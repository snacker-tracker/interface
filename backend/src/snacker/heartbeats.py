"""Heartbeats: each scanner's periodic sign of life, and what it says about the scanner.

Scanner firmware has sent three heartbeat payload shapes, all carrying the same facts:

- flat, unversioned (v0.1.35): `device_name`, `location`, `version`
- flat with telemetry (v0.1.36): the same keys, plus `serial_number`, `telemetry`, ...
- `schema_version` 2 (v0.1.37+): `device.name`, `device.location`, `app.version`

The EventBridge envelope `time` is when the heartbeat arrived. A scanner's scans are the
ones sent with the API key its heartbeats use (see docs/adr/0002).
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
    "api_key": pl.String(),
})


class LastScan(TypedDict):
    scanned_at: str
    """UTC, e.g. "2026-10-16T10:33:45Z"."""
    code: str
    product_name: str | None
    """Null for an unknown product."""


class ScannerStatus(TypedDict):
    name: str
    """The scanner's name, e.g. "rpi-pico-w-01"."""
    location: str
    """Where its latest heartbeat said it was."""
    app_version: str
    """From its latest heartbeat."""
    last_seen: str
    """UTC time of its latest heartbeat, e.g. "2026-10-19T09:45:47Z"."""
    last_scan: LastScan | None
    """The latest scan sent with its API key; None if it has sent none."""


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
        "api_key": event["detail"].get("apiKeyId"),
    }


def scanner_statuses(heartbeats: pl.DataFrame, scans: pl.DataFrame) -> list[ScannerStatus]:
    """Each scanner as its latest heartbeat describes it, with its last scan, ordered by name.

    `scans` are all scans, with products attached (see products.with_products): a scanner's
    last scan is found by API key wherever it happened.
    """
    latest_heartbeats = (
        heartbeats.sort("sent_at", descending=True)
        .unique("scanner", keep="first")
        .sort("scanner")
    )
    last_scans = (
        scans.filter(pl.col("api_key").is_not_null())
        .sort("scanned_at", descending=True)
        .unique("api_key", keep="first")
        # Renamed so it can't be confused with the heartbeat's own times once joined.
        .select("api_key", pl.col("scanned_at").alias("last_scanned_at"), "code", "product_name")
    )
    rows = latest_heartbeats.join(last_scans, on="api_key", how="left", maintain_order="left")
    return [
        ScannerStatus(
            name=row["scanner"],
            location=row["location"],
            app_version=row["app_version"],
            last_seen=row["sent_at"].strftime(UTC_TIMESTAMP_FORMAT),
            last_scan=None if row["last_scanned_at"] is None else LastScan(
                scanned_at=row["last_scanned_at"].strftime(UTC_TIMESTAMP_FORMAT),
                code=row["code"],
                product_name=row["product_name"],
            ),
        )
        for row in rows.iter_rows(named=True)
    ]
