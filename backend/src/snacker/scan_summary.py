"""Scan summary: what a set of scans amounts to, shaped like the published JSON.

Days are counted in each scan's office time zone, so the scans table must carry an
`office_time_zone` column (see Locations.with_office_time_zones) alongside `scanned_at` in UTC,
plus `product_name` and `product_brands` columns, null for unknown products (see products.with_products).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict
from zoneinfo import ZoneInfo

import polars as pl

from snacker.timestamps import DATE_FORMAT, UTC_TIMESTAMP_FORMAT


class DailyCount(TypedDict):
    date: str
    count: int


class HourlyCount(TypedDict):
    hour: int
    """0-23, in the office time zone."""
    count: int


class ScanRow(TypedDict):
    code: str
    name: str | None
    """The product's name; null for an unknown product."""
    brands: str | None
    location: str
    scanned_at: str
    """UTC, e.g. "2026-09-23T06:26:00Z"."""
    office_time: str
    """The same moment in the office time zone, e.g. "2026-09-23T13:26:00+07:00"."""
    office_time_zone: str


@dataclass(frozen=True)
class ScanSummary:
    daily: list[DailyCount]
    """Scans per date in their office time zone, oldest first; days without scans are left out."""
    hourly: list[HourlyCount]
    """Scans per hour of the day in their office time zone: always 24 entries, 0 to 23."""
    recent: list[ScanRow]
    """The most recent scans, newest first."""


def summarise(scans: pl.DataFrame, *, recent_limit: int) -> ScanSummary:
    return ScanSummary(
        daily=_daily_counts(scans),
        hourly=_hourly_counts(scans),
        recent=_recent_scans(scans, recent_limit),
    )


def _daily_counts(scans: pl.DataFrame) -> list[DailyCount]:
    counts = (
        _with_office_moments(scans)
        .group_by("office_date")
        .len(name="count")
        .sort("office_date")
        .select(pl.col("office_date").dt.to_string(DATE_FORMAT).alias("date"), "count")
    )
    return [DailyCount(date=row["date"], count=row["count"]) for row in counts.to_dicts()]


def _hourly_counts(scans: pl.DataFrame) -> list[HourlyCount]:
    counts = dict(
        _with_office_moments(scans).group_by("office_hour").len(name="count").iter_rows()
    )
    return [HourlyCount(hour=hour, count=counts.get(hour, 0)) for hour in range(24)]


def _with_office_moments(scans: pl.DataFrame) -> pl.DataFrame:
    """Add each scan's calendar date and hour of the day in its own office time zone.

    Polars holds one time zone per column, so each zone's scans are converted separately.
    """
    if scans.is_empty():
        return scans.with_columns(
            pl.lit(None, dtype=pl.Date()).alias("office_date"),
            pl.lit(None, dtype=pl.Int8()).alias("office_hour"),
        )
    return pl.concat([
        group.with_columns(
            pl.col("scanned_at").dt.convert_time_zone(time_zone).alias("office_moment")
        ).with_columns(
            pl.col("office_moment").dt.date().alias("office_date"),
            pl.col("office_moment").dt.hour().alias("office_hour"),
        ).drop("office_moment")
        for (time_zone,), group in scans.group_by("office_time_zone")
    ])


def _recent_scans(scans: pl.DataFrame, limit: int) -> list[ScanRow]:
    rows = (
        scans.sort(["scanned_at", "event_id"], descending=True)
        .head(limit)
        .select("code", "product_name", "product_brands", "location", "scanned_at", "office_time_zone")
    )
    return [
        ScanRow(
            code=row["code"],
            name=row["product_name"],
            brands=row["product_brands"],
            location=row["location"],
            scanned_at=row["scanned_at"].strftime(UTC_TIMESTAMP_FORMAT),
            office_time=in_office_time_zone(row["scanned_at"], row["office_time_zone"]),
            office_time_zone=row["office_time_zone"],
        )
        for row in rows.to_dicts()
    ]


def in_office_time_zone(moment: datetime, office_time_zone: str) -> str:
    """The moment as ISO 8601 in the office time zone, e.g. "2026-09-23T13:26:00+07:00"."""
    return moment.astimezone(ZoneInfo(office_time_zone)).isoformat(timespec="seconds")
