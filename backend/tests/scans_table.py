"""Fixture builder for a normalised scans table with office time zones attached."""

import uuid
from datetime import datetime

import polars as pl


def scan(
    code: str, scanned_at: str, *, location: str = "thailand:bangkok", office_time_zone: str = "UTC"
) -> dict[str, object]:
    return {
        "event_id": str(uuid.uuid4()),
        "code": code,
        "location": location,
        "scanned_at": datetime.fromisoformat(scanned_at),
        "office_time_zone": office_time_zone,
    }


def scans_table(*scans: dict[str, object]) -> pl.DataFrame:
    return pl.DataFrame(
        list(scans),
        schema={
            "event_id": pl.String(),
            "code": pl.String(),
            "location": pl.String(),
            "scanned_at": pl.Datetime("us", "UTC"),
            "office_time_zone": pl.String(),
        },
    )
