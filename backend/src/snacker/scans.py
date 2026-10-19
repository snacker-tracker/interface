"""Normalise raw scan events into one scans table.

Two eras of scan events exist and are treated identically downstream:
- backfill: imported from the previous system (`source: from-backup`), carries a device `scanned_at`
- live: from the current scanner (`source: scanner`), has no `scanned_at`, so the EventBridge
  envelope `time` (when the event was reported) stands in for it
"""

from pathlib import Path
from typing import Any

import polars as pl

from snacker.events import read_events
from snacker.timestamps import parse_aware_timestamp

SCANS_SCHEMA = pl.Schema({
    "event_id": pl.String(),
    "code": pl.String(),
    "location": pl.String(),
    "scanned_at": pl.Datetime("us", "UTC"),
    "scanned_at_source": pl.String(),  # "device" | "reported"
    "origin": pl.String(),  # "backfill" | "live"; kept for debugging only
})

ORIGIN_BY_SOURCE = {"from-backup": "backfill", "scanner": "live"}


def normalise_scans(raw_dir: Path) -> pl.DataFrame:
    rows = [normalise_scan_event(event) for event in read_events(raw_dir / "scans")]
    # Delivery to S3 is at-least-once, so the same event can land in more than one file.
    return pl.DataFrame(rows, schema=SCANS_SCHEMA).unique("event_id", keep="first", maintain_order=True)


def normalise_scan_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event["detail"]["payload"]
    device_time = payload.get("scanned_at")
    if event["source"] not in ORIGIN_BY_SOURCE:
        raise ValueError(f"unknown scan source {event['source']!r} in event {event['id']}")
    return {
        "event_id": event["id"],
        "code": str(payload["code"]),
        "location": payload["location"],
        "scanned_at": parse_aware_timestamp(device_time or event["time"]),
        "scanned_at_source": "device" if device_time else "reported",
        "origin": ORIGIN_BY_SOURCE[event["source"]],
    }
