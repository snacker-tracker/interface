"""Fixture builders for raw scanner events, shaped like the real EventBridge envelopes on S3."""

import json
import uuid
from pathlib import Path
from typing import Any

Event = dict[str, Any]


def backfill_scan(
    code: str,
    *,
    scanned_at: str,
    time: str | None = None,
    location: str = "thailand:bangkok",
    event_id: str | None = None,
) -> Event:
    """A scan imported from the previous system: `/scans`, `from-backup`, carries `scanned_at`."""
    return {
        "version": "-1",
        "id": event_id or str(uuid.uuid4()),
        "detail-type": "/scans",
        "source": "from-backup",
        "account": None,
        "time": time or scanned_at,
        "region": None,
        "resources": [],
        "detail": {
            "client_ip": None,
            "request_id": None,
            "payload": {"code": code, "location": location, "scanned_at": scanned_at},
            "apiKeyId": None,
        },
    }


def live_scan(
    code: str,
    *,
    time: str,
    location: str = "thailand:bangkok:main-kitchen",
    event_id: str | None = None,
) -> Event:
    """A scan from the current scanner: `scans`, `scanner`, no `scanned_at` in the payload."""
    return {
        "version": "0",
        "id": event_id or str(uuid.uuid4()),
        "detail-type": "scans",
        "source": "scanner",
        "account": "132218943709",
        "time": time,
        "region": "ap-southeast-1",
        "resources": [],
        "detail": {
            "client_ip": "203.0.113.10",
            "request_id": str(uuid.uuid4()),
            "payload": {"code": code, "location": location},
            "apiKeyId": "s8ma4oq3ue",
        },
    }


def write_events(raw_dir: Path, relative_path: str, events: list[Event]) -> None:
    """Write events one JSON envelope per line, as the delivery stream does."""
    path = raw_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(event) + "\n" for event in events))
