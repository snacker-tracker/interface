"""Scan summary: what a set of scans amounts to, shaped like the published JSON.

Days are counted in each scan's office time zone, so the scans table must carry an
`office_time_zone` column (see Locations.with_office_time_zones) alongside `scanned_at` in UTC.
"""

from dataclasses import dataclass
from typing import TypedDict

import polars as pl

from snacker.timestamps import DATE_FORMAT, UTC_TIMESTAMP_FORMAT


class DailyCount(TypedDict):
    date: str
    count: int


class ScanRow(TypedDict):
    code: str
    location: str
    scanned_at: str


@dataclass(frozen=True)
class ScanSummary:
    daily: list[DailyCount]
    """Scans per date in their office time zone, oldest first; days without scans are left out."""
    recent: list[ScanRow]
    """The most recent scans, newest first."""


def summarise(scans: pl.DataFrame, *, recent_limit: int) -> ScanSummary:
    return ScanSummary(
        daily=_daily_counts(scans),
        recent=_recent_scans(scans, recent_limit),
    )


def _daily_counts(scans: pl.DataFrame) -> list[DailyCount]:
    counts = (
        _with_office_dates(scans)
        .group_by("office_date")
        .len(name="count")
        .sort("office_date")
        .select(pl.col("office_date").dt.to_string(DATE_FORMAT).alias("date"), "count")
    )
    return [DailyCount(date=row["date"], count=row["count"]) for row in counts.to_dicts()]


def _with_office_dates(scans: pl.DataFrame) -> pl.DataFrame:
    """Add each scan's calendar date in its own office time zone.

    Polars holds one time zone per column, so each zone's scans are converted separately.
    """
    if scans.is_empty():
        return scans.with_columns(pl.lit(None, dtype=pl.Date()).alias("office_date"))
    return pl.concat([
        group.with_columns(
            pl.col("scanned_at").dt.convert_time_zone(time_zone).dt.date().alias("office_date")
        )
        for (time_zone,), group in scans.group_by("office_time_zone")
    ])


def _recent_scans(scans: pl.DataFrame, limit: int) -> list[ScanRow]:
    rows = (
        scans.sort(["scanned_at", "event_id"], descending=True)
        .head(limit)
        .select(
            "code",
            "location",
            pl.col("scanned_at").dt.to_string(UTC_TIMESTAMP_FORMAT),
        )
    )
    return [
        ScanRow(code=row["code"], location=row["location"], scanned_at=row["scanned_at"])
        for row in rows.to_dicts()
    ]
