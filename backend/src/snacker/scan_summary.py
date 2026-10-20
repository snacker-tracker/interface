"""Scan summary: what a set of scans amounts to, shaped like the published JSON.

Days are counted in each scan's office time zone, so the scans table must carry an
`office_time_zone` column (see Locations.with_office_time_zones) alongside `scanned_at` in UTC,
plus each scan's scanned product as a `product` column (see products.with_products).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from collections.abc import Callable
from typing import Any, cast, get_args
from zoneinfo import ZoneInfo

import polars as pl

from snacker.contract import (
    PERIODS,
    DailyCount,
    HealthiestAndLeastHealthy,
    HealthiestAndLeastHealthyByPeriod,
    HourlyCount,
    NutriScore,
    PeriodDays,
    PeriodDaysByPeriod,
    ScanRow,
    TopScan,
    TopScansByPeriod,
)
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
    ]).rechunk()  # One chunk per zone otherwise, which the product struct must not be (see products.with_products).


def _recent_scans(scans: pl.DataFrame, limit: int) -> list[ScanRow]:
    rows = (
        scans.sort(["scanned_at", "event_id"], descending=True)
        .head(limit)
        .select("product", "location", "scanned_at", "office_time_zone")
    )
    return [
        cast(ScanRow, {
            **row["product"],
            "location": row["location"],
            "scanned_at": row["scanned_at"].strftime(UTC_TIMESTAMP_FORMAT),
            "office_time": in_office_time_zone(row["scanned_at"], row["office_time_zone"]),
            "office_time_zone": row["office_time_zone"],
        })
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
    ranked = flagged.filter(~pl.col("product").struct.field("known")) if unknown_only else flagged
    return cast(TopScansByPeriod, {
        period: _rank(ranked.filter(pl.col(period)), limit, total=flagged.filter(pl.col(period)).height)
        for period in PERIODS
    })


def period_days(scans: pl.DataFrame, *, now: datetime) -> PeriodDaysByPeriod:
    """For every period (see PERIODS), the office days it touches in the scans' office time
    zones, from the earliest first day to the latest build day. Without scans there's no
    office time zone to count days in, so every day is null.
    """
    if scans.is_empty():
        return cast(PeriodDaysByPeriod, {period: PeriodDays(first_day=None, last_day=None) for period in PERIODS})
    zones = [ZoneInfo(zone) for zone in scans["office_time_zone"].unique().to_list()]
    last_day = max(now.astimezone(zone).date() for zone in zones)
    first_scanned = cast(date, _with_office_moments(scans.filter(pl.col("scanned_at") <= now))["office_date"].min())
    first_days: dict[str, date] = {
        **{
            period: min(first_day(now.astimezone(zone).date()) for zone in zones)
            for period, first_day in CALENDAR_PERIODS.items()
        },
        **{
            period: min((now - duration).astimezone(zone).date() for zone in zones)
            for period, duration in ROLLING_PERIODS.items()
        },
        # Scans after the build fall in no period, so all time can start on the build day.
        "all-time": first_scanned or last_day,
    }
    return cast(PeriodDaysByPeriod, {
        period: PeriodDays(first_day=first_days[period].strftime(DATE_FORMAT), last_day=last_day.strftime(DATE_FORMAT))
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
    ranked = _per_code(scans).sort(["count", "last_scanned_at", "code"], descending=[True, True, False]).head(limit)
    return [_top_scan(row, total) for row in ranked.iter_rows(named=True)]


def healthiest_and_least_healthy(scans: pl.DataFrame, *, limit: int, now: datetime) -> HealthiestAndLeastHealthyByPeriod:
    """For every period (see PERIODS), its healthiest and least healthy products (GLOSSARY.md).

    `now` is when the data is built, as for top_scans.
    """
    flagged = _with_period_flags(scans, now)
    return cast(HealthiestAndLeastHealthyByPeriod, {
        period: _split_by_health(flagged.filter(pl.col(period)), limit) for period in PERIODS
    })


def _split_by_health(scans: pl.DataFrame, limit: int) -> HealthiestAndLeastHealthy:
    """The graded products ranked best first and split in halves, each cut to `limit`: the
    better half is the healthiest, and an odd count's extra product goes to it. The least
    healthy are the worst of the rest, so a big period lists its 10 best and 10 worst."""
    nutri_score = pl.col("product").struct.field("nutri_score")
    graded = _per_code(scans.filter(nutri_score.is_not_null())).with_columns(
        nutri_score.cast(pl.Enum(get_args(NutriScore))).to_physical().alias("grade")
    )
    healthiest_count = min(limit, (graded.height + 1) // 2)
    least_healthy_count = min(limit, graded.height // 2)
    # Within a grade, as in top scans: most scanned first, ties to the most recently scanned.
    order = ["grade", "count", "last_scanned_at", "code"]
    healthiest = graded.sort(order, descending=[False, True, True, False]).head(healthiest_count)
    least_healthy = (
        graded.join(healthiest, on="code", how="anti")
        .sort(order, descending=[True, True, True, False])
        .head(least_healthy_count)
    )
    return HealthiestAndLeastHealthy(
        healthiest=[_top_scan(row, scans.height) for row in healthiest.iter_rows(named=True)],
        least_healthy=[_top_scan(row, scans.height) for row in least_healthy.iter_rows(named=True)],
        graded_scans=int(graded["count"].sum()),
        scans=scans.height,
    )


def _per_code(scans: pl.DataFrame) -> pl.DataFrame:
    """One row per code in `scans`: its count, when it was last scanned, and its scanned product."""
    return scans.group_by("code").agg(
        pl.len().alias("count"),
        pl.col("scanned_at").max().alias("last_scanned_at"),
        pl.col("product").first(),
    )


def _top_scan(row: dict[str, Any], total: int) -> TopScan:
    return cast(TopScan, {**row["product"], "count": row["count"], "share": round(row["count"] / total, 4)})
