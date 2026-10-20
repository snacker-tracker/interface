"""Scan summary: what a set of scans amounts to, shaped like the published JSON.

Days are counted in each scan's office time zone, so the scans table must carry an
`office_time_zone` column (see Locations.with_office_time_zones) alongside `scanned_at` in UTC,
plus `product_name`, `product_name_source`, `product_brands` and `product_known` columns (see products.with_products).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from collections.abc import Callable
from typing import cast
from zoneinfo import ZoneInfo

import polars as pl

from snacker.contract import PERIODS, DailyCount, HourlyCount, ScanRow, TopScan, TopScansByPeriod
from snacker.timestamps import DATE_FORMAT, UTC_TIMESTAMP_FORMAT


CALENDAR_PERIODS: dict[str, Callable[[date], date]] = {
    # Each maps today's office date to the period's first office date.
    "today": lambda today: today,
    "this-work-week": lambda today: today - timedelta(days=today.weekday()),  # back to Monday
    "this-month": lambda today: today.replace(day=1),
    "this-year": lambda today: date(today.year, 1, 1),
}

ROLLING_PERIODS = {
    "last-7-days": timedelta(days=7),
    "last-30-days": timedelta(days=30),
    "last-365-days": timedelta(days=365),
}


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
        .select(
            "code", "product_name", "product_name_source", "product_brands", "product_known",
            "location", "scanned_at", "office_time_zone",
        )
    )
    return [
        ScanRow(
            code=row["code"],
            name=row["product_name"],
            name_source=row["product_name_source"],
            brands=row["product_brands"],
            known=row["product_known"],
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


def top_scans(
    scans: pl.DataFrame, *, limit: int, now: datetime, unknown_only: bool = False
) -> TopScansByPeriod:
    """For every period (see PERIODS), the codes scanned most within it, most first.

    `now` is when the data is built: every period ends then, so later scans aren't counted.
    With `unknown_only`, only unknown products are ranked, but each share is still of all
    scans in the period, so it shows how much of what's taken is missing a product.
    Kept apart from `summarise` because only index files show top scans, and code files are many.
    """
    flagged = _with_period_flags(scans, now)
    ranked = flagged.filter(~pl.col("product_known")) if unknown_only else flagged
    return cast(TopScansByPeriod, {
        period: _rank(ranked.filter(pl.col(period)), limit, total=flagged.filter(pl.col(period)).height)
        for period in PERIODS
    })


def _with_period_flags(scans: pl.DataFrame, now: datetime) -> pl.DataFrame:
    """Add a boolean column per period: whether each scan falls within it.

    Calendar periods start at midnight in each scan's own office time zone, so each
    zone's period starts are worked out from `now` in that zone and joined on.
    Rolling periods include a scan exactly at their cutoff.
    """
    starts = pl.DataFrame(
        [_calendar_starts(zone, now) for zone in scans["office_time_zone"].unique().to_list()],
        schema={"office_time_zone": pl.String(), **{f"{period}-start": pl.Date() for period in CALENDAR_PERIODS}},
    )
    dated = _with_office_moments(scans).join(starts, on="office_time_zone", how="left")
    before_now = pl.col("scanned_at") <= now
    return dated.with_columns(
        *(
            (before_now & (pl.col("office_date") >= pl.col(f"{period}-start"))).alias(period)
            for period in CALENDAR_PERIODS
        ),
        *(
            (before_now & (pl.col("scanned_at") >= now - duration)).alias(period)
            for period, duration in ROLLING_PERIODS.items()
        ),
        before_now.alias("all-time"),
    )


def _calendar_starts(time_zone: str, now: datetime) -> dict[str, object]:
    """The first office date of each calendar period, as of `now` in `time_zone`."""
    today = now.astimezone(ZoneInfo(time_zone)).date()
    return {
        "office_time_zone": time_zone,
        **{f"{period}-start": first_day(today) for period, first_day in CALENDAR_PERIODS.items()},
    }


def _rank(scans: pl.DataFrame, limit: int, *, total: int) -> list[TopScan]:
    """The codes in `scans` by number of scans, most first; ties go to the most recently scanned.

    `total` is the number of scans each share is a fraction of.
    """
    ranked = (
        scans.group_by("code")
        .agg(
            pl.len().alias("count"),
            pl.col("scanned_at").max().alias("last_scanned_at"),
            pl.col("product_name").first(),
            pl.col("product_name_source").first(),
            pl.col("product_brands").first(),
            pl.col("product_known").first(),
        )
        .sort(["count", "last_scanned_at", "code"], descending=[True, True, False])
        .head(limit)
    )
    return [
        TopScan(
            code=row["code"],
            name=row["product_name"],
            name_source=row["product_name_source"],
            brands=row["product_brands"],
            known=bool(row["product_known"]),
            count=row["count"],
            share=round(row["count"] / total, 4),
        )
        for row in ranked.iter_rows(named=True)
    ]
