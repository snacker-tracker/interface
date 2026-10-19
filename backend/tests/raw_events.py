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
    api_key: str = "s8ma4oq3ue",
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
            "apiKeyId": api_key,
        },
    }


def _heartbeat_envelope(time: str, payload: dict[str, Any], api_key: str | None = "s8ma4oq3ue") -> Event:
    return {
        "version": "0",
        "id": str(uuid.uuid4()),
        "detail-type": "heartbeats",
        "source": "scanner",
        "account": "132218943709",
        "time": time,
        "region": "ap-southeast-1",
        "resources": [],
        "detail": {"client_ip": "203.0.113.10", "request_id": str(uuid.uuid4()), "payload": payload, "apiKeyId": api_key},
    }


def heartbeat_flat(
    *, time: str, device_name: str = "rpi-pico-w-01",
    location: str = "thailand:bangkok:main-kitchen", version: str = "v0.1.35",
) -> Event:
    """The first firmware's heartbeat: flat, unversioned."""
    return _heartbeat_envelope(time, {"location": location, "device_name": device_name, "uptime": 3902, "version": version})


def heartbeat_flat_with_telemetry(
    *, time: str, device_name: str = "rpi-pico-w-01",
    location: str = "thailand:bangkok:main-kitchen", version: str = "v0.1.36",
) -> Event:
    """A brief interim shape: still flat and unversioned, with telemetry."""
    return _heartbeat_envelope(time, {
        "location": location, "serial_number": "e6614c311b334739", "version": version,
        "board_model": "Raspberry Pi Pico W with RP2040",
        "telemetry": {"wifi_ssid": "Office", "wifi_rssi": -46, "reset_cause": "WDT_RESET", "mem_free": 180592},
        "device_name": device_name, "uptime": 600, "micropython_version": "1.28.0",
    })


def heartbeat_v2(
    *, time: str, device_name: str = "rpi-pico-w-01",
    location: str = "thailand:bangkok:main-kitchen", version: str = "v0.1.42",
    api_key: str | None = "s8ma4oq3ue",
) -> Event:
    """`schema_version` 2: nested under platform, device, telemetry and app."""
    return _heartbeat_envelope(time, {
        "platform": {"name": "micropython", "version": "1.28.0"},
        "device": {"id": "e6614c311b334739", "location": location, "name": device_name,
                   "board": "Raspberry Pi Pico W with RP2040"},
        "telemetry": {"wifi_rssi": -46, "reset_cause": "PWRON_RESET", "wifi_ssid": "Office", "uptime": 20094,
                      "mem_free": 185872},
        "app": {"name": "snacker-tracker/pico-scanner", "version": version},
        "schema_version": 2,
    }, api_key)


def write_events(raw_dir: Path, relative_path: str, events: list[Event]) -> None:
    """Write events one JSON envelope per line, as the delivery stream does."""
    path = raw_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(event) + "\n" for event in events))
