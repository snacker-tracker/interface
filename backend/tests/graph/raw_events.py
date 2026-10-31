"""Raw scanner events shaped like the real EventBridge envelopes, written as Firehose lays them out."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

Event = dict[str, Any]


def backfill_scan(code: str, *, scanned_at: str, location: str = "thailand:bangkok", event_id: str | None = None) -> Event:
    """A scan imported from the previous system: `from-backup`, carries a device `scanned_at`."""
    return {
        "version": "-1",
        "id": event_id or str(uuid.uuid4()),
        "detail-type": "/scans",
        "source": "from-backup",
        "time": scanned_at,
        "detail": {"payload": {"code": code, "location": location, "scanned_at": scanned_at}, "apiKeyId": None},
    }


def live_scan(code: str, *, time: str, location: str = "thailand:bangkok:main-kitchen", event_id: str | None = None) -> Event:
    """A scan from the current scanner: `scanner`, no `scanned_at`; the envelope time stands in."""
    return {
        "version": "0",
        "id": event_id or str(uuid.uuid4()),
        "detail-type": "scans",
        "source": "scanner",
        "time": time,
        "detail": {"payload": {"code": code, "location": location}, "apiKeyId": "s8ma4oq3ue"},
    }


def write_raw(root: Path, day: str, name: str, events: list[Event], modified: str) -> str:
    """Write `events` as one NDJSON file under `<root>/scans/<day>/`, last modified at `modified`.

    `day` is `YYYY/MM/DD`. Returns the file's key relative to `root`.
    """
    key = f"scans/{day}/{name}"
    path = root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    stamp = datetime.fromisoformat(modified).timestamp()
    os.utime(path, (stamp, stamp))
    return key


def with_api_key(event: Event, api_key: str | None) -> Event:
    """`event` as if sent with another API key (each scanner has its own, ADR 0002)."""
    return {**event, "detail": {**event["detail"], "apiKeyId": api_key}}


def _heartbeat_envelope(time: str, payload: dict[str, Any], api_key: str | None) -> Event:
    return {
        "version": "0",
        "id": str(uuid.uuid4()),
        "detail-type": "heartbeats",
        "source": "scanner",
        "time": time,
        "detail": {"client_ip": "203.0.113.10", "request_id": str(uuid.uuid4()), "payload": payload, "apiKeyId": api_key},
    }


def heartbeat_flat(*, time: str, device_name: str = "rpi-pico-w-01", location: str = "thailand:bangkok:main-kitchen", version: str = "v0.1.35", api_key: str | None = "s8ma4oq3ue") -> Event:
    """The first firmware's heartbeat: flat, unversioned."""
    return _heartbeat_envelope(time, {"location": location, "device_name": device_name, "uptime": 3902, "version": version}, api_key)


def heartbeat_flat_with_telemetry(*, time: str, device_name: str = "rpi-pico-w-01", location: str = "thailand:bangkok:main-kitchen", version: str = "v0.1.36", api_key: str | None = "s8ma4oq3ue") -> Event:
    """A brief interim shape: still flat and unversioned, with telemetry."""
    return _heartbeat_envelope(time, {
        "location": location, "serial_number": "e6614c311b334739", "version": version,
        "telemetry": {"wifi_ssid": "Office", "wifi_rssi": -46, "reset_cause": "WDT_RESET", "mem_free": 180592},
        "device_name": device_name, "uptime": 600,
    }, api_key)


def heartbeat_v2(*, time: str, device_name: str = "rpi-pico-w-01", location: str = "thailand:bangkok:main-kitchen", version: str = "v0.1.42", api_key: str | None = "s8ma4oq3ue") -> Event:
    """`schema_version` 2: nested under platform, device, telemetry and app."""
    return _heartbeat_envelope(time, {
        "platform": {"name": "micropython", "version": "1.28.0"},
        "device": {"id": "e6614c311b334739", "location": location, "name": device_name},
        "telemetry": {"wifi_rssi": -46, "uptime": 20094},
        "app": {"name": "snacker-tracker/pico-scanner", "version": version},
        "schema_version": 2,
    }, api_key)


def write_heartbeats(root: Path, day: str, name: str, events: list[Event], modified: str) -> str:
    """Write heartbeat `events` as one NDJSON file under `<root>/heartbeats/<day>/`, last modified at `modified`."""
    key = f"heartbeats/{day}/{name}"
    path = root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    stamp = datetime.fromisoformat(modified).timestamp()
    os.utime(path, (stamp, stamp))
    return key
